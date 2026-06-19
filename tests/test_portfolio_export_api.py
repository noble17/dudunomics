import core.repository as repo


def _headers(key: str = "sheet-secret") -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def test_portfolio_export_requires_configuration(client, monkeypatch):
    monkeypatch.delenv("PORTFOLIO_EXPORT_API_KEY", raising=False)

    res = client.get("/api/external/portfolio")

    assert res.status_code == 503


def test_portfolio_export_rejects_invalid_api_key(client, monkeypatch):
    monkeypatch.setenv("PORTFOLIO_EXPORT_API_KEY", "sheet-secret")

    res = client.get("/api/external/portfolio", headers=_headers("wrong"))

    assert res.status_code == 401


def test_portfolio_export_matches_spreadsheet_shape(client, monkeypatch):
    monkeypatch.setenv("PORTFOLIO_EXPORT_API_KEY", "sheet-secret")
    user = repo.get_user_by_email("test@test.com")
    uid = user["id"]

    repo.upsert_holding(
        uid, "005930.KS", "삼성전자", "KRW", 114, 294623,
        sector="반도체", market="KOSPI", source="toss",
    )
    repo.upsert_holding(
        uid, "0195R0", "삼성전자 2X", "KRW", 800, 24337,
        sector="반도체", market="KOSPI", source="toss",
    )
    repo.upsert_holding(
        uid, "GEV", "GE 버노바", "USD", 8, 1113,
        sector="에너지", market="NYSE", source="toss",
    )
    repo.upsert_holding(
        uid, "SNXX", "SNXX", "USD", 200, 26.86,
        sector="반도체", market="AMEX", source="toss",
    )
    repo.set_cash_source(uid, "toss", 47_196_514, 4_156.51)

    res = client.get("/api/external/portfolio", headers=_headers())

    assert res.status_code == 200
    body = res.json()
    assert body["cash"] == {"krw": 47_196_514, "usd": 4_156.51}
    assert body["domestic"] == [
        {
            "no": 1,
            "name": "삼성전자",
            "ticker": "005930",
            "market": "KOSPI",
            "quantity": 114,
            "avg_price": 294623,
            "sector": "반도체",
        },
        {
            "no": 2,
            "name": "삼성전자 2X",
            "ticker": "0195R0",
            "market": "KOSPI",
            "quantity": 800,
            "avg_price": 24337,
            "sector": "반도체",
        },
    ]
    assert body["overseas"] == [
        {
            "no": 21,
            "name": "GE 버노바",
            "ticker": "GEV",
            "market": "NYSE",
            "quantity": 8,
            "avg_price": 1113,
            "sector": "에너지",
        },
        {
            "no": 22,
            "name": "SNXX",
            "ticker": "SNXX",
            "market": "AMS",
            "quantity": 200,
            "avg_price": 26.86,
            "sector": "반도체",
        },
    ]
    assert "generated_at" in body


def test_portfolio_export_uses_primary_user_when_multiple_users_exist(client, monkeypatch):
    from core.auth.passwords import hash_password

    primary = repo.get_user_by_email("test@test.com")
    repo.upsert_holding(primary["id"], "005930.KS", "삼성전자", "KRW", 10, 70000)
    second_id = repo.create_user("second@test.com", hash_password("password123"))
    repo.upsert_holding(second_id, "AAPL", "Apple", "USD", 10, 150)
    monkeypatch.setenv("PORTFOLIO_EXPORT_API_KEY", "sheet-secret")

    res = client.get("/api/external/portfolio", headers=_headers())

    assert res.status_code == 200
    assert [row["ticker"] for row in res.json()["domestic"]] == ["005930"]
    assert res.json()["overseas"] == []
