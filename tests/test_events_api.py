import pytest


def test_get_events_empty(client):
    res = client.get("/api/portfolio/events")
    assert res.status_code == 200
    assert res.json() == []


def test_add_event(client):
    payload = {
        "ts": "2026-05-23T21:09:00",
        "label": "5월 월급",
        "amount": 7_900_000,
        "type": "입금",
    }
    res = client.post("/api/portfolio/events", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] >= 1
    assert data["label"] == "5월 월급"
    assert data["amount"] == 7_900_000
    assert data["type"] == "입금"


def test_add_event_minimal(client):
    """amount, type 생략 시 기본값 적용"""
    res = client.post("/api/portfolio/events", json={"ts": "2026-05-01T10:00:00", "label": "메모"})
    assert res.status_code == 200
    data = res.json()
    assert data["amount"] == 0
    assert data["type"] == "기타"


def test_delete_event(client):
    res = client.post("/api/portfolio/events", json={
        "ts": "2026-05-01T10:00:00", "label": "삭제테스트", "amount": 0, "type": "기타"
    })
    event_id = res.json()["id"]

    del_res = client.delete(f"/api/portfolio/events/{event_id}")
    assert del_res.status_code == 200
    assert del_res.json() == {"ok": True}

    assert client.get("/api/portfolio/events").json() == []


def test_delete_nonexistent_event(client):
    res = client.delete("/api/portfolio/events/9999")
    assert res.status_code == 200  # 존재하지 않아도 ok
