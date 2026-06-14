from api.routers.candidates import _limit_by_region, _matches_numeric_filters, _rerank_with_weights


def test_rerank_with_custom_weights_changes_order():
    rows = [
        {
            "ticker": "GROW",
            "growth_score": 95,
            "quality_score": 60,
            "valuation_score": 30,
            "momentum_score": 60,
            "timing_score": 60,
            "liquidity_score": 60,
        },
        {
            "ticker": "VALUE",
            "growth_score": 40,
            "quality_score": 60,
            "valuation_score": 95,
            "momentum_score": 60,
            "timing_score": 60,
            "liquidity_score": 60,
        },
    ]

    growth_first = _rerank_with_weights(rows, {
        "growth_score": 100,
        "quality_score": 0,
        "valuation_score": 0,
        "momentum_score": 0,
        "timing_score": 0,
        "liquidity_score": 0,
    })
    value_first = _rerank_with_weights(rows, {
        "growth_score": 0,
        "quality_score": 0,
        "valuation_score": 100,
        "momentum_score": 0,
        "timing_score": 0,
        "liquidity_score": 0,
    })

    assert growth_first[0]["ticker"] == "GROW"
    assert value_first[0]["ticker"] == "VALUE"


def test_numeric_filters_use_available_candidate_snapshot_fields():
    row = {
        "growth_score": 80,
        "quality_score": 75,
        "valuation_score": 60,
        "momentum_score": 70,
        "timing_score": 65,
        "liquidity_score": 90,
        "raw_market_cap": 12_000,
        "raw_forward_pe": 24,
        "raw_peg": 0.8,
        "raw_roe": 18,
        "raw_rsi": 58,
        "above_ma200": True,
        "raw_fwd_eps_growth": 12,
        "raw_fwd_rev_growth": 8,
    }

    assert _matches_numeric_filters(
        row,
        min_growth_score=70,
        min_quality_score=70,
        min_valuation_score=50,
        min_momentum_score=60,
        min_timing_score=60,
        min_liquidity_score=80,
        min_market_cap=10_000,
        max_forward_pe=30,
        max_peg=1,
        min_roe=10,
        max_rsi=70,
        require_above_ma200=True,
        positive_eps_growth=True,
        positive_revenue_growth=True,
    )

    assert not _matches_numeric_filters(
        row,
        min_growth_score=90,
        min_quality_score=None,
        min_valuation_score=None,
        min_momentum_score=None,
        min_timing_score=None,
        min_liquidity_score=None,
        min_market_cap=None,
        max_forward_pe=None,
        max_peg=None,
        min_roe=None,
        max_rsi=None,
        require_above_ma200=False,
        positive_eps_growth=False,
        positive_revenue_growth=False,
    )


def test_all_region_limit_picks_each_source_bucket_once():
    rows = []
    for source in ("russell1000", "nasdaq100", "sp500", "kospi200", "kosdaq150"):
        region = "KR" if source.startswith("kos") else "US"
        for idx in range(12):
            rows.append({
                "ticker": f"{source.upper()}_{idx}",
                "region": region,
                "candidate_score": 100 - idx,
                "source_universe": source,
                "source_universes": [source],
            })
    rows.insert(0, {
        "ticker": "DUP",
        "region": "US",
        "candidate_score": 101,
        "source_universe": "russell1000",
        "source_universes": ["russell1000", "nasdaq100"],
    })

    limited = _limit_by_region(rows, "all", "all", 50)
    tickers = [row["ticker"] for row in limited]

    assert len(limited) == 50
    assert len(tickers) == len(set(tickers))
    assert "DUP" in tickers
