"""APScheduler 잡 정의 — snapshot(10분), fundamentals(1일, Phase β), universe(1일, γ)."""
import logging
import os
import traceback
from datetime import date, datetime, timedelta
from typing import Callable

import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler

import core.repository as repo
from core.ema_scan import run_ema_scan, _load_tickers as _load_ema_tickers
from core.fx import get_fx_provider
from core.indicators import compute_indicators
from core.data.prices_provider import fetch_ohlcv
from core.data.fundamental_backfill import hydrate_fundamental_snapshots
from core.data.price_target_backfill import hydrate_price_target_consensus_snapshots
from core.data.choicestock_public import get_public_summary, is_supported_public_ticker
from core.prices.selection import prefer_toss_market_data
from core.prices.kis import KISPriceProvider
from core.prices.toss import fetch_buying_power as fetch_toss_buying_power
from core.prices.toss import fetch_holdings as fetch_toss_holdings
from core.prices.toss import TossPriceProvider
from core.scoring.technical_timing import analyze_timing
from core.telegram import send_telegram

log = logging.getLogger(__name__)

_price_provider = TossPriceProvider() if prefer_toss_market_data() else KISPriceProvider()
_fx_provider = get_fx_provider()


JobFunc = Callable[[], object]


def snapshot_job():
    """보유 종목 있는 사용자 전원에 대해 현재가 + 환율 → portfolio_snapshots (10분 주기)."""
    try:
        ts = datetime.now().replace(second=0, microsecond=0)
        try:
            usdkrw = _fx_provider.get_rate("USDKRW")
            repo.insert_fx_rate(ts=ts, pair="USDKRW", rate=usdkrw)
        except Exception as e:
            cached = repo.get_latest_fx_rate("USDKRW")
            if not cached:
                raise
            usdkrw = cached
            log.warning("USDKRW 조회 실패: %s — 최신 저장 환율 %.2f 사용", e, usdkrw)

        user_ids = repo.get_active_user_ids_with_holdings()
        if not user_ids:
            return

        for user_id in user_ids:
            _snapshot_for_user(user_id, usdkrw, ts)

        log.info("snapshot_job 완료: 사용자 %d명", len(user_ids))
    except Exception as e:
        log.error("snapshot_job 오류: %s", e)
        raise


def _snapshot_for_user(user_id: int, usdkrw: float, ts: datetime):
    try:
        holdings = repo.get_holdings(user_id)
        if not holdings:
            return

        tickers = [h["ticker"] for h in holdings]
        markets = {h["ticker"]: h.get("market") for h in holdings}
        try:
            prices = _price_provider.get_current_prices(tickers, markets=markets)
        except Exception as e:
            prices = {}
            log.warning("스냅샷 현재가 조회 실패(user_id=%d): %s — 평단 기준으로 저장", user_id, e)

        cash = repo.get_cash_total(user_id)
        cash_krw = cash["cash_krw"]
        cash_usd = cash["cash_usd"]

        total_equity_krw = 0.0
        total_equity_usd = 0.0
        holdings_snapshot = []

        for h in holdings:
            ticker = h["ticker"]
            p = prices.get(ticker)
            current = p.current if p else h["avg_price"]
            currency = p.currency if p else h["currency"]
            mv = current * h["quantity"]
            if currency == "KRW":
                mv_krw, mv_usd = mv, mv / usdkrw
            else:
                mv_krw, mv_usd = mv * usdkrw, mv
            total_equity_krw += mv_krw
            total_equity_usd += mv_usd
            holdings_snapshot.append({
                "ticker": ticker, "price": current, "currency": currency,
                "quantity": h["quantity"], "mv_krw": mv_krw,
            })

        cash_total_krw = cash_krw + cash_usd * usdkrw
        cash_total_usd = cash_krw / usdkrw + cash_usd

        repo.insert_snapshot(
            user_id=user_id,
            ts=ts,
            total_equity_krw=total_equity_krw,
            total_with_cash_krw=total_equity_krw + cash_total_krw,
            cash_krw=cash_total_krw,
            total_equity_usd=total_equity_usd,
            total_with_cash_usd=total_equity_usd + cash_total_usd,
            cash_usd=cash_total_usd,
            usdkrw=usdkrw,
            holdings_json=holdings_snapshot,
        )
    except Exception as e:
        log.error("_snapshot_for_user(user_id=%d) 오류: %s", user_id, e)


