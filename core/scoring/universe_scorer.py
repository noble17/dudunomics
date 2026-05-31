"""core/scoring/universe_scorer.py — 유니버스 배치 스코어링 오케스트레이터.

실행 흐름:
1. 유니버스 티커 목록 취득
2. OHLCV 캐시 갱신 (price_momentum, technical 계산용)
3. 확장 펀더멘탈 페치 (valuation, quality, eps 계산용)
4. 5팩터 raw 값 계산
5. 각 팩터를 유니버스 내 백분위(0~1)로 변환
6. DuckDB quant_scores upsert
"""
from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from core.data.universe_provider import get_tickers
from core.data.fundamentals_extended import fetch_extended, ExtendedSnapshot
from core.data.ohlcv_cache import fetch_ohlcv
from core.factors.price_momentum import PriceMomentumFactor
from core.factors.forward_eps_momentum import ForwardEpsMomentumFactor
from core.factors.quality import QualityFactor
from core.factors.technical import TechnicalFactor
from core.factors.valuation import compute_valuation_zscore
from core.data.finviz_screener import fetch_finviz_bulk
import core.repository as repo

log = logging.getLogger(__name__)


def _sync_quarterly_korean(tickers: list[str], bs_universe: str | None = None) -> None:
    """국내 종목 전용 분기 재무 sync (Naver). 해외는 Finviz bulk로 대체."""
    import core.batch_state as _bs
    from core.data.naver_quarterly import fetch_naver_quarterly as _fetch

    total = len(tickers)
    latest_in_db = repo.get_latest_quarterly_period(tickers)
    rows_to_upsert: list[dict] = []
    for i, ticker in enumerate(tickers, 1):
        if bs_universe:
            _bs.update(bs_universe, f"분기 재무 동기화 중 ({i}/{total})", i)
        fetched = _fetch(ticker)
        if not fetched:
            continue
        api_latest = fetched[0]["period"]
        db_latest = latest_in_db.get(ticker)
        if db_latest and db_latest >= api_latest:
            continue
        rows_to_upsert.extend(fetched)
    if rows_to_upsert:
        repo.upsert_quarterly_financials(rows_to_upsert)
        log.info("[quarterly sync] %d행 upsert (korean)", len(rows_to_upsert))


def _compute_yoy_eps_momentum(q_rows: list[dict]) -> float:
    """최근 확정 분기 EPS vs 전년 동기 EPS → YoY 성장률. q_rows는 period 내림차순."""
    if len(q_rows) < 5:
        return 0.0
    by_period = {r["period"]: r for r in q_rows}
    recent_period = q_rows[0]["period"]
    year = int(recent_period[:4])
    q    = recent_period[4:]
    yoy_period = f"{year - 1}{q}"
    recent_eps = q_rows[0].get("eps")
    yoy_row    = by_period.get(yoy_period)
    yoy_eps    = yoy_row.get("eps") if yoy_row else None
    if recent_eps is None or yoy_eps is None or yoy_eps == 0:
        return 0.0
    return (recent_eps - yoy_eps) / abs(yoy_eps)


def _percentile_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
    """유니버스 내 백분위 순위(0~1). ascending=False이면 낮을수록 높은 점수."""
    clean = series.dropna()
    if clean.empty:
        return pd.Series(dtype=float)
    ranked = clean.rank(pct=True, ascending=ascending)
    return ranked.reindex(series.index)


