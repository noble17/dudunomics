"""EMA 골든크로스 유니버스 스캔 — 종가 기준, Telegram 발송."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

import core.repository as repo
from core.data.prices_provider import fetch_ohlcv
from core.telegram import send_telegram

log = logging.getLogger(__name__)

_DATA_DIR = Path(os.getenv("DATA_DIR", "data"))

_TICKER_FILES = {
    "KR": [
        ("KOSPI200_PATH", "kospi200_tickers.json"),
        ("KOSDAQ150_PATH", "kosdaq150_tickers.json"),
    ],
    "US": [
        ("SP500_PATH", "sp500_tickers.json"),
        ("NASDAQ100_PATH", "nasdaq100_tickers.json"),
    ],
}

_GROUP_LABELS = {
    "KOSPI": "코스피",
    "KOSDAQ": "코스닥",
    "US": "미장",
}
_BATCH_SIZE = 50
_MAINTAINED_SEND_LIMIT_DAYS = 5


def _load_ticker_groups(market: str) -> list[tuple[str, list[str]]]:
    """유니버스 티커 리스트를 발송 그룹 단위로 반환."""
    seen: set[str] = set()
    groups: list[tuple[str, list[str]]] = []
    for idx, (env_key, default_name) in enumerate(_TICKER_FILES[market]):
        group = "US"
        if market == "KR":
            group = "KOSPI" if idx == 0 else "KOSDAQ"
        path = Path(os.getenv(env_key, str(_DATA_DIR / default_name)))
        if not path.exists():
            log.warning("티커 파일 없음: %s", path)
            continue
        tickers = json.loads(path.read_text())
        result: list[str] = []
        for t in tickers:
            if t not in seen:
                seen.add(t)
                result.append(t)
        if result:
            groups.append((group, result))
    return groups


def _load_tickers(market: str) -> list[str]:
    """유니버스 티커 리스트 반환 (중복 제거)."""
    result: list[str] = []
    for _, tickers in _load_ticker_groups(market):
        result.extend(tickers)
    return result


def _detect_golden_cross(close: pd.Series, today: date | None = None) -> dict | None:
    """EMA5 > EMA20 상태 확인. 최소 62 거래일 필요 (EMA60 워밍업).

    day_count: 골든크로스 첫 거래일~오늘 기준 영업일 수 (캐시 최신 여부와 무관).
    cross_start_date: 해당 구간의 첫 거래일.
    """
    if len(close) < 62:
        return None
    today = today or date.today()

    ema5 = close.ewm(span=5, adjust=False).mean()
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema60 = close.ewm(span=60, adjust=False).mean()

    curr_above = ema5.iloc[-1] > ema20.iloc[-1]
    if not curr_above:
        return None

    prev_above = ema5.iloc[-2] > ema20.iloc[-2]

    # 골든크로스 연속 구간의 첫 거래일 탐색
    streak_start = len(ema5) - 1
    while streak_start > 0 and ema5.iloc[streak_start - 1] > ema20.iloc[streak_start - 1]:
        streak_start -= 1

    cross_start = close.index[streak_start]
    if hasattr(cross_start, "date"):
        cross_start = cross_start.date()

    # 오늘 날짜 기준 영업일 수 (주말 제외, 공휴일 미제외)
    day_count = len(pd.bdate_range(str(cross_start), str(today)))

    return {
        "ema5": round(ema5.iloc[-1], 2),
        "ema20": round(ema20.iloc[-1], 2),
        "ema60": round(ema60.iloc[-1], 2),
        "close": round(close.iloc[-1], 2),
        "is_new_cross": not prev_above,
        "day_count": day_count,
        "cross_start_date": cross_start,
    }


def _ticker_label(ticker: str, names: dict[str, str]) -> str:
    name = names.get(ticker)
    return f"{name} ({ticker})" if name else ticker


def _format_entry(e: dict, names: dict[str, str]) -> str:
    return (
        f"• {_ticker_label(e['ticker'], names)} — {e['day_count']}일차\n"
        f"  현재가 {e['close']} | EMA5 {e['ema5']} | EMA20 {e['ema20']} | EMA60 {e['ema60']}"
    )


def _record_history(market: str, group: str, ticker: str, names: dict[str, str], status: str, result: dict | None, reason: str) -> None:
    repo.insert_golden_cross_history(
        ticker=ticker,
        market=market,
        group_name=group,
        name=names.get(ticker),
        status=status,
        day_count=result.get("day_count") if result else None,
        cross_start_date=result.get("cross_start_date") if result else None,
        close=result.get("close") if result else None,
        ema5=result.get("ema5") if result else None,
        ema20=result.get("ema20") if result else None,
        ema60=result.get("ema60") if result else None,
        reason=reason,
    )


def _build_group_message(group: str, today: date,
                         new_entries: list[dict], maintained_entries: list[dict],
                         names: dict[str, str]) -> str:
    label = _GROUP_LABELS.get(group, group)
    lines = [f"📈 EMA 골든크로스 ({label} · {today})"]

    if new_entries:
        lines.append("\n🆕 신규")
        for e in new_entries:
            lines.append(_format_entry(e, names))

    if maintained_entries:
        lines.append(f"\n🔄 유지 중 ({_MAINTAINED_SEND_LIMIT_DAYS}일 미만)")
        for e in maintained_entries:
            lines.append(_format_entry(e, names))

    if not new_entries and not maintained_entries:
        lines.append("\n해당 없음 — 현재 골든크로스 종목 없음")

    return "\n".join(lines)


def run_ema_scan(market: str) -> dict:
    """
    유니버스 EMA 골든크로스 스캔 실행.
    반환: {"new": int, "maintained": int}
    """
    ticker_groups = _load_ticker_groups(market)
    tickers = [ticker for _, group_tickers in ticker_groups for ticker in group_tickers]
    if not tickers:
        log.warning("ema_scan: 티커 없음 (market=%s)", market)
        return {"new": 0, "maintained": 0}

    today = date.today()
    end = today
    start = end - timedelta(days=130)  # 90 거래일 확보용 여유

    active_in_db: dict[str, dict] = {
        r["ticker"]: r for r in repo.get_active_golden_crosses(market)
    }

    entries_by_group = {
        group: {"new": [], "maintained": []}
        for group, _ in ticker_groups
    }
    names: dict[str, str] = repo.get_company_names(tickers)

    # 배치 단위로 OHLCV 조회
    for group, group_tickers in ticker_groups:
        for batch_start in range(0, len(group_tickers), _BATCH_SIZE):
            batch = group_tickers[batch_start:batch_start + _BATCH_SIZE]
            try:
                df, _ = fetch_ohlcv(batch, start, end, cache_only=True)
            except Exception as e:
                log.error("ema_scan fetch_ohlcv 오류 (batch=%s): %s", batch[:3], e)
                continue

            if df.empty:
                continue

            available = df.columns.get_level_values(0).unique().tolist()

            for ticker in batch:
                if ticker not in available:
                    continue
                try:
                    close = df[ticker]["Close"].dropna()
                    result = _detect_golden_cross(close, today)

                    if result is None:
                        # 골든크로스 아님 → DB에 있으면 삭제
                        if ticker in active_in_db:
                            old = active_in_db[ticker]
                            _record_history(
                                market,
                                old.get("group_name") or group,
                                ticker,
                                names,
                                "BROKEN",
                                None,
                                "EMA5가 EMA20 아래로 내려가 골든크로스가 종료되었습니다.",
                            )
                            repo.delete_golden_cross(ticker)
                        continue

                    entry = {**result, "ticker": ticker}
                    is_old_maintained = (not result["is_new_cross"]) and result["day_count"] >= _MAINTAINED_SEND_LIMIT_DAYS

                    if ticker not in active_in_db:
                        if is_old_maintained:
                            continue
                        repo.insert_golden_cross(ticker, market, names.get(ticker), result["cross_start_date"], group)
                        if result["is_new_cross"]:
                            entries_by_group[group]["new"].append(entry)
                            _record_history(market, group, ticker, names, "NEW", result, "신규 골든크로스 발생")
                        else:
                            entries_by_group[group]["maintained"].append(entry)
                            _record_history(market, group, ticker, names, "MAINTAINED", result, "5일 미만 유지 중")
                    else:
                        old = active_in_db[ticker]
                        active_group = old.get("group_name") or group
                        already_counted_today = old.get("already_sent_today", False)
                        if is_old_maintained:
                            _record_history(
                                market,
                                active_group,
                                ticker,
                                names,
                                "EXPIRED",
                                result,
                                "5일 이상 유지되어 활성 목록에서 제외되었습니다.",
                            )
                            repo.delete_golden_cross(ticker)
                        elif already_counted_today:
                            entries_by_group[group]["maintained"].append(entry)
                            _record_history(market, active_group, ticker, names, "MAINTAINED", result, "이미 오늘 확인된 유지 상태")
                        else:
                            repo.update_golden_cross(ticker, result["day_count"])
                            entries_by_group[group]["maintained"].append(entry)
                            _record_history(market, active_group, ticker, names, "MAINTAINED", result, "5일 미만 유지 중")

                except Exception as e:
                    log.warning("ema_scan 티커 처리 오류 (%s): %s", ticker, e)

    for group, entries in entries_by_group.items():
        msg = _build_group_message(group, today, entries["new"], entries["maintained"], names)
        send_telegram(msg, channel="alerts")

    new_count = sum(len(entries["new"]) for entries in entries_by_group.values())
    maintained_count = sum(len(entries["maintained"]) for entries in entries_by_group.values())
    log.info("ema_scan 완료: market=%s new=%d maintained=%d",
             market, new_count, maintained_count)
    return {"new": new_count, "maintained": maintained_count}