def snapshot_rollup_job(bucket: str = "10m"):
    """portfolio_snapshots 원본을 차트용 시간 버킷으로 집계합니다."""
    return repo.refresh_snapshot_rollups(buckets=(bucket,))


def prices_refresh_kr_job():
    """KR EMA 유니버스 OHLCV 강제 갱신 — EMA 스캔 전 15:45 실행."""
    tickers = _load_ema_tickers("KR")
    end = date.today()
    start = end - timedelta(days=130)
    _BATCH = 50
    log.info("prices_refresh_kr: %d개 종목 강제 갱신 시작", len(tickers))
    for i in range(0, len(tickers), _BATCH):
        batch = tickers[i:i + _BATCH]
        try:
            fetch_ohlcv(batch, start, end, force=True)
        except Exception as e:
            log.error("prices_refresh_kr 배치 오류 (%s...): %s", batch[:2], e)
    log.info("prices_refresh_kr: 갱신 완료")


def ema_scan_kr_job():
    """국장 EMA 골든크로스 스캔 — 매일 16:00 KST."""
    try:
        result = run_ema_scan("KR")
        log.info("ema_scan_kr 완료: %s", result)
    except Exception as e:
        log.error("ema_scan_kr_job 오류: %s", e)
        raise


def prices_refresh_us_job():
    """US EMA 유니버스 OHLCV 강제 갱신 — EMA 스캔 전 06:45 실행."""
    tickers = _load_ema_tickers("US")
    end = date.today()
    start = end - timedelta(days=130)
    _BATCH = 50
    log.info("prices_refresh_us: %d개 종목 강제 갱신 시작", len(tickers))
    for i in range(0, len(tickers), _BATCH):
        batch = tickers[i:i + _BATCH]
        try:
            fetch_ohlcv(batch, start, end, force=True)
        except Exception as e:
            log.error("prices_refresh_us 배치 오류 (%s...): %s", batch[:2], e)
    log.info("prices_refresh_us: 갱신 완료")


def ema_scan_us_job():
    """미장 EMA 골든크로스 스캔 — 매일 07:00 KST."""
    try:
        result = run_ema_scan("US")
        log.info("ema_scan_us 완료: %s", result)
    except Exception as e:
        log.error("ema_scan_us_job 오류: %s", e)
        raise


def growth_batch_kr_job():
    """국장 성장주 배치 — 매일 16:10 KST."""
    if not os.getenv("DART_API_KEY"):
        log.error("growth_batch_kr 건너뜀: DART_API_KEY가 필요합니다.")
        return
    _run_growth_universes(("kospi200", "kosdaq150"))


def growth_batch_us_job():
    """미장 성장주 배치 — 매일 07:10 KST."""
    _run_growth_universes(("sp500", "nasdaq100"))


def toss_holdings_sync_job():
    """Toss 보유종목/현금 자동 동기화."""
    if os.getenv("TOSS_HOLDINGS_SYNC_ENABLED", "").lower() not in ("1", "true", "yes"):
        return

    user_ids = repo.get_active_user_ids()
    if not user_ids:
        return

    try:
        holdings = fetch_toss_holdings()
        cash_krw = fetch_toss_buying_power("KRW")
        cash_usd = fetch_toss_buying_power("USD")
    except Exception as e:
        log.error("toss_holdings_sync_job 조회 오류: %s", e)
        raise

    for user_id in user_ids:
        try:
            for item in holdings:
                repo.upsert_holding(
                    user_id=user_id,
                    source="toss",
                    preserve_display_fields=True,
                    **item,
                )
            repo.set_cash_source(user_id, "toss", cash_krw, cash_usd)
        except Exception as e:
            log.error("toss_holdings_sync_job 저장 오류(user_id=%d): %s", user_id, e)

    log.info("toss_holdings_sync_job 완료: 사용자 %d명, 종목 %d개", len(user_ids), len(holdings))
    return {"users": len(user_ids), "holdings": len(holdings)}


def fundamental_snapshots_hydrate_job():
    """관심종목/보유종목 미국 펀더멘털 snapshot 명시 적재."""
    result = hydrate_fundamental_snapshots()
    log.info(
        "fundamental_snapshots_hydrate_job 완료: requested=%d updated=%d skipped=%d",
        result["requested"],
        result["updated"],
        result["skipped"],
    )
    return {key: value for key, value in result.items() if key != "errors"}


