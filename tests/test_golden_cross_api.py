from datetime import date

import core.repository as repo


def test_golden_cross_api_returns_active_and_history(client):
    repo.insert_golden_cross("005930.KS", "KR", "삼성전자", date(2026, 6, 1), "KOSPI")
    repo.insert_golden_cross_history(
        ticker="005930.KS",
        market="KR",
        group_name="KOSPI",
        name="삼성전자",
        status="NEW",
        day_count=1,
        cross_start_date=date(2026, 6, 1),
        close=80000,
        ema5=79000,
        ema20=78000,
        ema60=76000,
        reason="신규 골든크로스 발생",
    )

    res = client.get("/api/golden-cross?group_name=KOSPI")

    assert res.status_code == 200
    data = res.json()
    assert data["active"][0]["ticker"] == "005930.KS"
    assert data["active"][0]["group_name"] == "KOSPI"
    assert data["history"][0]["status"] == "NEW"
