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
import core.repository as repo

log = logging.getLogger(__name__)


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
    snaps: list[ExtendedSnapshot] = fetch_extended(tickers, max_workers=1)
    snap_map: dict[str, ExtendedSnapshot] = {s.ticker: s for s in snaps}
    bs.update(universe, "팩터 계산 중", len(snaps))

    # 4. 팩터별 raw 값 계산
    log.info("[Universe Scorer] 팩터 계산 중...")

    # 4a. Price Momentum
    momentum_factor = PriceMomentumFactor()
    raw_momentum: pd.Series = momentum_factor.compute(tickers, today)

    # 4b. EPS Momentum
    eps_factor = ForwardEpsMomentumFactor()
    raw_eps: pd.Series = eps_factor.compute(tickers, today)

    # 4c. Valuation raw (PER, PBR — Winsorize + Z-score는 percentile 전에 처리)
    raw_fwd_pe = pd.Series({t: snap_map[t].forward_pe for t in tickers if t in snap_map})
    raw_pbr    = pd.Series({t: snap_map[t].pbr       for t in tickers if t in snap_map})

    from core.factors.valuation import _winsorize_series, _combined_value_zscore
    pe_clean  = raw_fwd_pe.dropna()
    pbr_clean = raw_pbr.dropna()
    if pe_clean.empty or pbr_clean.empty:
        raw_valuation = pd.Series({t: math.nan for t in tickers})
    else:
        w_pe  = _winsorize_series(pe_clean)
        w_pbr = _winsorize_series(pbr_clean)
        common = w_pe.index.intersection(w_pbr.index)
        if common.empty:
            raw_valuation = pd.Series({t: math.nan for t in tickers})
        else:
            raw_valuation = _combined_value_zscore(w_pe[common], w_pbr[common]).reindex(tickers)

    # 4d. Quality
    raw_quality_vals: dict[str, float] = {}
    for ticker in tickers:
        snap = snap_map.get(ticker)
        if snap:
            raw_quality_vals[ticker] = QualityFactor.score(snap.roe, snap.debt_to_equity)
        else:
            raw_quality_vals[ticker] = math.nan
    raw_quality = pd.Series(raw_quality_vals)

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
            "raw_roe":          snap.roe if snap else None,
            "raw_debt_ratio":   (snap.debt_to_equity / 100.0) if (snap and snap.debt_to_equity) else None,
            "raw_rsi":          _safe_float(raw_rsi.get(ticker)),
            "above_ma200":      bool(above_ma200.get(ticker, False)),
            "cfo_positive":     bool(snap.operating_cashflow and snap.operating_cashflow > 0) if snap else False,
            "company_name":     snap.company_name if snap else None,
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