def price_target_consensus_hydrate_job():
    """관심종목/보유종목 목표주가 consensus snapshot 명시 적재."""
    result = hydrate_price_target_consensus_snapshots()
    log.info(
        "price_target_consensus_hydrate_job 완료: requested=%d updated=%d skipped=%d",
        result["requested"],
        result["updated"],
        result["skipped"],
    )
    return {key: value for key, value in result.items() if key != "errors"}


def choicestock_public_hydrate_job():
    """관심종목의 ChoiceStock 공개 summary 캐시를 하루 1회 보강."""
    tickers = [
        ticker
        for ticker in repo.list_all_watchlist_tickers()
        if is_supported_public_ticker(ticker)
    ]
    if not tickers:
        return {"tickers": 0, "updated": 0, "failed": 0}

    updated = 0
    failed = 0
    for ticker in tickers:
        try:
            before = repo.get_choicestock_public_snapshot(ticker, date.today())
            result = get_public_summary(ticker)
            if result and before is None:
                updated += 1
        except Exception as exc:
            failed += 1
            log.warning("choicestock_public_hydrate 실패 (%s): %s", ticker, exc)

    log.info("choicestock_public_hydrate 완료: tickers=%d updated=%d failed=%d", len(tickers), updated, failed)
    return {"tickers": len(tickers), "updated": updated, "failed": failed}


def _run_growth_universes(universes: tuple[str, ...]):
    import core.batch_state as bs
    from core.batch_refresh import get_status
    from core.scoring.universe_scorer import run_batch

    for universe in universes:
        status = get_status(universe)
        if status["status"] == "running":
            log.warning("growth batch 건너뜀: %s 배치가 이미 실행 중입니다.", universe)
            continue
        if status["is_fresh"]:
            log.info("growth batch 건너뜀: %s 데이터가 이미 최신입니다.", universe)
            continue
        try:
            run_batch(universe)
        except Exception as e:
            log.error("growth batch 오류 (%s): %s", universe, e)
            bs.fail(universe, str(e))


def _check_condition(alert: dict, current_price: float, ohlcv_df: pd.DataFrame | None) -> bool:
    """알림 조건 충족 여부 반환."""
    ct = alert["condition_type"]
    cv = alert.get("condition_value")

    if ct == "price_above":
        return cv is not None and current_price > cv
    if ct == "price_below":
        return cv is not None and current_price < cv

    if ohlcv_df is None or len(ohlcv_df) < 21:
        return False

    indicators = compute_indicators(ohlcv_df)

    if ct in ("rsi_above", "rsi_below") and cv is not None:
        rsi_pts = indicators["rsi"]
        if not rsi_pts:
            return False
        last_rsi = rsi_pts[-1]["value"]
        return last_rsi > cv if ct == "rsi_above" else last_rsi < cv

    if ct in ("ma_golden_cross", "ma_dead_cross"):
        ma5 = indicators["ma"]["5"]
        ma20 = indicators["ma"]["20"]
        if len(ma5) < 2 or len(ma20) < 2:
            return False
        prev_above = ma5[-2]["value"] > ma20[-2]["value"]
        curr_above = ma5[-1]["value"] > ma20[-1]["value"]
        if ct == "ma_golden_cross":
            return (not prev_above) and curr_above     # prev: MA5 < MA20, curr: MA5 > MA20
        else:  # dead_cross
            return prev_above and (not curr_above)     # prev: MA5 > MA20, curr: MA5 < MA20

    return False