def run_batch(universe: str = "sp500") -> dict:
    """전체 유니버스 배치 스코어링 실행. 완료 후 통계 dict 반환."""
    import core.batch_state as bs

    today = date.today()
    log.info("[Universe Scorer] 시작: %s %s", universe, today)

    # 1. 유니버스 티커 목록
    tickers = get_tickers(universe)
    log.info("[Universe Scorer] 티커 %d개", len(tickers))
    bs.start(universe, len(tickers))

    # 2. OHLCV 캐시 갱신 (1년치 — momentum 12M 계산 필요)
    start_ohlcv = today - timedelta(days=380)
    log.info("[Universe Scorer] OHLCV 갱신 중...")
    bs.update(universe, "주가 데이터 캐시 갱신 중", 0)
    _, warns = fetch_ohlcv(tickers, start_ohlcv, today)
    if warns:
        log.warning("OHLCV 경고 %d건: %s...", len(warns), warns[:3])

    # 3. 확장 펀더멘탈 페치
    log.info("[Universe Scorer] 펀더멘탈 페치 중...")
    bs.update(universe, "펀더멘탈 페치 중 (가장 오래 걸림)", 0)
    def _progress(done: int, total: int) -> None:
        bs.update(universe, f"펀더멘탈 페치 중 ({done}/{total})", done)
    snaps: list[ExtendedSnapshot] = fetch_extended(tickers, max_workers=1, progress_callback=_progress)
    snap_map: dict[str, ExtendedSnapshot] = {s.ticker: s for s in snaps}
    # 3b. 분기 재무 sync: 한국은 Naver, 해외는 Finviz bulk
    is_korean = universe in ("kospi200", "kosdaq150")
    if is_korean:
        log.info("[Universe Scorer] 분기 재무 sync 중 (Naver)...")
        _sync_quarterly_korean(tickers, bs_universe=universe)

    # 3c. Finviz bulk — 해외 유니버스 EPS Q/Q 일괄 수집
    _FINVIZ_INDEX_MAP = {"sp500": "idx_sp500", "nasdaq100": "idx_ndx100"}
    finviz_bulk_data: dict[str, dict] = {}
    if not is_korean and universe in _FINVIZ_INDEX_MAP:
        log.info("[Universe Scorer] Finviz bulk 수집 중...")
        bs.update(universe, "Finviz bulk 수집 중", 0)
        finviz_bulk_data = fetch_finviz_bulk(_FINVIZ_INDEX_MAP[universe])

    bs.update(universe, "팩터 계산 중", len(snaps))

    # 4. 팩터별 raw 값 계산
    log.info("[Universe Scorer] 팩터 계산 중...")

    # 4a. Price Momentum
    momentum_factor = PriceMomentumFactor()
    raw_momentum: pd.Series = momentum_factor.compute(tickers, today)

    # 4c. Valuation raw (EV/EBITDA + PER — Winsorize + Z-score)
    # forward_pe 없는 국내 종목은 trailing_pe 폴백 (Naver는 forward PE 미제공)
    raw_fwd_pe = pd.Series({
        t: (snap_map[t].forward_pe if snap_map[t].forward_pe is not None else snap_map[t].trailing_pe)
        for t in tickers if t in snap_map
    })
    raw_ev_ebitda = pd.Series({t: snap_map[t].ev_ebitda for t in tickers if t in snap_map})

    raw_valuation = compute_valuation_zscore(
        raw_ev_ebitda.dropna(),
        raw_fwd_pe.dropna(),
    ).reindex(tickers)

    # 4d. Quality — quarterly_financials 일괄 조회 후 최신 분기 ROE/부채비율 사용
    quarterly_bulk = repo.get_quarterly_bulk(tickers, n=8)
    quarterly_map: dict[str, dict] = {
        t: rows[0] for t, rows in quarterly_bulk.items() if rows
    }

    raw_quality_vals: dict[str, float] = {}
    for ticker in tickers:
        q = quarterly_map.get(ticker)
        if q and (q.get("roe") is not None or q.get("debt_ratio") is not None):
            raw_quality_vals[ticker] = QualityFactor.score(q.get("roe"), q.get("debt_ratio"))
        else:
            snap = snap_map.get(ticker)
            if snap:
                raw_quality_vals[ticker] = QualityFactor.score(snap.roe, snap.debt_to_equity)
            else:
                raw_quality_vals[ticker] = math.nan
    raw_quality = pd.Series(raw_quality_vals)

    # 4b. EPS Momentum — quarterly YoY 성장률 (quarterly 없으면 forward_eps 리비전 fallback)
    eps_factor = ForwardEpsMomentumFactor()
    fwd_eps_momentum: pd.Series = eps_factor.compute(tickers, today)

    yoy_scores: dict[str, float] = {}
    for ticker in tickers:
        # 해외: Finviz bulk EPS Q/Q 우선
        if not is_korean and ticker in finviz_bulk_data:
            v = finviz_bulk_data[ticker].get("eps_qq")
            yoy_scores[ticker] = float(v) if v is not None else 0.0
            continue
        # 국내: quarterly_financials YoY 우선
        q_rows = quarterly_bulk.get(ticker, [])
        if len(q_rows) >= 5:
            yoy_scores[ticker] = _compute_yoy_eps_momentum(q_rows)
        else:
            yoy_scores[ticker] = float(fwd_eps_momentum.get(ticker, 0.0) or 0.0)
    raw_eps = pd.Series(yoy_scores)

    # 4e. Technical (RSI + MA200) — ThreadPool으로 병렬 계산
    log.info("[Universe Scorer] 기술적 지표 계산 중 (병렬)...")
    tech_raw: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(TechnicalFactor.compute_raw, t, today): t for t in tickers}
        for future in as_completed(futures):
            t = futures[future]
            try:
                tech_raw[t] = future.result()
            except Exception as e:
                log.warning("기술 지표 실패 (%s): %s", t, e)
                tech_raw[t] = {"rsi": math.nan, "above_ma200": False}

    raw_rsi = pd.Series({t: tech_raw[t]["rsi"] for t in tickers})
    above_ma200 = {t: tech_raw[t]["above_ma200"] for t in tickers}

    # 4f. Technical composite: RSI 백분위 + MA200
    rsi_pct = _percentile_rank(raw_rsi, ascending=True)
    ma200_s = pd.Series({t: 1.0 if above_ma200[t] else 0.0 for t in tickers})
    raw_technical = (0.6 * ma200_s + 0.4 * rsi_pct.reindex(tickers, fill_value=0.5))

    # 5. 백분위 변환
    pct_momentum     = _percentile_rank(raw_momentum,  ascending=True)
    pct_valuation    = _percentile_rank(raw_valuation, ascending=False)  # 낮을수록 좋음
    pct_eps          = _percentile_rank(raw_eps,       ascending=True)
    pct_quality      = _percentile_rank(raw_quality,   ascending=True)
    pct_technical    = _percentile_rank(raw_technical, ascending=True)

    # 6. DB upsert
    rows: list[dict] = []
    for ticker in tickers:
        snap = snap_map.get(ticker)
        rows.append({
            "ticker": ticker,
            "universe": universe,
            "as_of": today,
            "pct_momentum":     _safe_float(pct_momentum.get(ticker)),
            "pct_valuation":    _safe_float(pct_valuation.get(ticker)),
            "pct_eps_momentum": _safe_float(pct_eps.get(ticker)),
            "pct_quality":      _safe_float(pct_quality.get(ticker)),
            "pct_technical":    _safe_float(pct_technical.get(ticker)),
            "raw_momentum":     _safe_float(raw_momentum.get(ticker)),
            "raw_fwd_pe":       snap.forward_pe if snap else None,
            "raw_pbr":          snap.pbr if snap else None,
            "raw_psr":          snap.psr if snap else None,
            "raw_trailing_pe":  snap.trailing_pe if snap else None,
            "raw_eps_ttm":      snap.eps_ttm if snap else None,
            "raw_fwd_eps":      snap.forward_eps if snap else None,
            "raw_roe":          (quarterly_map[ticker]["roe"] if ticker in quarterly_map and quarterly_map[ticker].get("roe") is not None
                                 else snap.roe if snap else None),
            "raw_debt_ratio":   (quarterly_map[ticker]["debt_ratio"] / 100.0 if ticker in quarterly_map and quarterly_map[ticker].get("debt_ratio") is not None
                                 else (snap.debt_to_equity / 100.0) if (snap and snap.debt_to_equity) else None),
            "raw_rsi":          _safe_float(raw_rsi.get(ticker)),
            "above_ma200":      bool(above_ma200.get(ticker, False)),
            "cfo_positive":     bool(snap.operating_cashflow and snap.operating_cashflow > 0) if snap else False,
            "company_name":     snap.company_name if snap else None,
            "raw_ev_ebitda":    snap.ev_ebitda if snap else None,
            "raw_peg":          snap.peg if snap else None,
            "raw_fcf_yield":    snap.fcf_yield if snap else None,
            "raw_eps_momentum": _safe_float(raw_eps.get(ticker)),
            "negative_book_value": bool(snap.negative_book_value) if snap else False,
            "sector":           snap.sector if snap else None,
            "industry":         snap.industry if snap else None,
        })

    bs.update(universe, "DB 저장 중", len(tickers))
    repo.upsert_quant_scores(rows)
    bs.finish(universe, len(rows))
    log.info("[Universe Scorer] 완료: %d행 upsert", len(rows))
    return {"universe": universe, "as_of": str(today), "count": len(rows)}


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None
