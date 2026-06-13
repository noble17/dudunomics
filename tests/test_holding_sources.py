import pytest

import core.repository as repo


def test_get_holdings_aggregates_sources_by_weighted_average(fresh_db):
    repo.upsert_holding(1, "000660.KS", "SK하이닉스", "KRW", 10, 200000, market="KRX", source="manual")
    repo.upsert_holding(1, "000660.KS", "SK하이닉스", "KRW", 5, 220000, market="KRX", source="toss")

    rows = repo.get_holdings(1)

    assert len(rows) == 1
    row = rows[0]
    assert row["quantity"] == 15
    assert row["avg_price"] == pytest.approx((10 * 200000 + 5 * 220000) / 15)
    assert {s["source"] for s in row["sources"]} == {"manual", "toss"}


def test_delete_holding_removes_manual_source_only(fresh_db):
    repo.upsert_holding(1, "000660.KS", "SK하이닉스", "KRW", 10, 200000, market="KRX", source="manual")
    repo.upsert_holding(1, "000660.KS", "SK하이닉스", "KRW", 5, 220000, market="KRX", source="toss")

    repo.delete_holding(1, "000660.KS")
    row = repo.get_holdings(1)[0]

    assert row["quantity"] == 5
    assert row["avg_price"] == 220000
    assert [s["source"] for s in row["sources"]] == ["toss"]


def test_update_holding_source_meta_updates_display_fields_only(fresh_db):
    repo.upsert_holding(1, "0195R0", "TIGER 삼성전자단일종목레버리지", "KRW", 800, 25345, market="KOSPI", source="toss")

    assert repo.update_holding_source_meta(1, "0195R0", "toss", name="삼성 레버리지", sector="반도체") is True

    row = repo.get_holdings(1)[0]
    assert row["name"] == "삼성 레버리지"
    assert row["sector"] == "반도체"
    assert row["quantity"] == 800
    assert row["avg_price"] == 25345
    assert row["sources"][0]["name"] == "삼성 레버리지"
    assert row["sources"][0]["sector"] == "반도체"


def test_toss_upsert_preserves_user_display_fields(fresh_db):
    repo.upsert_holding(1, "0195R0", "TIGER 삼성전자단일종목레버리지", "KRW", 800, 25345, sector=None, market="KOSPI", source="toss")
    repo.update_holding_source_meta(1, "0195R0", "toss", name="삼성 레버리지", sector="반도체")

    repo.upsert_holding(
        1,
        "0195R0",
        "Toss 종목명",
        "KRW",
        900,
        25000,
        sector=None,
        market="KOSPI",
        source="toss",
        preserve_display_fields=True,
    )

    row = repo.get_holdings(1, include_excluded=True)[0]
    assert row["name"] == "삼성 레버리지"
    assert row["sector"] == "반도체"
    assert row["quantity"] == 900
    assert row["avg_price"] == 25000
    assert row["sources"][0]["name"] == "삼성 레버리지"
    assert row["sources"][0]["sector"] == "반도체"


def test_excluded_source_is_hidden_from_portfolio_but_visible_in_editor(fresh_db):
    repo.upsert_holding(1, "0195R0", "TIGER 삼성전자단일종목레버리지", "KRW", 800, 25345, market="KOSPI", source="toss")

    assert repo.update_holding_source_meta(1, "0195R0", "toss", excluded_from_portfolio=True) is True

    assert repo.get_holdings(1) == []
    editor_rows = repo.get_holdings(1, include_excluded=True)
    assert editor_rows[0]["ticker"] == "0195R0"
    assert editor_rows[0]["sources"][0]["excluded_from_portfolio"] is True