def alert_check_job():
    """활성 알림 조건 체크 — 조건 충족 시 user_alert_events 삽입 (1분 주기)."""
    try:
        alerts = repo.get_all_enabled_alerts()
        if not alerts:
            return

        # 티커별로 현재가 일괄 조회
        tickers = list({a["ticker"] for a in alerts})
        try:
            prices = _price_provider.get_current_prices(tickers)
        except Exception as e:
            log.warning("alert_check_job 시세 조회 실패: %s", e)
            raise

        # RSI/MA 조건이 있는 티커만 OHLCV 조회
        indicator_tickers = {
            a["ticker"] for a in alerts
            if a["condition_type"] in ("rsi_above", "rsi_below", "ma_golden_cross", "ma_dead_cross")
        }
        ohlcv_cache: dict[str, pd.DataFrame] = {}
        if indicator_tickers:
            end = date.today()
            start = end - timedelta(days=60)
            for ticker in indicator_tickers:
                try:
                    prices_df, _ = fetch_ohlcv([ticker], start, end)
                    if not prices_df.empty and ticker in prices_df.columns.get_level_values(0):
                        ohlcv_cache[ticker] = prices_df[ticker][
                            ["Open", "High", "Low", "Close", "Volume"]
                        ].dropna()
                except Exception:
                    pass

        for alert in alerts:
            try:
                ticker = alert["ticker"]
                if ticker not in prices:
                    continue

                current_price = prices[ticker].current
                ohlcv_df = ohlcv_cache.get(ticker)

                if repo.has_recent_alert_event(alert["id"], minutes=60):
                    continue

                if _check_condition(alert, current_price, ohlcv_df):
                    repo.insert_alert_event(
                        user_id=alert["user_id"],
                        alert_id=alert["id"],
                        ticker=ticker,
                        condition_type=alert["condition_type"],
                        condition_value=alert.get("condition_value"),
                        triggered_price=current_price,
                    )
                    log.info("alert fired: user=%d ticker=%s type=%s price=%.2f",
                             alert["user_id"], ticker, alert["condition_type"], current_price)
            except Exception as e:
                log.error("alert check 오류 (alert_id=%d): %s", alert.get("id", -1), e)

    except Exception as e:
        log.error("alert_check_job 오류: %s", e)
        raise


def daily_holdings_news_job():
    """관심종목의 ChoiceStock 공개 summary 오늘 뉴스를 Telegram으로 발송."""
    today = datetime.now().date()
    tickers = [
        ticker
        for ticker in repo.list_all_watchlist_tickers()
        if is_supported_public_ticker(ticker)
    ]
    if not tickers:
        return {"tickers": 0, "sent": False}

    lines = [f"관심종목 오늘 뉴스 ({today.isoformat()})"]
    count = 0
    for ticker in sorted(tickers):
        summary = get_public_summary(ticker)
        today_items = [
            item for item in (summary or {}).get("news", [])
            if _is_choicestock_news_today(item, today)
        ]
        if not today_items:
            continue
        lines.append(f"\n[{ticker}]")
        for item in today_items[:3]:
            title = item.get("title", "")
            link = item.get("url", "")
            site = item.get("site", "ChoiceStock public page")
            lines.append(f"- {title} ({site})\n  {link}")
            count += 1

    if count == 0:
        return {"tickers": len(tickers), "news": 0, "sent": False}
    sent = send_telegram("\n".join(lines))
    return {"tickers": len(tickers), "news": count, "sent": sent}


def _is_choicestock_news_today(item: dict, today: date) -> bool:
    published = str(item.get("published_date") or "")
    try:
        return datetime.strptime(published[:10], "%Y.%m.%d").date() == today
    except Exception:
        return False


def daily_watchlist_timing_alert_job():
    """알림 체크된 관심종목의 TIMING CHECK를 Telegram으로 발송."""
    items = repo.list_timing_alert_watchlist_items()
    if not items:
        return {"items": 0, "sent": False}

    today = datetime.now().date().isoformat()
    lines = [f"관심종목 TIMING CHECK ({today})"]
    success = 0
    failed = 0
    for item in items:
        ticker = item["ticker"]
        try:
            timing = analyze_timing(ticker)
            lines.extend(_format_watchlist_timing_alert(item, timing))
            success += 1
        except Exception as exc:
            failed += 1
            log.error("watchlist timing alert 오류 (%s): %s", ticker, exc)
            lines.append(f"\n[{item['watchlist_name']}] {ticker}\n상태: 분석 실패")

    sent = send_telegram("\n".join(lines))
    return {"items": len(items), "success": success, "failed": failed, "sent": sent}


