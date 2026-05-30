"""OHLCV DuckDB 캐시 레이어.

fetch_ohlcv / fetch_index 는 DB 우선 조회 → 캐시 미스 시 fetch 후 저장.
우선순위: KIS API → FDR (국내 fallback) / yfinance (해외 fallback)
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import text

from core import repository as repo
from core.ids import is_domestic

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


def _fetch_yfinance(ticker: str, start: date, end: date) -> pd.DataFrame:
    """yfinance fallback — 해외 종목 단건. bulk 경로가 없을 때 사용."""
    import yfinance as yf
    from core.data.yf_session import get_session
    t = yf.Ticker(ticker, session=get_session())
    df = t.history(start=str(start), end=str(end), auto_adjust=True)
    if df.empty:
        return df
    df.index = df.index.tz_localize(None) if df.index.tz else df.index
    return df[[c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]]


def _fetch_yfinance_bulk(tickers: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    """여러 해외 종목을 yf.download() 단일 호출로 페치.

    HTTP 커넥션 1개로 수백 종목 처리 → IP 차단 방지.
    threads=False로 yfinance 내부 병렬 요청 비활성화.
    """
    if not tickers:
        return {}

    log.warning("yf bulk fallback activated for %d tickers: %s...", len(tickers), tickers[:3])

    import yfinance as yf
    from core.data.yf_session import get_session
    # yf.download는 직접 session 파라미터를 지원하지 않으므로 shared session에 주입
    yf.shared._requests_session = get_session()

    log.info("[ohlcv] bulk download %d개 종목 (%s ~ %s)", len(tickers), start, end)
    raw = yf.download(
        tickers,
        start=str(start),
        end=str(end),
        auto_adjust=True,
        group_by="ticker",
        threads=False,
        progress=False,
    )

    if raw.empty:
        return {}

    result: dict[str, pd.DataFrame] = {}
    cols = ["Open", "High", "Low", "Close", "Volume"]

    if len(tickers) == 1:
        # 단일 종목이면 MultiIndex 없이 반환됨
        df = raw.copy()
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        available = [c for c in cols if c in df.columns]
        if available:
            result[tickers[0]] = df[available].dropna(how="all")
    else:
        for ticker in tickers:
            if ticker not in raw.columns.get_level_values(0):
                continue
            df = raw[ticker].copy()
            df.index = df.index.tz_localize(None) if df.index.tz else df.index
            available = [c for c in cols if c in df.columns]
            if available:
                df = df[available].dropna(how="all")
                if not df.empty:
                    result[ticker] = df

    return result


def _fetch_and_store(tickers: list[str], start: date, end: date) -> list[str]:
    """OHLCV 다운로드 후 prices_cache에 저장.

    - 국내 종목: KIS API → FDR fallback (개별)
    - 해외 종목: KIS API (개별) → 실패 종목만 yfinance bulk fallback
    """
    from core.prices.kis import fetch_ohlcv_domestic, fetch_ohlcv_overseas
    from yfinance.exceptions import YFRateLimitError

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

    # ── 해외 종목: KIS 우선 → yfinance fallback ──────────────────────────────
    if not overseas_tickers:
        return warns

    kis_failed: list[str] = []
    for ticker in overseas_tickers:
        df = fetch_ohlcv_overseas(ticker, start, end)
        if df.empty:
            kis_failed.append(ticker)
            continue
        try:
            _store_df(ticker, df)
        except Exception as e:
            warns.append(f"{ticker}: 저장 실패 — {e}")

    if not kis_failed:
        return warns

    # yfinance fallback — KIS 실패 종목만
    try:
        bulk = _fetch_yfinance_bulk(kis_failed, start, end)
    except YFRateLimitError:
        warns.append("해외 bulk: Yahoo Finance 요청 한도 초과. 잠시 후 다시 시도하세요.")
        return warns
    except Exception as e:
        log.warning("bulk download 실패: %s — 개별 재시도", e)
        bulk = {}

    failed = [t for t in kis_failed if t not in bulk]

    for ticker, df in bulk.items():
        try:
            _store_df(ticker, df)
        except Exception as e:
            warns.append(f"{ticker}: 저장 실패 — {e}")

    for ticker in failed:
        try:
            df = _fetch_yfinance(ticker, start, end)
            if df.empty:
                warns.append(f"{ticker}: 데이터 없음")
                continue
            _store_df(ticker, df)
        except YFRateLimitError:
            warns.append(f"{ticker}: Yahoo Finance 요청 한도 초과.")
        except Exception as e:
            warns.append(f"{ticker}: fetch 실패 — {e}")

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
