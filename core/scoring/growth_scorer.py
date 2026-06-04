"""성장주 4팩터 스코어링과 Top10 하드 필터."""
from __future__ import annotations

import math
from typing import Iterable

import pandas as pd


_MIN_SECTOR_SIZE = 5
_FACTOR_COLUMNS = ("pct_growth", "pct_profitability", "pct_cashflow", "pct_stability")
_FACTOR_WEIGHTS = {
    "pct_growth": 0.4,
    "pct_profitability": 0.3,
    "pct_cashflow": 0.2,
    "pct_stability": 0.1,
}


def percentile_rank_by_sector(
    values: pd.Series,
    sectors: pd.Series,
    *,
    ascending: bool = True,
) -> pd.Series:
    """섹터 내 백분위. 표본 5개 미만 또는 섹터 없음은 유니버스 백분위."""
    values = values.astype(float)
    global_rank = values.rank(pct=True, ascending=ascending)
    result = global_rank.copy()
    sector_values = sectors.reindex(values.index)

    for sector, indices in sector_values.dropna().groupby(sector_values.dropna()).groups.items():
        if len(indices) < _MIN_SECTOR_SIZE:
            continue
        result.loc[indices] = values.loc[indices].rank(pct=True, ascending=ascending)
    return result


def compute_growth_scores(raw: pd.DataFrame) -> pd.DataFrame:
    """정규화된 raw 지표 DataFrame에 성장주 팩터 점수와 coverage를 추가한다."""
    out = raw.copy()
    sectors = out.get("sector", pd.Series(index=out.index, dtype=object))

    sales_growth = _col(out, "sales_growth")
    eps_growth = _col(out, "eps_growth")
    growth_raw = pd.concat([sales_growth, eps_growth], axis=1).mean(axis=1, skipna=False)

    profitability_parts = [
        percentile_rank_by_sector(_col(out, "roe"), sectors),
        percentile_rank_by_sector(_col(out, "roic"), sectors),
        percentile_rank_by_sector(_col(out, "operating_margin"), sectors),
    ]
    cashflow_raw = _col(out, "fcf_yield").where(_col(out, "cfo_positive").fillna(False).astype(bool))
    stability_parts = [
        percentile_rank_by_sector(_col(out, "debt_to_equity"), sectors, ascending=False),
        percentile_rank_by_sector(_col(out, "current_ratio"), sectors),
    ]

    out["pct_growth"] = percentile_rank_by_sector(growth_raw, sectors)
    out["pct_profitability"] = pd.concat(profitability_parts, axis=1).mean(axis=1, skipna=False)
    out["pct_cashflow"] = percentile_rank_by_sector(cashflow_raw, sectors)
    out["pct_stability"] = pd.concat(stability_parts, axis=1).mean(axis=1, skipna=False)

    factor_count = out[list(_FACTOR_COLUMNS)].notna().sum(axis=1)
    out["growth_composite"] = sum(out[col] * weight for col, weight in _FACTOR_WEIGHTS.items()) * 100
    out.loc[factor_count < 3, "growth_composite"] = math.nan
    out["data_coverage"] = [
        {
            "factor_count": int(count),
            "missing_factors": [col for col in _FACTOR_COLUMNS if pd.isna(out.at[idx, col])],
        }
        for idx, count in factor_count.items()
    ]
    return out


def filter_growth_top(
    scores: pd.DataFrame,
    *,
    market: str,
    cap: str | None = None,
    sector: str | None = None,
    limit: int = 10,
) -> pd.DataFrame:
    """성장주 하드 필터 통과 종목을 점수순으로 반환한다."""
    if scores.empty:
        return scores.copy()
    df = scores.copy()
    required = (
        "debt_to_equity",
        "fcf_yield",
        "operating_cashflow",
        "current_ratio",
        "operating_margin",
        "roe",
        "roic",
        "growth_composite",
    )
    df = df.dropna(subset=list(required))
    if df.empty:
        return df

    sector_avg_margin = df.groupby("sector", dropna=False)["operating_margin"].transform("mean")
    sector_median_roe = df.groupby("sector", dropna=False)["roe"].transform("median")
    sector_median_roic = df.groupby("sector", dropna=False)["roic"].transform("median")
    df = df[
        (df["debt_to_equity"] < 1.0)
        & (df["fcf_yield"] > 0)
        & (df["operating_cashflow"] > 0)
        & (df["current_ratio"] > 1.5)
        & (df["operating_margin"] >= sector_avg_margin)
        & (df["roe"] >= sector_median_roe)
        & (df["roic"] >= sector_median_roic)
    ]
    if sector:
        df = df[df["sector"] == sector]
    if cap:
        if df.empty:
            return df
        df = df[df.apply(lambda row: market_cap_bucket(row, market) == cap.lower(), axis=1)]
    return df.sort_values("growth_composite", ascending=False).head(max(1, min(limit, 100)))


def market_cap_bucket(row: pd.Series, market: str) -> str | None:
    if market.upper() == "KR":
        cap = _number(row.get("market_cap_krw"))
        if cap is None:
            return None
        if cap >= 10_000_000_000_000:
            return "large"
        if cap >= 1_000_000_000_000:
            return "mid"
        return "small"

    cap = _number(row.get("market_cap_usd_m"))
    if cap is None:
        return None
    if cap >= 10_000:
        return "large"
    if cap >= 2_000:
        return "mid"
    return "small"


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    if name not in df:
        return pd.Series(index=df.index, dtype=float)
    return pd.to_numeric(df[name], errors="coerce")


def _number(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)