def _format_watchlist_timing_alert(item: dict, timing: dict) -> list[str]:
    label = _timing_status_label(timing)
    name = item.get("name") or item["ticker"]
    reasons = (
        timing.get("downgrade_reasons")
        or timing.get("warning_reasons")
        or timing.get("positive_reasons")
        or []
    )
    reason_text = " / ".join(str(reason) for reason in reasons[:2]) if reasons else "특이 사유 없음"
    return [
        "",
        f"[{item['watchlist_name']}] {item['ticker']} {name}",
        f"상태: {label}",
        (
            "현재가/EMA20/50/200: "
            f"{_fmt_number(timing.get('close'))} / "
            f"{_fmt_number(timing.get('ema20'))} / "
            f"{_fmt_number(timing.get('ema50'))} / "
            f"{_fmt_number(timing.get('ema200'))}"
        ),
        (
            "눌림/거래량/RSI: "
            f"{_PULLBACK_LABEL.get(str(timing.get('pullback_stage')), timing.get('pullback_stage') or '-')} / "
            f"{_VOLUME_DIRECTION_LABEL.get(str(timing.get('volume_direction')), timing.get('volume_direction') or '-')} "
            f"{_VOLUME_LABEL.get(str(timing.get('volume_level')), timing.get('volume_level') or '-')}"
            f" {_fmt_ratio(timing.get('volume_ratio'))} / "
            f"{_fmt_number(timing.get('rsi14'))} "
            f"{_RSI_LABEL.get(str(timing.get('rsi_level')), timing.get('rsi_level') or '-')}"
        ),
        f"사유: {reason_text}",
    ]


def _timing_status_label(timing: dict) -> str:
    status = timing.get("status") or "unknown"
    if status == "watch" and timing.get("aligned") and timing.get("pullback_stage") != "none":
        return "진입대기"
    if status == "watch" and timing.get("aligned"):
        return "추세확인"
    return _TIMING_STATUS_LABEL.get(str(status), str(status))


def _fmt_number(value) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_ratio(value) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2f}x"
    except (TypeError, ValueError):
        return str(value)


_TIMING_STATUS_LABEL = {
    "suitable": "진입후보",
    "watch": "추세확인",
    "unsuitable": "대기",
    "unknown": "부족",
}

_PULLBACK_LABEL = {
    "approach": "눌림목 접근",
    "lower": "눌림목 하단",
    "breakdown": "이탈 주의",
    "none": "눌림 없음",
}

_VOLUME_DIRECTION_LABEL = {
    "bullish": "양봉",
    "bearish": "음봉",
    "flat": "보합",
}

_VOLUME_LABEL = {
    "quiet": "낮음",
    "normal": "보통",
    "increased": "증가",
    "strong": "강함",
    "explosive": "폭발",
}

_RSI_LABEL = {
    "oversold": "과매도",
    "neutral": "중립",
    "overheated": "과열 주의",
    "extreme_overheated": "극단 과열",
}


