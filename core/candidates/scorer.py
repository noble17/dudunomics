"""후보 발굴용 점수 생성.

기존 성장주 배치가 만든 quant_scores를 후보 테이블로 정규화한다.
ChoiceStock 공개 데이터는 관심종목으로 승격된 뒤 별도 작업에서만 수집한다.
"""
from __future__ import annotations

import json
from datetime import date
from statistics import mean
from typing import Iterable

import core.repository as repo


US_UNIVERSES = ("sp500", "nasdaq100", "russell1000")
KR_UNIVERSES = ("kospi200", "kosdaq150")
TECH_KEYWORDS = (
    "technology",
    "communication",
    "semiconductor",
    "software",
    "internet",
    "data",
    "electronic",
    "cloud",
    "computer",
    "hardware",
)


def refresh_candidate_scores(region: str = "all") -> dict:
    regions = ("US", "KR") if region.lower() == "all" else (region.upper(),)
    result = {"regions": 0, "rows": 0}
    for item in regions:
        if item == "US":
            rows = build_candidate_scores("US", US_UNIVERSES)
        elif item == "KR":
            rows = build_candidate_scores("KR", KR_UNIVERSES)
        else:
            continue
        repo.upsert_candidate_scores(rows)
        result["regions"] += 1
        result["rows"] += len(rows)
    return result


def build_candidate_scores(region: str, universes: Iterable[str]) -> list[dict]:
    by_ticker: dict[str, dict] = {}
    for universe in universes:
        for row in repo.get_latest_quant_scores(universe):
            ticker = str(row["ticker"]).upper()
            candidate = _candidate_from_quant(row, region, universe)
            existing = by_ticker.get(ticker)
            if not existing or (candidate["candidate_score"] or 0) > (existing["candidate_score"] or 0):
                by_ticker[ticker] = candidate
            source_universes = set((by_ticker[ticker]["raw_json"] or {}).get("source_universes", []))
            source_universes.add(universe)
            by_ticker[ticker]["raw_json"]["source_universes"] = sorted(source_universes)

    ranked = sorted(
        by_ticker.values(),
        key=lambda row: (row["candidate_score"] is not None, row["candidate_score"] or -1),
        reverse=True,
    )
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx
    return ranked


def _candidate_from_quant(row: dict, region: str, universe: str) -> dict:
    growth = _first_score(row, "growth_composite", "pct_growth", "pct_eps_momentum")
    quality = _avg_score(row, "pct_quality", "pct_profitability", "pct_cashflow", "pct_stability")
    valuation = _first_score(row, "pct_valuation")
    momentum = _first_score(row, "pct_momentum")
    timing = _first_score(row, "pct_technical")
    liquidity = _liquidity_score(row)
    candidate = _weighted_score({
        "growth": (growth, 0.32),
        "quality": (quality, 0.22),
        "valuation": (valuation, 0.16),
        "momentum": (momentum, 0.16),
        "timing": (timing, 0.10),
        "liquidity": (liquidity, 0.04),
    })
    market = "KR" if region == "KR" else "US"
    return {
        "as_of": row.get("as_of") or date.today(),
        "region": region,
        "universe_group": region.lower(),
        "ticker": str(row["ticker"]).upper(),
        "name": row.get("company_name"),
        "market": market,
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "candidate_score": candidate,
        "growth_score": growth,
        "quality_score": quality,
        "valuation_score": valuation,
        "momentum_score": momentum,
        "timing_score": timing,
        "liquidity_score": liquidity,
        "rank": None,
        "raw_json": {
            "source_universe": universe,
            "source_universes": [universe],
            "raw_market_cap_usd_m": row.get("raw_market_cap_usd_m"),
            "raw_market_cap_krw": row.get("raw_market_cap_krw"),
            "raw_fwd_rev_growth": row.get("raw_fwd_rev_growth"),
            "raw_fwd_eps_growth": row.get("raw_fwd_eps_growth"),
            "raw_peg": row.get("raw_peg"),
            "raw_fwd_pe": row.get("raw_fwd_pe"),
            "raw_psr": row.get("raw_psr"),
            "raw_roe": row.get("raw_roe"),
            "raw_rsi": row.get("raw_rsi"),
            "above_ma200": row.get("above_ma200"),
            "is_tech": _is_tech(row),
        },
    }


def _first_score(row: dict, *keys: str) -> float | None:
    for key in keys:
        value = _score_value(row.get(key))
        if value is not None:
            return value
    return None


def _avg_score(row: dict, *keys: str) -> float | None:
    values = [_score_value(row.get(key)) for key in keys]
    values = [value for value in values if value is not None]
    return round(mean(values), 2) if values else None


def _score_value(value) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    if -1 <= number <= 1:
        number *= 100
    return round(max(0, min(number, 100)), 2)


def _weighted_score(parts: dict[str, tuple[float | None, float]]) -> float | None:
    total = 0.0
    weight = 0.0
    for value, item_weight in parts.values():
        if value is None:
            continue
        total += value * item_weight
        weight += item_weight
    if weight == 0:
        return None
    return round(total / weight, 2)


def _liquidity_score(row: dict) -> float | None:
    market_cap = row.get("raw_market_cap_usd_m") or row.get("raw_market_cap_krw")
    try:
        value = float(market_cap)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    if value >= 100_000:
        return 100.0
    if value >= 10_000:
        return 85.0
    if value >= 2_000:
        return 70.0
    if value >= 500:
        return 55.0
    return 35.0


def _is_tech(row: dict) -> bool:
    haystack = f"{row.get('sector') or ''} {row.get('industry') or ''}".lower()
    return any(keyword in haystack for keyword in TECH_KEYWORDS)


def decode_raw_json(value) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}
