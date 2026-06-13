from datetime import date
import pytest
import core.repository as repo


def test_insert_and_get_golden_cross(fresh_db):
    repo.insert_golden_cross("005930.KS", "KR", "삼성전자", date(2026, 6, 1), "KOSPI")
    rows = repo.get_active_golden_crosses("KR")
    assert len(rows) == 1
    r = rows[0]
    assert r["ticker"] == "005930.KS"
    assert r["market"] == "KR"
    assert r["group_name"] == "KOSPI"
    assert r["day_count"] == 1


def test_update_golden_cross_day_count(fresh_db):
    repo.insert_golden_cross("AAPL", "US", "Apple", date(2026, 6, 1))
    repo.update_golden_cross("AAPL", 2)
    rows = repo.get_active_golden_crosses("US")
    assert rows[0]["day_count"] == 2


def test_delete_golden_cross(fresh_db):
    repo.insert_golden_cross("AAPL", "US", "Apple", date(2026, 6, 1))
    repo.delete_golden_cross("AAPL")
    assert repo.get_active_golden_crosses("US") == []


def test_get_active_golden_crosses_filters_by_market(fresh_db):
    repo.insert_golden_cross("005930.KS", "KR", "삼성전자", date(2026, 6, 1))
    repo.insert_golden_cross("AAPL", "US", "Apple", date(2026, 6, 1))
    kr = repo.get_active_golden_crosses("KR")
    us = repo.get_active_golden_crosses("US")
    assert len(kr) == 1 and kr[0]["ticker"] == "005930.KS"
    assert kr[0]["group_name"] == "KOSPI"
    assert len(us) == 1 and us[0]["ticker"] == "AAPL"
    assert us[0]["group_name"] == "US"


def test_insert_golden_cross_idempotent(fresh_db):
    """동일 ticker 중복 INSERT → 기존 행 유지 (INSERT OR IGNORE)."""
    repo.insert_golden_cross("AAPL", "US", "Apple", date(2026, 6, 1))
    repo.insert_golden_cross("AAPL", "US", "Apple", date(2026, 6, 2))  # 중복
    rows = repo.get_active_golden_crosses("US")
    assert len(rows) == 1
    assert str(rows[0]["first_detected_at"]) == "2026-06-01"  # 첫 감지일 유지


def test_insert_and_list_golden_cross_history(fresh_db):
    repo.insert_golden_cross_history(
        ticker="AAPL",
        market="US",
        group_name="US",
        name="Apple",
        status="NEW",
        day_count=1,
        cross_start_date=date(2026, 6, 1),
        close=200.0,
        ema5=198.0,
        ema20=190.0,
        ema60=180.0,
        reason="신규 골든크로스 발생",
    )

    rows = repo.list_golden_cross_history(market="US", group_name="US")
    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["status"] == "NEW"
    assert rows[0]["ema20"] == 190.0