def _job_registry() -> list[dict]:
    return [
        {
            "id": "snapshot",
            "name": "자산 스냅샷",
            "category": "portfolio",
            "schedule": "10분마다",
            "description": "보유종목 현재가, 현금, 환율을 계산해 포트폴리오 스냅샷을 저장합니다.",
            "bootstrap": True,
            "bootstrap_description": "보유/현금 동기화 후 포트폴리오 첫 스냅샷을 만듭니다.",
            "func": snapshot_job,
        },
        {
            "id": "snapshot_rollup_10m",
            "name": "자산 추이 10분 집계",
            "category": "portfolio",
            "schedule": "10분마다",
            "description": "자산 스냅샷을 10분 단위 차트 데이터로 저장합니다.",
            "bootstrap": True,
            "bootstrap_description": "기존 자산 스냅샷을 10분 단위 차트 데이터로 집계합니다.",
            "func": lambda: snapshot_rollup_job("10m"),
        },
        {
            "id": "snapshot_rollup_1h",
            "name": "자산 추이 1시간 집계",
            "category": "portfolio",
            "schedule": "매시 1분",
            "description": "자산 스냅샷을 1시간 단위 차트 데이터로 저장합니다.",
            "bootstrap": True,
            "bootstrap_description": "기존 자산 스냅샷을 1시간 단위 차트 데이터로 집계합니다.",
            "func": lambda: snapshot_rollup_job("1h"),
        },
        {
            "id": "snapshot_rollup_1d",
            "name": "자산 추이 일별 집계",
            "category": "portfolio",
            "schedule": "매일 00:05 KST",
            "description": "자산 스냅샷을 일별 차트 데이터로 저장합니다.",
            "bootstrap": True,
            "bootstrap_description": "기존 자산 스냅샷을 일별 차트 데이터로 집계합니다.",
            "func": lambda: snapshot_rollup_job("1d"),
        },
        {
            "id": "snapshot_rollup_1w",
            "name": "자산 추이 주별 집계",
            "category": "portfolio",
            "schedule": "매주 월요일 00:10 KST",
            "description": "자산 스냅샷을 주별 차트 데이터로 저장합니다.",
            "bootstrap": True,
            "bootstrap_description": "기존 자산 스냅샷을 주별 차트 데이터로 집계합니다.",
            "func": lambda: snapshot_rollup_job("1w"),
        },
        {
            "id": "snapshot_rollup_1mo",
            "name": "자산 추이 월별 집계",
            "category": "portfolio",
            "schedule": "매월 1일 00:15 KST",
            "description": "자산 스냅샷을 월별 차트 데이터로 저장합니다.",
            "bootstrap": True,
            "bootstrap_description": "기존 자산 스냅샷을 월별 차트 데이터로 집계합니다.",
            "func": lambda: snapshot_rollup_job("1mo"),
        },
        {
            "id": "alert_check",
            "name": "가격/지표 알림 체크",
            "category": "alert",
            "schedule": "1분마다",
            "description": "가격, RSI, 이동평균 조건을 확인해 알림 이벤트를 생성합니다.",
            "func": alert_check_job,
        },
        {
            "id": "prices_refresh_kr",
            "name": "국장 EMA 가격 갱신",
            "category": "price",
            "schedule": "매일 15:45 KST",
            "description": "국장 EMA 스캔 전에 KOSPI200/KOSDAQ150 OHLCV 캐시를 갱신합니다.",
            "bootstrap": True,
            "bootstrap_description": "국내 지수 구성 종목의 가격 캐시를 먼저 채웁니다.",
            "func": prices_refresh_kr_job,
        },
        {
            "id": "ema_scan_kr",
            "name": "국장 EMA 골든크로스",
            "category": "telegram",
            "schedule": "매일 16:00 KST",
            "description": "국장 EMA 골든크로스 종목을 스캔하고 Telegram으로 발송합니다.",
            "func": ema_scan_kr_job,
        },
        {
            "id": "prices_refresh_us",
            "name": "미장 EMA 가격 갱신",
            "category": "price",
            "schedule": "매일 06:45 KST",
            "description": "미장 EMA 스캔 전에 S&P500/NASDAQ100 OHLCV 캐시를 갱신합니다.",
            "bootstrap": True,
            "bootstrap_description": "미국 지수 구성 종목의 가격 캐시를 먼저 채웁니다.",
            "func": prices_refresh_us_job,
        },
        {
            "id": "ema_scan_us",
            "name": "미장 EMA 골든크로스",
            "category": "telegram",
            "schedule": "매일 07:00 KST",
            "description": "미장 EMA 골든크로스 종목을 스캔하고 Telegram으로 발송합니다.",
            "func": ema_scan_us_job,
        },
        {
            "id": "growth_batch_kr",
            "name": "국장 성장주 배치",
            "category": "valuation",
            "schedule": "매일 16:10 KST",
            "description": "KOSPI200/KOSDAQ150 valuation, quality, growth, technical 점수를 갱신합니다.",
            "bootstrap": True,
            "bootstrap_description": "국내 종목 분석 화면에서 사용할 점수 데이터를 적재합니다.",
            "func": growth_batch_kr_job,
        },
        {
            "id": "growth_batch_us",
            "name": "미장 성장주 배치",
            "category": "valuation",
            "schedule": "매일 07:10 KST",
            "description": "S&P500/NASDAQ100 valuation, quality, growth, technical 점수를 갱신합니다.",
            "bootstrap": True,
            "bootstrap_description": "미국 종목 분석 화면에서 사용할 점수 데이터를 적재합니다.",
            "func": growth_batch_us_job,
        },
        {
            "id": "toss_holdings_sync",
            "name": "Toss 보유/현금 동기화",
            "category": "broker",
            "schedule": f"{int(os.getenv('TOSS_HOLDINGS_SYNC_INTERVAL_MINUTES', '60'))}분마다",
            "description": "Toss 보유종목과 매수 가능 현금을 가져와 source=toss로 저장합니다.",
            "bootstrap": True,
            "bootstrap_description": "Toss 보유종목과 현금을 최초로 가져옵니다.",
            "func": toss_holdings_sync_job,
        },
        {
            "id": "fundamental_snapshots_hydrate",
            "name": "관심/보유 펀더멘털 적재",
            "category": "valuation",
            "schedule": "매일 08:20 KST",
            "description": "관심종목과 보유종목의 미국 펀더멘털 snapshot을 Finviz/StockAnalysis 수집 작업으로 저장합니다.",
            "bootstrap": True,
            "bootstrap_description": "관심/보유 미국 종목의 펀더멘털 snapshot을 캐시에 저장합니다.",
            "func": fundamental_snapshots_hydrate_job,
        },
        {
            "id": "price_target_consensus_hydrate",
            "name": "관심/보유 목표주가 적재",
            "category": "valuation",
            "schedule": "매일 08:30 KST",
            "description": "관심종목과 보유종목의 목표주가 consensus를 백그라운드에서 수집해 snapshot으로 저장합니다.",
            "bootstrap": True,
            "bootstrap_description": "관심/보유 종목의 목표주가 consensus를 저장합니다.",
            "func": price_target_consensus_hydrate_job,
        },
        {
            "id": "choicestock_public_hydrate",
            "name": "관심종목 초이스스탁 공개 데이터 적재",
            "category": "valuation",
            "schedule": "매일 08:35 KST",
            "description": "관심종목의 초이스스탁 공개 summary 숫자와 뉴스 링크를 종목당 하루 1회만 캐시에 저장합니다.",
            "bootstrap": True,
            "bootstrap_description": "관심종목의 초이스스탁 공개 summary 캐시를 먼저 채웁니다.",
            "func": choicestock_public_hydrate_job,
        },
        {
            "id": "daily_holdings_news",
            "name": "관심종목 초이스스탁 오늘 뉴스",
            "category": "telegram",
            "schedule": "매일 08:40 KST",
            "description": "관심종목의 초이스스탁 공개 summary 오늘 뉴스 링크를 Telegram으로 발송합니다.",
            "func": daily_holdings_news_job,
        },
        {
            "id": "daily_watchlist_timing_alert",
            "name": "관심종목 TIMING CHECK",
            "category": "telegram",
            "schedule": "매일 08:50 KST",
            "description": "알림 체크된 관심종목의 TIMING CHECK 요약을 Telegram으로 발송합니다.",
            "func": daily_watchlist_timing_alert_job,
        },
    ]


