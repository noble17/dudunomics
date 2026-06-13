"""OHLCV DuckDB 캐시 레이어.

fetch_ohlcv / fetch_index 는 DB 우선 조회 → 캐시 미스 시 fetch 후 저장.
우선순위: KIS API → FDR (국내 fallback). 해외 OHLCV는 KIS만 사용한다.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import text

from core import repository as repo
from core.ids import is_domestic
from core.prices.selection import prefer_toss_market_data

log = logging.getLogger(__name__)

# 비영업일 허용 오차 (일수)
_TOLERANCE = timedelta(days=5)


def fetch_ohlcv(
    tickers: list[str],
    start: date,
    end: date,
    *,
    cache_only: bool = False,
    force: bool = False,
) -> tuple[pd.DataFrame, list[str]]:
    """tickers OHLCV MultiIndex DataFrame + warnings 반환.

    cache_only=True: DB 캐시만 조회, 네트워크 fetch 하지 않음.
    force=True: 캐시 상태 무관하게 강제 재페치 (데이터 갱신용).
    """
    warns: list[str] = []
    if not tickers:
        return pd.DataFrame(), warns

    if not cache_only:
        to_fetch = tickers if force else [t for t in tickers if not _is_cached(t, start, end)]
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

    비영업일로 인해 실제 저장 날짜가 요청 날짜와 최대 5일 차이날 수
    있으므로 _TOLERANCE 허용.
    """
    cached = repo.get_ohlcv_range(ticker)
    if not cached:
        return False
    min_date, max_date = cached
    return min_date <= start + _TOLERANCE and max_date >= end - _TOLERANCE


def _store_df(ticker: str, df: pd.DataFrame) -> None:
    """OHLCV DataFrame을 prices_cache에 저장."""
    rows = [
        {"ticker": ticker, "date": dt.date() if hasattr(dt, "date") else dt,
         "open": float(row.get("Open") or 0), "high": float(row.get("High") or 0),
         "low": float(row.get("Low") or 0), "close": float(row.get("Close") or 0),
         "volume": int(row.get("Volume") or 0)}
        for dt, row in df.iterrows()
    ]
    repo.upsert_ohlcv_rows(rows)


def _covers_requested_start(df: pd.DataFrame, start: date) -> bool:
    """반환 데이터가 요청 시작일을 충분히 커버하는지 확인."""
    if df.empty:
        return False
    min_idx = df.index.min()
    min_date = min_idx.date() if hasattr(min_idx, "date") else min_idx
    return min_date <= start + _TOLERANCE


def _fetch_fdr(ticker: str, start: date, end: date) -> pd.DataFrame:
    """FDR fallback — KRX 종목 전용."""
    import FinanceDataReader as fdr
    code = ticker.split(".")[0]
    df = fdr.DataReader(code, start=str(start), end=str(end))
    if df.empty:
        return df
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.columns = [c.capitalize() if c.lower() in ("open", "high", "low", "close", "volume") else c for c in df.columns]
    return df[[c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]]


def _fetch_and_store(tickers: list[str], start: date, end: date) -> list[str]:
    """OHLCV 다운로드 후 prices_cache에 저장.

    - 국내 종목: KIS API → FDR fallback (개별)
    - 해외 종목: KIS API only
    """
    if prefer_toss_market_data():
        return _fetch_and_store_toss(tickers, start, end)

    from core.prices.kis import fetch_ohlcv_domestic, fetch_ohlcv_overseas

    warns: list[str] = []
    domestic_tickers = [t for t in tickers if is_domestic(t)]
    overseas_tickers = [t for t in tickers if not is_domestic(t)]

    # ── 국내 종목: 개별 KIS/FDR ──────────────────────────────────────────────
    for ticker in domestic_tickers:
        df: pd.DataFrame = pd.DataFrame()
        try:
            df = fetch_ohlcv_domestic(ticker, start, end)
        except Exception as e:
            log.warning("KIS OHLCV 실패 (%s): %s — FDR fallback", ticker, e)

        if df.empty:
            try:
                df = _fetch_fdr(ticker, start, end)
            except Exception as e:
                warns.append(f"{ticker}: fetch 실패 — {e}")
                continue
            if df.empty:
                warns.append(f"{ticker}: 데이터 없음")
                continue

        try:
            _store_df(ticker, df)
        except Exception as e:
            warns.append(f"{ticker}: 저장 실패 — {e}")

    # ── 해외 종목: KIS only ─────────────────────────────────────────────────
    if not overseas_tickers:
        return warns

    for ticker in overseas_tickers:
        df = fetch_ohlcv_overseas(ticker, start, end)
        if df.empty:
            warns.append(f"{ticker}: KIS 해외 OHLCV 데이터 없음")
            continue
        try:
            _store_df(ticker, df)
        except Exception as e:
            warns.append(f"{ticker}: 저장 실패 — {e}")
        if not _covers_requested_start(df, start):
            warns.append(f"{ticker}: KIS 데이터가 요청 구간보다 짧습니다.")

    return warns


def _fetch_and_store_toss(tickers: list[str], start: date, end: date) -> list[str]:
    from core.prices.toss import fetch_ohlcv_daily

    warns: list[str] = []
    for ticker in tickers:
        df = fetch_ohlcv_daily(ticker, start, end)
        if df.empty:
            warns.append(f"{ticker}: Toss OHLCV 데이터 없음")
            continue
        try:
            _store_df(ticker, df)
        except Exception as e:
            warns.append(f"{ticker}: 저장 실패 — {e}")
        if not _covers_requested_start(df, start):
            warns.append(f"{ticker}: Toss 데이터가 요청 구간보다 짧습니다.")
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
