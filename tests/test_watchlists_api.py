from __future__ import annotations

from unittest.mock import patch
from datetime import date

import core.repository as repo


def _perf_row(ticker: str, name: str) -> dict:
    return {
        "ticker": ticker,
        "name": name,
        "price": 100.0,
        "change_pct": 1.0,
        "volume": 1_000,
        "avg_volume20": 900,
        "perf_1w": 2.0,
        "perf_1m": 3.0,
        "perf_6m": 4.0,
        "perf_ytd": 5.0,
        "ma20": 95.0,
        "ma50": 90.0,
        "ma200": 80.0,
        "price_vs_ma20": 5.26,
        "price_vs_ma50": 11.11,
        "price_vs_ma200": 25.0,
        "day_low": 99.0,
        "day_high": 101.0,
        "range_52w_low": 70.0,
        "range_52w_high": 120.0,
    }


def test_watchlists_create_multiple_lists_and_share_one_ticker(client):
    first = client.get("/api/watchlists").json()[0]
    assert first["name"] == "기본 Watchlist"

    semiconductor = client.post("/api/watchlists", json={"name": "반도체"}).json()
    ai = client.post("/api/watchlists", json={"name": "AI 인프라"}).json()

    add_semis = client.put(
        f"/api/watchlists/{semiconductor['id']}/items/MU",
        json={"name": "Micron", "universe": "sp500"},
    )
    add_ai = client.put(
        f"/api/watchlists/{ai['id']}/items/MU",
        json={"name": "Micron", "universe": "sp500"},
    )

    assert add_semis.status_code == 200
    assert add_ai.status_code == 200

    lists = client.get("/api/watchlists").json()
    counts = {row["name"]: row["item_count"] for row in lists}
    assert counts["반도체"] == 1
    assert counts["AI 인프라"] == 1

    with patch("api.routers.watchlists.build_ticker_performance", return_value=[_perf_row("MU", "Micron")]):
        items = client.get(f"/api/watchlists/{semiconductor['id']}/items").json()

    assert items[0]["ticker"] == "MU"
    assert items[0]["name"] == "Micron"
    assert items[0]["price_vs_ma200"] == 25.0


def test_watchlist_item_remove_is_scoped_to_one_list(client):
    left = client.post("/api/watchlists", json={"name": "왼쪽"}).json()
    right = client.post("/api/watchlists", json={"name": "오른쪽"}).json()

    client.put(f"/api/watchlists/{left['id']}/items/MU", json={"name": "Micron", "universe": "sp500"})
    client.put(f"/api/watchlists/{right['id']}/items/MU", json={"name": "Micron", "universe": "sp500"})

    res = client.delete(f"/api/watchlists/{left['id']}/items/MU?universe=sp500")
    assert res.status_code == 200

    lists = client.get("/api/watchlists").json()
    counts = {row["name"]: row["item_count"] for row in lists}
    assert counts["왼쪽"] == 0
    assert counts["오른쪽"] == 1


def test_watchlist_memberships_for_ticker(client):
    first = client.get("/api/watchlists").json()[0]
    second = client.post("/api/watchlists", json={"name": "TEST"}).json()

    client.put(f"/api/watchlists/{first['id']}/items/BE", json={"name": "Bloom Energy", "universe": "sp500"})
    client.put(f"/api/watchlists/{second['id']}/items/BE", json={"name": "Bloom Energy", "universe": "sp500"})
    client.put(f"/api/watchlists/{second['id']}/items/MU", json={"name": "Micron", "universe": "sp500"})

    memberships = client.get("/api/watchlists/memberships/BE").json()

    assert [row["name"] for row in memberships] == ["기본 Watchlist", "TEST"]
    assert all(row["universe"] == "sp500" for row in memberships)


def test_watchlist_can_rename_and_return_growth_timing_fields(client):
    target = client.post("/api/watchlists", json={"name": "OLD"}).json()

    rename = client.patch(f"/api/watchlists/{target['id']}", json={"name": "NEW", "description": "눌림목 후보"})
    assert rename.status_code == 200
    assert rename.json()["name"] == "NEW"
    assert rename.json()["description"] == "눌림목 후보"

    repo.upsert_quant_scores([{
        "ticker": "MU",
        "universe": "sp500",
        "as_of": date.today(),
        "pct_momentum": 0.5,
        "pct_valuation": 0.5,
        "pct_eps_momentum": 0.5,
        "pct_quality": 0.5,
        "pct_technical": 0.5,
        "raw_momentum": 0.1,
        "raw_fwd_pe": 10.0,
        "raw_pbr": 2.0,
        "raw_psr": 3.0,
        "raw_trailing_pe": 12.0,
        "raw_eps_ttm": 4.0,
        "raw_fwd_eps": 5.0,
        "raw_roe": 20.0,
        "raw_debt_ratio": 0.3,
        "raw_rsi": 55.0,
        "above_ma200": True,
        "cfo_positive": True,
        "company_name": "Micron",
        "raw_ev_ebitda": None,
        "raw_peg": None,
        "raw_fcf_yield": None,
        "raw_eps_momentum": None,
        "negative_book_value": False,
        "growth_composite": 91.5,
        "sector": "Technology",
        "industry": "Semiconductors",
    }])
    client.put(f"/api/watchlists/{target['id']}/items/MU", json={"name": "Micron", "universe": "sp500"})

    with (
        patch("api.routers.watchlists.build_ticker_performance", return_value=[_perf_row("MU", "Micron")]),
        patch("api.routers.watchlists.analyze_timing", return_value={
            "status": "watch",
            "aligned": True,
            "pullback_stage": "lower",
            "volume_level": "normal",
            "rsi_level": "neutral",
        }),
    ):
        items = client.get(f"/api/watchlists/{target['id']}/items").json()

    assert items[0]["growth_composite"] == 91.5
    assert items[0]["timing_status"] == "watch"
    assert items[0]["timing_aligned"] is True
    assert items[0]["timing_pullback_stage"] == "lower"
