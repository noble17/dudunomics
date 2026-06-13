import core.repository as repo


def test_jobs_list_includes_registered_jobs(client):
    res = client.get("/api/jobs")

    assert res.status_code == 200
    payload = res.json()
    ids = {job["id"] for job in payload}
    assert "snapshot" in ids
    assert "toss_holdings_sync" in ids
    assert "fundamental_snapshots_hydrate" in ids
    assert "daily_watchlist_timing_alert" in ids
    toss = next(job for job in payload if job["id"] == "toss_holdings_sync")
    assert toss["bootstrap"] is True
    assert "Toss" in toss["bootstrap_description"]
    assert payload[0]["latest_run"] is None


def test_jobs_list_exposes_latest_run(client):
    run_id, should_run = repo.start_job_run("snapshot", "manual")
    assert should_run is True
    repo.finish_job_run(run_id, "success", message="완료", meta={"rows": 3})

    res = client.get("/api/jobs")

    assert res.status_code == 200
    snapshot = next(job for job in res.json() if job["id"] == "snapshot")
    assert snapshot["latest_run"]["status"] == "success"
    assert snapshot["latest_run"]["message"] == "완료"
    assert snapshot["latest_run"]["meta_json"] == {"rows": 3}


def test_job_run_endpoint_queues_manual_run(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "api.routers.jobs.run_registered_job",
        lambda job_id, trigger_type: calls.append((job_id, trigger_type)),
    )

    res = client.post("/api/jobs/snapshot/run")

    assert res.status_code == 200
    assert res.json() == {"status": "started", "job_id": "snapshot"}
    assert calls == [("snapshot", "manual")]


def test_bootstrap_run_endpoint_queues_bootstrap_jobs(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "api.routers.jobs.run_bootstrap_jobs",
        lambda trigger_type: calls.append(trigger_type),
    )

    res = client.post("/api/jobs/bootstrap/run")

    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "started"
    assert "snapshot" in payload["job_ids"]
    assert "toss_holdings_sync" in payload["job_ids"]
    assert "alert_check" not in payload["job_ids"]
    assert calls == ["manual_bootstrap"]


def test_unknown_job_returns_404(client):
    res = client.post("/api/jobs/not-found/run")

    assert res.status_code == 404


def test_daily_watchlist_timing_alert_sends_checked_items(client, monkeypatch):
    from core.scheduler import daily_watchlist_timing_alert_job

    target = client.post("/api/watchlists", json={"name": "반도체"}).json()
    client.put(
        f"/api/watchlists/{target['id']}/items/MU",
        json={"name": "Micron", "universe": "sp500", "timing_alert_enabled": True},
    )
    client.put(
        f"/api/watchlists/{target['id']}/items/NVDA",
        json={"name": "Nvidia", "universe": "sp500", "timing_alert_enabled": False},
    )

    sent = []
    monkeypatch.setattr("core.scheduler.send_telegram", lambda text: sent.append(text) or True)
    monkeypatch.setattr("core.scheduler.analyze_timing", lambda ticker: {
        "status": "watch",
        "aligned": True,
        "pullback_stage": "approach",
        "volume_direction": "bullish",
        "volume_level": "normal",
        "volume_ratio": 1.2,
        "rsi14": 54.2,
        "rsi_level": "neutral",
        "close": 100.0,
        "ema20": 95.0,
        "ema50": 90.0,
        "ema200": 80.0,
        "positive_reasons": ["정배열입니다."],
    })

    result = daily_watchlist_timing_alert_job()

    assert result == {"items": 1, "success": 1, "failed": 0, "sent": True}
    assert len(sent) == 1
    assert "관심종목 TIMING CHECK" in sent[0]
    assert "[반도체] MU Micron" in sent[0]
    assert "NVDA" not in sent[0]
