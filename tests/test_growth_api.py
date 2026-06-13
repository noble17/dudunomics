"""tests/test_growth_api.py — 성장주 탐색 API 계약."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import core.repository as repo
import pytest


@pytest.fixture(autouse=True)
def stub_growth_price_provider(monkeypatch):
    import api.routers.growth as growth

    provider = MagicMock()
    provider.get_current_price.side_effect = RuntimeError("quote unavailable")
    monkeypatch.setattr(growth, "_price_provider", provider, raising=False)
    return provider


def _score_row(ticker: str, score: float, **overrides) -> dict:
    row = {
        "ticker": ticker,
        "universe": "sp500",
        "as_of": date.today(),
        "pct_momentum": 0.5,
        "pct_valuation": 0.5,
        "pct_eps_momentum": 0.5,
        "pct_quality": 0.5,
        "pct_technical": 0.5,
        "raw_momentum": 0.1,
        "raw_fwd_pe": 20.0,
        "raw_pbr": 3.0,
        "raw_psr": 4.0,
        "raw_trailing_pe": 22.0,
        "raw_eps_ttm": 5.0,
        "raw_fwd_eps": 6.0,
        "raw_roe": 25.0,
        "raw_debt_ratio": 0.4,
        "raw_rsi": 55.0,
        "above_ma200": True,
        "cfo_positive": True,
        "company_name": ticker,
        "raw_ev_ebitda": 15.0,
        "raw_peg": 0.8,
        "raw_fcf_yield": 0.04,
        "raw_eps_momentum": 0.2,
        "negative_book_value": False,
        "sector": "Technology",
        "industry": "Software",
        "pct_growth": 0.9,
        "pct_profitability": 0.8,
        "pct_cashflow": 0.7,
        "pct_stability": 0.6,
        "growth_composite": score,
        "raw_roic": 0.2,
        "raw_gross_margin": 0.6,
        "raw_oper_margin": 0.3,
        "raw_current_ratio": 2.0,
        "raw_sales_growth": 0.25,
        "raw_rev_yoy": 0.25,
        "raw_market_cap_usd_m": 50_000.0,
        "raw_market_cap_krw": None,
        "raw_fwd_rev_growth": 0.15,
        "raw_fwd_eps_growth": 0.18,
        "raw_operating_cashflow": 1_000.0,
        "data_coverage": {"factor_count": 4, "missing_factors": []},
        "sector_percentile_fallback": False,
    }
    row.update(overrides)
    return row


def _consensus(**overrides) -> dict:
    result = {
        "consensus_status": "ok",
        "consensus_message": "애널리스트 목표주가 컨센서스입니다.",
        "consensus_source": "FMP",
        "retry_after": None,
        "current_price": 200.0,
        "target_mean": 240.0,
        "target_median": 245.0,
        "target_low": 190.0,
        "target_high": 300.0,
        "upside_pct": 20.0,
        "analyst_count": 15,
        "consensus_as_of": "2026-06-01",
        "fallback_used": False,
        "consensus_attempts": [{"source": "FMP", "status": "ok"}],
    }
    result.update(overrides)
    return result


def _store_consensus(ticker: str, **overrides) -> None:
    repo.upsert_price_target_consensus_snapshot(ticker, _consensus(**overrides))


def test_growth_scores_include_rank_delta(client):
    today = date.today()
    repo.upsert_quant_scores([_score_row("AAPL", 91.0)])
    repo.upsert_rank_history([
        {"universe": "sp500", "as_of": today, "ticker": "AAPL", "growth_composite": 91.0, "rank": 2},
    ])

    response = client.get("/api/growth/scores?universe=sp500")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["ticker"] == "AAPL"
    assert body[0]["growth_composite"] == 91.0
    assert body[0]["rank"] == 2
    assert body[0]["data_coverage"]["factor_count"] == 4


def test_growth_scores_convert_non_finite_numbers_to_null(client):
    repo.upsert_quant_scores([
        _score_row(
            "005930.KS",
            float("nan"),
            universe="kospi200",
            pct_growth=float("nan"),
            raw_roic=float("inf"),
        ),
    ])
    stored = repo.get_latest_quant_scores("kospi200")[0]

    response = client.get("/api/growth/scores?universe=kospi200")

    assert stored["growth_composite"] is None
    assert stored["pct_growth"] is None
    assert stored["raw_roic"] is None
    assert response.status_code == 200
    assert response.json()[0]["growth_composite"] is None
    assert response.json()[0]["pct_growth"] is None
    assert response.json()[0]["raw_roic"] is None


def test_growth_top_filters_and_sorts(client):
    repo.upsert_quant_scores([
        _score_row("PASS", 90.0),
        _score_row("NO_FCF", 99.0, raw_fcf_yield=-0.01),
    ])

    response = client.get("/api/growth/top?universe=sp500&cap=large")

    assert response.status_code == 200
    assert [row["ticker"] for row in response.json()] == ["PASS"]


def test_growth_top_filters_by_timing_stage(client):
    repo.upsert_quant_scores([
        _score_row("ALIGNED", 90.0),
        _score_row("UNSUITABLE", 80.0),
    ])

    with patch("api.routers.growth.analyze_timing", side_effect=[
        {
            "status": "watch",
            "aligned": True,
            "pullback": False,
            "pullback_stage": "none",
            "volume_explosion": False,
            "volume_ratio": 1.1,
            "volume_level": "increased",
            "volume_direction": "bullish",
            "rsi_level": "neutral",
            "downgrade_reasons": [{"code": "recent_bearish_volume_spike", "message": "최근 매도 압력", "severity": "downgrade"}],
        },
        {"status": "unsuitable", "aligned": False, "pullback": False, "volume_explosion": False},
    ]):
        response = client.get("/api/growth/top?universe=sp500&signal=aligned")

    assert response.status_code == 200
    assert [row["ticker"] for row in response.json()] == ["ALIGNED"]
    assert response.json()[0]["timing_status"] == "watch"
    assert response.json()[0]["timing_aligned"] is True
    assert response.json()[0]["timing_pullback_stage"] == "none"
    assert response.json()[0]["timing_volume_level"] == "increased"
    assert response.json()[0]["timing_volume_direction"] == "bullish"
    assert response.json()[0]["timing_rsi_level"] == "neutral"
    assert response.json()[0]["timing_downgrade_reasons"][0]["code"] == "recent_bearish_volume_spike"


def test_growth_top_keeps_unknown_card_when_one_timing_analysis_fails(client):
    repo.upsert_quant_scores([
        _score_row("BROKEN", 90.0),
        _score_row("PASS", 80.0),
    ])

    def analyze(ticker):
        if ticker == "BROKEN":
            raise RuntimeError("upstream failed")
        return {"status": "watch", "aligned": True, "pullback": False, "volume_explosion": False}

    with patch("api.routers.growth.analyze_timing", side_effect=analyze):
        response = client.get("/api/growth/top?universe=sp500&signal=all")

    assert response.status_code == 200
    assert [row["ticker"] for row in response.json()] == ["BROKEN", "PASS"]
    assert response.json()[0]["timing_status"] == "unknown"


def test_growth_top_excludes_failed_timing_analysis_from_specific_signal(client):
    repo.upsert_quant_scores([
        _score_row("BROKEN", 90.0),
        _score_row("PASS", 80.0),
    ])

    def analyze(ticker):
        if ticker == "BROKEN":
            raise RuntimeError("upstream failed")
        return {"status": "watch", "aligned": True, "pullback": False, "volume_explosion": False}

    with patch("api.routers.growth.analyze_timing", side_effect=analyze):
        response = client.get("/api/growth/top?universe=sp500&signal=aligned")

    assert response.status_code == 200
    assert [row["ticker"] for row in response.json()] == ["PASS"]


def test_growth_watchlist_add_list_status_and_remove(client):
    repo.upsert_quant_scores([
        _score_row("AAPL", 91.0),
        _score_row("MSFT", 88.0),
    ])

    with patch("api.routers.growth.analyze_timing", return_value={
        "status": "watch",
        "aligned": True,
        "pullback": False,
        "pullback_stage": "none",
        "volume_explosion": False,
    }):
        add_response = client.put("/api/growth/watchlist/AAPL?universe=sp500")
        duplicate_response = client.put("/api/growth/watchlist/aapl?universe=sp500")
        status_response = client.get("/api/growth/watchlist/AAPL?universe=sp500")
        list_response = client.get("/api/growth/watchlist?universe=sp500")
        delete_response = client.delete("/api/growth/watchlist/AAPL?universe=sp500")
        list_after_delete = client.get("/api/growth/watchlist?universe=sp500")

    assert add_response.status_code == 200
    assert add_response.json() == {"ticker": "AAPL", "universe": "sp500", "in_watchlist": True}
    assert duplicate_response.status_code == 200
    assert status_response.json()["in_watchlist"] is True
    assert [row["ticker"] for row in list_response.json()] == ["AAPL"]
    assert list_response.json()[0]["growth_composite"] == 91.0
    assert list_response.json()[0]["timing_status"] == "watch"
    assert delete_response.json() == {"ticker": "AAPL", "universe": "sp500", "in_watchlist": False}
    assert list_after_delete.json() == []


def test_growth_valuation_returns_consensus_metrics(client):
    repo.upsert_quant_scores([_score_row("AAPL", 91.0)])
    _store_consensus("AAPL")

    response = client.get("/api/growth/ticker/aapl/valuation?universe=sp500&refresh_consensus=true")

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert body["peg"] == 0.8
    assert body["forward_revenue_growth"] == 0.15
    assert body["forward_eps_growth"] == 0.18
    assert body["consensus_status"] == "ok"
    assert body["consensus_source"] == "FMP"
    assert body["current_price"] == 200.0
    assert body["target_mean"] == 240.0
    assert body["target_median"] == 245.0
    assert body["target_low"] == 190.0
    assert body["target_high"] == 300.0
    assert body["upside_pct"] == 20.0
    assert body["analyst_count"] == 15
    assert body["consensus_as_of"] == "2026-06-01"
    assert body["fallback_used"] is False
    assert body["consensus_attempts"] == [{"source": "FMP", "status": "ok"}]


def test_growth_valuation_returns_empty_metrics_when_quant_row_is_missing(client):
    response = client.get("/api/growth/ticker/BE/valuation?universe=sp500")

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "BE"
    assert body["peg"] is None
    assert body["forward_pe"] is None
    assert body["psr"] is None
    assert body["score_status"] == "missing"
    assert body["score_message"] == "BE는 sp500 성장주 배치 데이터에 아직 없습니다."
    assert body["missing_reasons"] == [
        "BE 펀더멘털 snapshot이 없습니다.",
        "데이터 보강 작업 또는 종목 hydrate를 먼저 실행해 주세요.",
    ]
    assert body["consensus_status"] == "missing"


def test_growth_valuation_does_not_fetch_fundamentals_on_page_read(client):
    with patch("core.data.price_target_consensus.fetch_price_target_consensus") as fetch_consensus:
        response = client.get("/api/growth/ticker/BE/valuation?universe=sp500")

    assert response.status_code == 200
    body = response.json()
    assert body["score_status"] == "missing"
    assert body["valuation_source"] is None
    assert body["peg"] is None
    assert body["consensus_status"] == "missing"
    fetch_consensus.assert_not_called()


def test_growth_valuation_uses_common_fundamental_snapshot(client):
    repo.upsert_fundamental_snapshot({
        "ticker": "BE",
        "as_of": date(2026, 6, 3),
        "source": "finviz",
        "per": None,
        "pbr": 12.3,
        "psr": 35.1,
        "peg": 0.6,
        "forward_pe": 69.47,
        "trailing_pe": None,
        "forward_eps": 104.03,
        "eps_ttm": None,
        "roe": None,
        "roic": None,
        "debt_ratio": None,
        "current_ratio": None,
        "gross_margin": None,
        "operating_margin": None,
        "revenue_growth": 82.2,
        "eps_growth": None,
        "market_cap": None,
        "raw_json": {},
    })

    _store_consensus("BE")
    response = client.get("/api/growth/ticker/BE/valuation?universe=sp500&refresh_consensus=true")

    assert response.status_code == 200
    body = response.json()
    assert body["score_status"] == "missing"
    assert body["valuation_source"] == "finviz"
    assert body["peg"] == 0.6
    assert body["forward_pe"] == 69.47
    assert body["psr"] == 35.1
    assert body["forward_eps"] == 104.03
    assert body["forward_revenue_growth"] == 82.2


def test_growth_valuation_uses_live_price_for_fmp_upside(client, stub_growth_price_provider):
    repo.upsert_quant_scores([_score_row("AAPL", 91.0)])
    stub_growth_price_provider.get_current_price.side_effect = None
    stub_growth_price_provider.get_current_price.return_value = SimpleNamespace(current=200.0)
    _store_consensus("AAPL", current_price=None, target_mean=240.0, upside_pct=None)

    response = client.get("/api/growth/ticker/AAPL/valuation?universe=sp500&refresh_consensus=true")

    assert response.status_code == 200
    assert response.json()["current_price"] == 200.0
    assert response.json()["upside_pct"] == 20.0


def test_growth_valuation_overrides_kis_report_price_with_live_price(
    client, stub_growth_price_provider
):
    repo.upsert_quant_scores([_score_row("005930.KS", 91.0, universe="kospi200")])
    stub_growth_price_provider.get_current_price.side_effect = None
    stub_growth_price_provider.get_current_price.return_value = SimpleNamespace(current=360_500.0)
    _store_consensus("005930.KS", consensus_source="KIS", current_price=317_000.0, target_mean=400_000.0, upside_pct=26.18)

    response = client.get("/api/growth/ticker/005930.KS/valuation?universe=kospi200&refresh_consensus=true")

    assert response.status_code == 200
    assert response.json()["current_price"] == 360_500.0
    assert response.json()["upside_pct"] == pytest.approx((400_000.0 - 360_500.0) / 360_500.0 * 100)


def test_growth_valuation_keeps_consensus_price_when_live_quote_raises(
    client, caplog, stub_growth_price_provider
):
    repo.upsert_quant_scores([_score_row("005930.KS", 91.0, universe="kospi200")])
    _store_consensus("005930.KS", consensus_source="KIS", current_price=317_000.0, target_mean=400_000.0, upside_pct=26.18)

    with caplog.at_level("WARNING", logger="api.routers.growth"):
        response = client.get("/api/growth/ticker/005930.KS/valuation?universe=kospi200&refresh_consensus=true")

    assert response.status_code == 200
    assert response.json()["current_price"] == 317_000.0
    assert response.json()["upside_pct"] == 26.18
    assert "live price fetch failed ticker=005930.KS error_type=RuntimeError" in caplog.text


@pytest.mark.parametrize("live_price", [0, -1, float("nan"), float("inf")])
def test_growth_valuation_keeps_consensus_price_when_live_quote_is_invalid(
    client, stub_growth_price_provider, live_price
):
    repo.upsert_quant_scores([_score_row("005930.KS", 91.0, universe="kospi200")])
    stub_growth_price_provider.get_current_price.side_effect = None
    stub_growth_price_provider.get_current_price.return_value = SimpleNamespace(current=live_price)
    _store_consensus("005930.KS", consensus_source="KIS", current_price=317_000.0, target_mean=400_000.0, upside_pct=26.18)

    response = client.get("/api/growth/ticker/005930.KS/valuation?universe=kospi200&refresh_consensus=true")

    assert response.status_code == 200
    assert response.json()["current_price"] == 317_000.0
    assert response.json()["upside_pct"] == 26.18


def test_growth_valuation_keeps_peg_when_consensus_is_rate_limited(client):
    repo.upsert_quant_scores([_score_row("AAPL", 91.0)])
    _store_consensus(
        "AAPL",
        consensus_status="rate_limited",
        consensus_message="FMP API 호출 한도에 도달했습니다.",
        current_price=None,
        target_mean=None,
        target_median=None,
        target_low=None,
        target_high=None,
        upside_pct=None,
        analyst_count=None,
        consensus_as_of=None,
    )

    response = client.get("/api/growth/ticker/AAPL/valuation?universe=sp500&refresh_consensus=true")

    assert response.status_code == 200
    body = response.json()
    assert body["peg"] == 0.8
    assert body["consensus_status"] == "rate_limited"
    assert body["consensus_message"] == "FMP API 호출 한도에 도달했습니다."


@pytest.mark.parametrize(
    ("ticker", "universe", "source"),
    [("005930.KS", "kospi200", "KIS"), ("AAPL", "sp500", "FMP")],
)
def test_growth_valuation_keeps_peg_when_consensus_snapshot_is_missing(
    client, ticker, universe, source
):
    repo.upsert_quant_scores([_score_row(ticker, 91.0, universe=universe)])

    response = client.get(f"/api/growth/ticker/{ticker}/valuation?universe={universe}&refresh_consensus=true")

    assert response.status_code == 200
    body = response.json()
    assert body["peg"] == 0.8
    assert body["consensus_status"] == "missing"
    assert body["consensus_source"] == source


def test_growth_valuation_converts_non_finite_numbers_to_null(client):
    _store_consensus("AAPL", target_mean=float("inf"), upside_pct=float("nan"))
    with patch("api.routers.growth.repo.get_quant_ticker", return_value={
        "raw_peg": float("inf"),
        "raw_fwd_pe": float("nan"),
        "raw_psr": 4.0,
        "raw_fwd_rev_growth": 0.15,
        "raw_fwd_eps_growth": 0.18,
    }):
        response = client.get("/api/growth/ticker/AAPL/valuation?universe=sp500&refresh_consensus=true")

    assert response.status_code == 200
    body = response.json()
    assert body["peg"] is None
    assert body["forward_pe"] is None
    assert body["target_mean"] is None
    assert body["upside_pct"] is None


def test_growth_timing_returns_analysis(client):
    with patch("api.routers.growth.analyze_timing", return_value={
        "status": "suitable",
        "aligned": True,
        "pullback": True,
        "pullback_stage": "approach",
        "volume_explosion": True,
        "volume_ratio": 1.6,
        "volume_level": "strong",
        "volume_direction": "bullish",
        "recent_bearish_volume_spike": False,
        "rsi14": 72.5,
        "rsi_level": "overheated",
        "positive_reasons": [{"code": "aligned", "message": "정배열", "severity": "positive"}],
        "warning_reasons": [{"code": "overheated_rsi", "message": "RSI 과열", "severity": "warning"}],
        "downgrade_reasons": [],
        "close": 205.0,
        "ema20": 202.0,
        "ema50": 190.0,
        "ema200": 160.0,
        "volume": 2_000.0,
        "avg_volume20": 1_000.0,
    }):
        response = client.get("/api/growth/ticker/AAPL/timing")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "suitable"
    assert body["pullback_stage"] == "approach"
    assert body["volume_ratio"] == 1.6


def test_growth_hydrate_fetches_watchlist_ticker_data(client):
    with (
        patch("api.routers.growth.fetch_ohlcv", return_value=("frame", ["BE: ok"])) as fetch_ohlcv,
        patch("api.routers.growth.analyze_timing", return_value={
            "status": "watch",
            "rows": 250,
            "volume_level": "strong",
            "volume_direction": "bullish",
            "rsi14": 72.5,
            "rsi_level": "overheated",
            "positive_reasons": [{"code": "aligned", "message": "정배열", "severity": "positive"}],
            "warning_reasons": [{"code": "overheated_rsi", "message": "RSI 과열", "severity": "warning"}],
            "downgrade_reasons": [],
        }) as analyze,
    ):
        response = client.post("/api/growth/ticker/BE/hydrate?universe=sp500")

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "BE"
    assert body["universe"] == "sp500"
    assert body["warnings"] == ["BE: ok"]
    assert body["timing_status"] == "watch"
    assert body["timing_rows"] == 250
    fetch_ohlcv.assert_called_once()
    assert fetch_ohlcv.call_args.args[0] == ["BE"]
    assert fetch_ohlcv.call_args.kwargs["force"] is True
    analyze.assert_called_once_with("BE")
    assert body["volume_level"] == "strong"
    assert body["volume_direction"] == "bullish"
    assert body["rsi14"] == 72.5
    assert body["rsi_level"] == "overheated"
    assert body["positive_reasons"][0]["code"] == "aligned"
    assert body["warning_reasons"][0]["message"] == "RSI 과열"
    assert body["downgrade_reasons"] == []


def test_growth_timing_converts_non_finite_numbers_to_null(client):
    with patch("api.routers.growth.analyze_timing", return_value={
        "status": "watch",
        "close": float("inf"),
        "ema20": float("nan"),
    }):
        response = client.get("/api/growth/ticker/AAPL/timing")

    assert response.status_code == 200
    assert response.json()["close"] is None
    assert response.json()["ema20"] is None


def test_growth_timing_returns_unknown_when_analysis_raises(client):
    with patch(
        "api.routers.growth.analyze_timing",
        side_effect=RuntimeError("upstream failed"),
    ):
        response = client.get("/api/growth/ticker/aapl/timing")

    assert response.status_code == 200
    assert response.json() == {
        "status": "unknown",
        "reason": "타이밍 분석 중 일시적인 오류가 발생했습니다.",
        "rows": None,
        "aligned": None,
        "pullback": None,
        "pullback_stage": None,
        "volume_explosion": None,
        "volume_ratio": None,
        "volume_level": None,
        "volume_direction": None,
        "recent_bearish_volume_spike": None,
        "rsi14": None,
        "rsi_level": None,
        "positive_reasons": [],
        "warning_reasons": [],
        "downgrade_reasons": [],
        "close": None,
        "ema20": None,
        "ema50": None,
        "ema200": None,
        "volume": None,
        "avg_volume20": None,
    }


def test_growth_refresh_requires_dart_for_korean_universe(client, monkeypatch):
    monkeypatch.delenv("DART_API_KEY", raising=False)

    response = client.post("/api/growth/refresh?universe=kospi200")

    assert response.status_code == 503


def test_growth_refresh_rejects_duplicate_batch(client, monkeypatch):
    import core.batch_state as bs

    monkeypatch.setitem(bs._state, "sp500", {
        "status": "running",
        "step": "팩터 계산 중",
        "done": 10,
        "total": 500,
        "started_at": "2026-06-02T07:10:00",
        "finished_at": "",
        "error": "",
    })

    response = client.post("/api/growth/refresh?universe=sp500")

    assert response.status_code == 409


def test_growth_refresh_skips_when_today_scores_exist(client):
    repo.upsert_quant_scores([_score_row("AAPL", 91.0)])

    with patch("core.scoring.universe_scorer.run_batch") as run_batch:
        response = client.post("/api/growth/refresh?universe=sp500")

    assert response.status_code == 200
    assert response.json()["status"] == "fresh"
    run_batch.assert_not_called()


def test_growth_status_reports_today_scores_as_fresh(client):
    repo.upsert_quant_scores([_score_row("AAPL", 91.0)])

    response = client.get("/api/screener/status?universe=sp500")

    assert response.status_code == 200
    assert response.json()["is_fresh"] is True
    assert response.json()["latest_as_of"] == date.today().isoformat()


def test_growth_force_refresh_runs_even_when_today_scores_exist(client):
    repo.upsert_quant_scores([_score_row("AAPL", 91.0)])

    with patch("core.scoring.universe_scorer.run_batch") as run_batch:
        response = client.post("/api/growth/refresh?universe=sp500&force=true")

    assert response.status_code == 200
    assert response.json()["status"] == "started"
    run_batch.assert_called_once_with("sp500")
