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
