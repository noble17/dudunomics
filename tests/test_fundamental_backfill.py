from datetime import date

import core.repository as repo
from core.data.fundamentals_scraper import FundamentalsSnapshot


def test_list_fundamental_hydration_tickers_collects_watchlist_and_holdings(fresh_db):
    repo.create_user("u@test.com", "hash")
    user = repo.get_user_by_email("u@test.com")
    watchlist_id = repo.ensure_default_watchlist(user["id"])
    repo.upsert_watchlist_item(user["id"], watchlist_id, "BE", "sp500", name="Bloom")
    repo.upsert_holding(user["id"], "AAPL", "Apple", "USD", 2, 100)
    repo.upsert_holding(user["id"], "005930.KS", "삼성전자", "KRW", 1, 70000)

    assert repo.list_fundamental_hydration_tickers() == ["005930.KS", "AAPL", "BE"]


def test_hydrate_fundamental_snapshots_skips_domestic_and_saves_us(monkeypatch, fresh_db):
    from core.data import fundamental_backfill as backfill

    calls = []

    def fake_fetch(ticker):
        calls.append(ticker)
        return FundamentalsSnapshot(
            ticker=ticker,
            forward_pe=18.5,
            trailing_pe=21.0,
            price_to_book=3.2,
            price_to_sales=6.7,
            forward_eps=2.3,
            trailing_eps=1.9,
            return_on_equity=22.0,
            debt_to_equity=0.4,
            peg=1.2,
            market_cap_m=12_000.0,
            roic=0.18,
            gross_margin=0.5,
            operating_margin=0.25,
            current_ratio=1.8,
        )

    monkeypatch.setattr(backfill, "fetch_fundamentals", fake_fetch)
    monkeypatch.setattr(
        backfill,
        "compute_consensus_growth",
        lambda ticker: {"rev_fwd_cagr": 0.22, "eps_fwd_cagr": 0.31, "fwd_years": 2},
    )

    result = backfill.hydrate_fundamental_snapshots(["BE", "005930.KS", "BE"])

    assert result["requested"] == 1
    assert result["updated"] == 1
    assert result["skipped"] == 0
    assert calls == ["BE"]
    snapshot = repo.get_latest_fundamental_snapshot("BE")
    assert snapshot["as_of"] == date.today()
    assert snapshot["source"] == "finviz_stockanalysis"
    assert snapshot["forward_pe"] == 18.5
    assert snapshot["revenue_growth"] == 0.22
    assert snapshot["eps_growth"] == 0.31


def test_hydrate_fundamental_snapshots_reports_missing(monkeypatch, fresh_db):
    from core.data import fundamental_backfill as backfill

    monkeypatch.setattr(backfill, "fetch_fundamentals", lambda ticker: None)

    result = backfill.hydrate_fundamental_snapshots(["ZZZ"])

    assert result["requested"] == 1
    assert result["updated"] == 0
    assert result["skipped"] == 1
    assert result["errors"] == ["ZZZ: fundamentals 없음"]
