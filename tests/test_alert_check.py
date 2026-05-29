import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
import core.repository as repo
from core.scheduler import alert_check_job


@pytest.fixture
def db_with_user(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    # 유저 생성 (id=1)
    repo.create_user("check@test.com", "hashed")
    return 1  # user_id


def _make_price_mock(ticker: str, price: float):
    from core.prices.base import Price
    return {ticker: Price(ticker=ticker, current=price, currency="USD")}


def _make_candle_df(n=50, close_values=None):
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    if close_values is None:
        close_values = [100.0 + i for i in range(n)]
    return pd.DataFrame({
        "Open": [c * 0.99 for c in close_values],
        "High": [c * 1.01 for c in close_values],
        "Low":  [c * 0.98 for c in close_values],
        "Close": close_values,
        "Volume": [1_000_000.0] * n,
    }, index=idx)


def test_price_above_fires(db_with_user):
    user_id = db_with_user
    alert_id = repo.create_alert(user_id, "AAPL", "price_above", 200.0)

    with patch("core.scheduler._price_provider") as mock_pp:
        mock_pp.get_current_prices.return_value = _make_price_mock("AAPL", 201.0)
        alert_check_job()

    events = repo.get_unread_alert_events(user_id)
    assert len(events) == 1
    assert events[0]["ticker"] == "AAPL"
    assert events[0]["condition_type"] == "price_above"
    assert events[0]["triggered_price"] == pytest.approx(201.0)


def test_price_above_no_fire_when_below(db_with_user):
    user_id = db_with_user
    repo.create_alert(user_id, "AAPL", "price_above", 200.0)

    with patch("core.scheduler._price_provider") as mock_pp:
        mock_pp.get_current_prices.return_value = _make_price_mock("AAPL", 199.0)
        alert_check_job()

    assert repo.get_unread_alert_events(user_id) == []


def test_rsi_below_fires(db_with_user):
    user_id = db_with_user
    alert_id = repo.create_alert(user_id, "SPY", "rsi_below", 30.0)

    # RSI가 30 미만이 되도록 하락 추세 데이터 생성
    close_values = [100.0 - i * 2 for i in range(60)]  # 급격한 하락
    fake_df = _make_candle_df(60, close_values)
    fake_prices = pd.concat({"SPY": fake_df}, axis=1)

    with patch("core.scheduler._price_provider") as mock_pp, \
         patch("core.scheduler.fetch_ohlcv", return_value=(fake_prices, [])):
        mock_pp.get_current_prices.return_value = _make_price_mock("SPY", 1.0)
        alert_check_job()

    events = repo.get_unread_alert_events(user_id)
    assert len(events) == 1
    assert events[0]["condition_type"] == "rsi_below"


def test_dedup_prevents_double_fire(db_with_user):
    """같은 alert_id가 1시간 내 두 번 이상 발화하지 않는다."""
    user_id = db_with_user
    repo.create_alert(user_id, "AAPL", "price_above", 200.0)

    with patch("core.scheduler._price_provider") as mock_pp:
        mock_pp.get_current_prices.return_value = _make_price_mock("AAPL", 201.0)
        alert_check_job()
        alert_check_job()  # 두 번 호출

    assert len(repo.get_unread_alert_events(user_id)) == 1


def test_golden_cross_fires(db_with_user):
    """MA5가 MA20을 상향 돌파하면 golden cross 발화."""
    user_id = db_with_user
    repo.create_alert(user_id, "TSLA", "ma_golden_cross", None)

    # 처음 35일 완만히 하락(MA5 < MA20에 근접), 마지막 5일 소폭 반등으로 MA5가 MA20 상향 돌파
    close_values = [100.0 - i * 0.5 for i in range(35)] + [82.5 + i * 3 for i in range(5)]
    fake_df = _make_candle_df(40, close_values)
    fake_prices = pd.concat({"TSLA": fake_df}, axis=1)

    with patch("core.scheduler._price_provider") as mock_pp, \
         patch("core.scheduler.fetch_ohlcv", return_value=(fake_prices, [])):
        mock_pp.get_current_prices.return_value = _make_price_mock("TSLA", 180.0)
        alert_check_job()

    events = repo.get_unread_alert_events(user_id)
    assert len(events) == 1
    assert events[0]["condition_type"] == "ma_golden_cross"
