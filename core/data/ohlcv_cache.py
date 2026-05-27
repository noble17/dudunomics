"""OHLCV DuckDB 캐시 레이어.

fetch_ohlcv / fetch_index 는 DB 우선 조회 → 캐시 미스 시 yfinance fetch 후 저장.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import text

from core import repository as repo

log = logging.getLogger(__name__)

# yfinance exclusive-end + 비영업일 허용 오차 (일수)
_TOLERANCE = timedelta(days=5)


def fetch_ohlcv(
    tickers: list[str],
    start: date,
    end: date,
) -> tuple[pd.DataFrame, list[str]]:
    """tickers OHLCV MultiIndex DataFrame + warnings 반환.

    columns: MultiIndex (ticker, field), field ∈ {Open, High, Low, Close, Volume}
    index: DatetimeIndex tz-naive
    """
    warns: list[str] = []
    if not tickers:
        return pd.DataFrame(), warns

    to_fetch = [t for t in tickers if not _is_cached(t, start, end)]
    if to_fetch:
        warns.extend(_fetch_and_store(to_fetch, start, end))

    return _read_ohlcv(tickers, start, end, warns)


def fetch_index(
    symbol: str,
    start: date,
    end: date,
) -> pd.Series:
    """시장 지수(SPY, ^KS11 등) 종가 시계열 반환 (tz-naive)."""
    if not _is_cached(symbol, start, end):
        _fetch_and_store([symbol], start, end)
    return _read_index(symbol, start, end)


# ── 내부 함수 ─────────────────────────────────────────────────────────────────

def _is_cached(ticker: str, start: date, end: date) -> bool:
    """prices_cache에 [start, end] 구간이 커버되어 있으면 True.

    yfinance exclusive-end 및 비영업일로 인해 실제 저장 날짜가
    요청 날짜와 최대 5일 차이날 수 있으므로 _TOLERANCE 허용.
    """
    cached = repo.get_ohlcv_range(ticker)
    if not cached:
        return False
    min_date, max_date = cached
    return min_date <= start + _TOLERANCE and max_date >= end - _TOLERANCE


def _fetch_and_store(tickers: list[str], start: date, end: date) -> list[str]:
    """yfinance로 데이터 다운로드 후 prices_cache에 저장. warnings 반환."""
    warns: list[str] = []
    try:
        raw = yf.download(
            tickers,
            start=str(start),
            end=str(end),
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )
    except Exception as e:
        warns.append(f"yfinance fetch 실패 ({tickers}): {e}")
        return warns

    if raw.empty:
        for t in tickers:
            warns.append(f"{t}: 데이터 없음")
        return warns

    if raw.index.tz is not None:
        raw.index = raw.index.tz_convert(None)

    # 단일 티커는 MultiIndex 없이 반환됨 → 수동 변환
    if not isinstance(raw.columns, pd.MultiIndex):
        cols = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
        raw.columns = cols
        keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
        raw = raw[keep]
        raw.columns = pd.MultiIndex.from_tuples([(tickers[0], c) for c in raw.columns])
    else:
        sample = raw.columns[0]
        if sample[0] in ("Open", "High", "Low", "Close", "Volume", "Adj Close"):
            raw = raw.swaplevel(axis=1)
        raw = raw.sort_index(axis=1)

    rows: list[dict] = []
    available = raw.columns.get_level_values(0).unique().tolist()
    for ticker in tickers:
        if ticker not in available:
            warns.append(f"{ticker}: 데이터 없음 — 제외")
            continue
        sub = raw[ticker].dropna(how="all")
        if sub.empty:
            warns.append(f"{ticker}: 구간 내 데이터 없음 — 제외")
            continue
        for dt, row in sub.iterrows():
            rows.append({
                "ticker": ticker,
                "date": dt.date(),
                "open": row.get("Open"),
                "high": row.get("High"),
                "low": row.get("Low"),
                "close": row.get("Close"),
                "volume": int(row.get("Volume") or 0),
            })

    repo.upsert_ohlcv_rows(rows)
    return warns


def _read_ohlcv(
    tickers: list[str],
    start: date,
    end: date,
    warns: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """prices_cache에서 읽어 MultiIndex(ticker, field) DataFrame 반환."""
    frames: dict[str, pd.DataFrame] = {}
    with repo.session() as s:
        for ticker in tickers:
            rows = s.execute(text("""
                SELECT date, open, high, low, close, volume
                FROM prices_cache
                WHERE ticker = :ticker AND date >= :start AND date <= :end
                ORDER BY date
            """), {"ticker": ticker, "start": start, "end": end}).fetchall()

            if not rows:
                warns.append(f"{ticker}: 캐시에 데이터 없음 — 백테스트에서 제외")
                continue

            idx = pd.to_datetime([r[0] for r in rows])
            frames[ticker] = pd.DataFrame({
                "Open":   [r[1] for r in rows],
                "High":   [r[2] for r in rows],
                "Low":    [r[3] for r in rows],
                "Close":  [r[4] for r in rows],
                "Volume": [r[5] for r in rows],
            }, index=idx)

    if not frames:
        return pd.DataFrame(), warns

    result = pd.concat(frames, axis=1)  # columns: (ticker, field)
    result.index.name = None
    return result.dropna(how="all"), warns


def _read_index(symbol: str, start: date, end: date) -> pd.Series:
    """prices_cache에서 지수 종가 시계열 반환."""
    with repo.session() as s:
        rows = s.execute(text("""
            SELECT date, close FROM prices_cache
            WHERE ticker = :ticker AND date >= :start AND date <= :end
            ORDER BY date
        """), {"ticker": symbol, "start": start, "end": end}).fetchall()

    if not rows:
        log.warning("인덱스 캐시 없음: %s (%s ~ %s)", symbol, start, end)
        return pd.Series(dtype=float, name=symbol)

    return pd.Series(
        [r[1] for r in rows],
        index=pd.to_datetime([r[0] for r in rows]),
        name=symbol,
    )
