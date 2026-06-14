import core.repository as repo
from datetime import date


def test_jobs_list_includes_registered_jobs(client):
    res = client.get("/api/jobs")

    assert res.status_code == 200
    payload = res.json()
    ids = {job["id"] for job in payload}
    assert "snapshot" in ids
    assert "toss_holdings_sync" in ids
    assert "fundamental_snapshots_hydrate" in ids
    assert "choicestock_public_hydrate" in ids
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


def test_choicestock_public_hydrate_job_collects_watchlist_once(client, monkeypatch):
    from core.scheduler import choicestock_public_hydrate_job

    target = client.post("/api/watchlists", json={"name": "반도체"}).json()
    client.put(
        f"/api/watchlists/{target['id']}/items/LITE",
        json={"name": "Lumentum", "universe": "sp500"},
    )
    client.put(
        f"/api/watchlists/{target['id']}/items/005930.KS",
        json={"name": "삼성전자", "universe": "kospi200"},
    )

    calls = []
    monkeypatch.setattr("core.scheduler.get_public_summary", lambda ticker: calls.append(ticker) or {"ticker": ticker})

    result = choicestock_public_hydrate_job()

    assert result == {"tickers": 1, "updated": 1, "failed": 0}
    assert calls == ["LITE"]


def test_daily_holdings_news_uses_choicestock_summary(client, monkeypatch):
    from core.scheduler import daily_holdings_news_job

    target = client.post("/api/watchlists", json={"name": "뉴스"}).json()
    client.put(
        f"/api/watchlists/{target['id']}/items/LITE",
        json={"name": "Lumentum", "universe": "sp500"},
    )

    today_text = date.today().strftime("%Y.%m.%d")
    monkeypatch.setattr("core.scheduler.get_public_summary", lambda ticker: {
        "news": [
            {
                "title": "루멘텀홀딩스, AI 성장 전략 제시",
                "published_date": f"{today_text} 08:10",
                "url": "https://www.choicestock.co.kr/stock/news_view/150978",
                "site": "ChoiceStock public page",
            },
            {
                "title": "어제 뉴스",
                "published_date": "2026.01.01 08:10",
                "url": "https://www.choicestock.co.kr/stock/news_view/1",
                "site": "ChoiceStock public page",
            },
        ],
    })
    sent = []
    monkeypatch.setattr("core.scheduler.send_telegram", lambda text: sent.append(text) or True)

    result = daily_holdings_news_job()

    assert result == {"tickers": 1, "news": 1, "sent": True}
    assert len(sent) == 1
    assert "관심종목 오늘 뉴스" in sent[0]
    assert "루멘텀홀딩스, AI 성장 전략 제시" in sent[0]
    assert "choicestock.co.kr/stock/news_view/150978" in sent[0]
    assert "어제 뉴스" not in sent[0]