def get_job_definitions() -> list[dict]:
    return [
        {k: v for k, v in job.items() if k != "func"}
        for job in _job_registry()
    ]


def get_bootstrap_job_definitions() -> list[dict]:
    return [
        {k: v for k, v in job.items() if k != "func"}
        for job in _job_registry()
        if job.get("bootstrap")
    ]


def run_bootstrap_jobs(trigger_type: str = "manual_bootstrap") -> dict:
    results = []
    for job in get_bootstrap_job_definitions():
        result = run_registered_job(job["id"], trigger_type)
        results.append({"job_id": job["id"], **result})
    return {
        "requested": len(results),
        "success": sum(1 for result in results if result.get("status") == "success"),
        "skipped": sum(1 for result in results if result.get("status") == "skipped"),
        "failed": sum(1 for result in results if result.get("status") == "failed"),
        "results": results,
    }


def run_registered_job(job_id: str, trigger_type: str = "manual") -> dict:
    jobs = {job["id"]: job for job in _job_registry()}
    if job_id not in jobs:
        raise KeyError(job_id)
    return _run_tracked(job_id, trigger_type, jobs[job_id]["func"])


def _run_tracked(job_id: str, trigger_type: str, func: JobFunc) -> dict:
    run_id, should_run = repo.start_job_run(job_id, trigger_type)
    if not should_run:
        return {"run_id": run_id, "status": "skipped"}

    try:
        result = func()
        meta = result if isinstance(result, dict) else {}
        message = _job_message(meta)
        repo.finish_job_run(run_id, "success", message=message, meta=meta)
        return {"run_id": run_id, "status": "success", "meta": meta}
    except Exception as e:
        log.error("job failed: %s: %s", job_id, e)
        repo.finish_job_run(
            run_id,
            "failed",
            error=traceback.format_exc(limit=8),
            message=str(e),
        )
        return {"run_id": run_id, "status": "failed", "error": str(e)}


