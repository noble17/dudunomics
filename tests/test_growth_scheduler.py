"""tests/test_growth_scheduler.py — 성장주 배치 스케줄러."""
from unittest.mock import patch


def test_growth_batch_kr_runs_both_domestic_universes(monkeypatch):
    from core.scheduler import growth_batch_kr_job

    monkeypatch.setenv("DART_API_KEY", "test-key")
    with patch("core.scoring.universe_scorer.run_batch") as run_batch:
        growth_batch_kr_job()

    assert [call.args[0] for call in run_batch.call_args_list] == ["kospi200", "kosdaq150"]


def test_growth_batch_kr_skips_without_dart(monkeypatch):
    from core.scheduler import growth_batch_kr_job

    monkeypatch.delenv("DART_API_KEY", raising=False)
    with patch("core.scoring.universe_scorer.run_batch") as run_batch:
        growth_batch_kr_job()

    run_batch.assert_not_called()


def test_growth_batch_us_runs_both_us_universes():
    from core.scheduler import growth_batch_us_job

    with patch("core.scoring.universe_scorer.run_batch") as run_batch:
        growth_batch_us_job()

    assert [call.args[0] for call in run_batch.call_args_list] == ["sp500", "nasdaq100"]


def test_growth_batch_us_skips_fresh_universe():
    from core.scheduler import growth_batch_us_job

    with patch("core.batch_refresh.get_status", return_value={"status": "idle", "is_fresh": True}), \
         patch("core.scoring.universe_scorer.run_batch") as run_batch:
        growth_batch_us_job()

    run_batch.assert_not_called()


def test_scheduler_registers_growth_jobs():
    from core.scheduler import create_scheduler

    scheduler = create_scheduler()

    assert scheduler.get_job("growth_batch_kr") is not None
    assert scheduler.get_job("growth_batch_us") is not None


def test_scheduler_registers_toss_holdings_sync_job():
    from core.scheduler import create_scheduler

    scheduler = create_scheduler()

    assert scheduler.get_job("toss_holdings_sync") is not None
    assert scheduler.get_job("fundamental_snapshots_hydrate") is not None


def test_toss_holdings_sync_job_updates_users(monkeypatch, fresh_db):
    import core.repository as repo
    from core.auth.passwords import hash_password
    from core.scheduler import toss_holdings_sync_job

    monkeypatch.setenv("TOSS_HOLDINGS_SYNC_ENABLED", "true")
    user_id = repo.create_user("sync@test.com", hash_password("password123"))
    item = {
        "ticker": "005930.KS",
        "name": "삼성전자",
        "quantity": 3.0,
        "avg_price": 70000.0,
        "currency": "KRW",
        "market": "KRX",
    }
    monkeypatch.setattr("core.scheduler.fetch_toss_holdings", lambda: [item])
    monkeypatch.setattr("core.scheduler.fetch_toss_buying_power", lambda currency: 1000 if currency == "KRW" else 2)

    toss_holdings_sync_job()

    holdings = repo.get_holdings(user_id)
    assert holdings[0]["ticker"] == "005930.KS"
    assert holdings[0]["sources"][0]["source"] == "toss"
    assert repo.get_cash_source(user_id, "toss") == {"cash_krw": 1000.0, "cash_usd": 2.0}
    assert repo.get_cash_total(user_id) == {"cash_krw": 1000.0, "cash_usd": 2.0}