def _job_message(meta: dict) -> str:
    if not meta:
        return "완료"
    parts = [f"{key}={value}" for key, value in meta.items() if value is not None]
    return ", ".join(parts) if parts else "완료"


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(lambda: run_registered_job("snapshot", "schedule"), "interval", minutes=10, id="snapshot",
                      next_run_time=datetime.now())
    scheduler.add_job(lambda: run_registered_job("snapshot_rollup_10m", "schedule"), "interval", minutes=10,
                      id="snapshot_rollup_10m")
    scheduler.add_job(lambda: run_registered_job("snapshot_rollup_1h", "schedule"), "cron", minute=1,
                      id="snapshot_rollup_1h", timezone="Asia/Seoul")
    scheduler.add_job(lambda: run_registered_job("snapshot_rollup_1d", "schedule"), "cron", hour=0, minute=5,
                      id="snapshot_rollup_1d", timezone="Asia/Seoul")
    scheduler.add_job(lambda: run_registered_job("snapshot_rollup_1w", "schedule"), "cron", day_of_week="mon", hour=0, minute=10,
                      id="snapshot_rollup_1w", timezone="Asia/Seoul")
    scheduler.add_job(lambda: run_registered_job("snapshot_rollup_1mo", "schedule"), "cron", day=1, hour=0, minute=15,
                      id="snapshot_rollup_1mo", timezone="Asia/Seoul")
    scheduler.add_job(lambda: run_registered_job("alert_check", "schedule"), "interval", minutes=1, id="alert_check")
    scheduler.add_job(lambda: run_registered_job("prices_refresh_kr", "schedule"), "cron", hour=15, minute=45,
                      id="prices_refresh_kr", timezone="Asia/Seoul")
    scheduler.add_job(lambda: run_registered_job("ema_scan_kr", "schedule"), "cron", hour=16, minute=0,
                      id="ema_scan_kr", timezone="Asia/Seoul")
    scheduler.add_job(lambda: run_registered_job("prices_refresh_us", "schedule"), "cron", hour=6, minute=45,
                      id="prices_refresh_us", timezone="Asia/Seoul")
    scheduler.add_job(lambda: run_registered_job("ema_scan_us", "schedule"), "cron", hour=7, minute=0,
                      id="ema_scan_us", timezone="Asia/Seoul")
    scheduler.add_job(lambda: run_registered_job("growth_batch_kr", "schedule"), "cron", hour=16, minute=10,
                      id="growth_batch_kr", timezone="Asia/Seoul")
    scheduler.add_job(lambda: run_registered_job("growth_batch_us", "schedule"), "cron", hour=7, minute=10,
                      id="growth_batch_us", timezone="Asia/Seoul")
    scheduler.add_job(
        lambda: run_registered_job("toss_holdings_sync", "schedule"),
        "interval",
        minutes=int(os.getenv("TOSS_HOLDINGS_SYNC_INTERVAL_MINUTES", "60")),
        id="toss_holdings_sync",
    )
    scheduler.add_job(lambda: run_registered_job("fundamental_snapshots_hydrate", "schedule"), "cron", hour=8, minute=20,
                      id="fundamental_snapshots_hydrate", timezone="Asia/Seoul")
    scheduler.add_job(lambda: run_registered_job("price_target_consensus_hydrate", "schedule"), "cron", hour=8, minute=30,
                      id="price_target_consensus_hydrate", timezone="Asia/Seoul")
    scheduler.add_job(lambda: run_registered_job("choicestock_public_hydrate", "schedule"), "cron", hour=8, minute=35,
                      id="choicestock_public_hydrate", timezone="Asia/Seoul")
    scheduler.add_job(lambda: run_registered_job("daily_holdings_news", "schedule"), "cron", hour=8, minute=40,
                      id="daily_holdings_news", timezone="Asia/Seoul")
    scheduler.add_job(lambda: run_registered_job("daily_watchlist_timing_alert", "schedule"), "cron", hour=8, minute=50,
                      id="daily_watchlist_timing_alert", timezone="Asia/Seoul")
    return scheduler
