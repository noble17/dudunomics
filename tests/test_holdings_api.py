def test_list_holdings_empty(client):
    res = client.get("/api/holdings")
    assert res.status_code == 200
    assert res.json() == []

def test_upsert_and_list(client):
    res = client.put("/api/holdings/005930.KS", json={
        "name": "삼성전자", "currency": "KRW", "quantity": 10, "avg_price": 70000
    })
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "005930.KS"
    assert data["quantity"] == 10
    res = client.get("/api/holdings")
    assert len(res.json()) == 1

def test_delete_holding(client):
    client.put("/api/holdings/AAPL", json={"name": "Apple", "currency": "USD", "quantity": 5, "avg_price": 175.0})
    res = client.delete("/api/holdings/AAPL")
    assert res.status_code == 200
    assert client.get("/api/holdings").json() == []

def test_cash_roundtrip(client):
    res = client.put("/api/holdings/cash", json={"cash_krw": 500000, "cash_usd": 200.0})
    assert res.status_code == 200
    res = client.get("/api/holdings/cash")
    data = res.json()
    assert data["cash_krw"] == 500000
    assert data["cash_usd"] == 200.0
    assert data["total_cash_krw"] == 500000
    assert data["total_cash_usd"] == 200.0

def test_invalid_currency(client):
    res = client.put("/api/holdings/TSLA", json={"name": "Tesla", "currency": "EUR", "quantity": 1, "avg_price": 100})
    assert res.status_code == 422


def test_lookup_uses_toss_provider(client, monkeypatch):
    monkeypatch.setattr("api.routers.holdings._price_provider.lookup", lambda ticker, market=None: {
        "ticker": "005930.KS",
        "name": "삼성전자",
        "market": "KOSPI",
        "currency": "KRW",
    })

    res = client.get("/api/holdings/lookup/005930.KS")

    assert res.status_code == 200
    assert res.json()["market"] == "KOSPI"


def test_sync_from_kis_is_deprecated(client):
    res = client.post("/api/holdings/sync-from-kis")

    assert res.status_code == 200
    assert res.json()["errors"] == ["KIS 동기화는 Toss 동기화로 대체되었습니다."]


def test_auth_required_when_env_set(monkeypatch):
    monkeypatch.setenv("BASIC_AUTH_USERNAME", "admin")
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", "secret")
    from fastapi.testclient import TestClient
    from api.main import app
    c = TestClient(app, raise_server_exceptions=False)
    res = c.get("/api/holdings")  # no auth header
    assert res.status_code == 401


def test_sync_from_toss_upserts_holdings(client, monkeypatch):
    items = [
        {"ticker": "005930.KS", "name": "삼성전자", "quantity": 10.0,
         "avg_price": 70000.0, "currency": "KRW", "market": "KRX"},
        {"ticker": "AAPL", "name": "Apple Inc.", "quantity": 5.0,
         "avg_price": 185.0, "currency": "USD", "market": "NASDAQ"},
    ]
    monkeypatch.setattr("api.routers.holdings.fetch_toss_holdings", lambda: items)
    monkeypatch.setattr("api.routers.holdings.fetch_toss_orders", lambda status="CLOSED": [])
    monkeypatch.setattr(
        "api.routers.holdings.fetch_toss_buying_power",
        lambda currency: 1_000_000 if currency == "KRW" else 500,
    )

    res = client.post("/api/holdings/sync-from-toss")

    assert res.status_code == 200
    assert res.json() == {"added": 2, "updated": 0, "deleted": 0, "errors": []}
    tickers = {h["ticker"] for h in client.get("/api/holdings").json()}
    assert tickers == {"005930.KS", "AAPL"}
    cash = client.get("/api/holdings/cash").json()
    assert cash["cash_krw"] == 0
    assert cash["cash_usd"] == 0
    assert cash["total_cash_krw"] == 1_000_000
    assert cash["total_cash_usd"] == 500
    assert cash["sources"] == [{"source": "toss", "cash_krw": 1_000_000, "cash_usd": 500}]


def test_sync_from_toss_returns_error_instead_of_500(client, monkeypatch):
    monkeypatch.setattr("api.routers.holdings.fetch_toss_holdings", lambda: (_ for _ in ()).throw(RuntimeError("401 Unauthorized")))

    res = client.post("/api/holdings/sync-from-toss")

    assert res.status_code == 200
    body = res.json()
    assert body["added"] == 0
    assert body["updated"] == 0
    assert "Toss 동기화 실패" in body["errors"][0]


def test_sync_from_toss_deletes_missing_toss_holding_and_keeps_manual_source(client, monkeypatch):
    import core.repository as repo

    user = repo.get_user_by_email("test@test.com")
    repo.upsert_holding(
        user["id"], "AAPL", "Apple", "USD", 2, 180,
        market="NASDAQ", source="manual",
    )
    repo.upsert_holding(
        user["id"], "AAPL", "Apple", "USD", 3, 185,
        market="NASDAQ", source="toss",
    )
    repo.upsert_holding(
        user["id"], "TSLA", "Tesla", "USD", 4, 220,
        market="NASDAQ", source="toss",
    )
    monkeypatch.setattr("api.routers.holdings.fetch_toss_holdings", lambda: [])
    monkeypatch.setattr("api.routers.holdings.fetch_toss_orders", lambda status="CLOSED": [])
    monkeypatch.setattr("api.routers.holdings.fetch_toss_buying_power", lambda currency: 0)

    res = client.post("/api/holdings/sync-from-toss")

    assert res.status_code == 200
    assert res.json() == {"added": 0, "updated": 0, "deleted": 2, "errors": []}
    holdings = client.get("/api/holdings").json()
    assert [(row["ticker"], row["quantity"]) for row in holdings] == [("AAPL", 2)]
    assert holdings[0]["sources"][0]["source"] == "manual"


def test_sync_from_toss_saves_closed_sell_trade_before_removing_holding(client, monkeypatch):
    import core.repository as repo

    user = repo.get_user_by_email("test@test.com")
    repo.upsert_holding(
        user["id"], "AAPL", "Apple", "USD", 3, 185,
        market="NASDAQ", source="toss",
    )
    monkeypatch.setattr("api.routers.holdings.fetch_toss_holdings", lambda: [])
    monkeypatch.setattr("api.routers.holdings.fetch_toss_buying_power", lambda currency: 0)
    monkeypatch.setattr("api.routers.holdings.fetch_toss_orders", lambda status="CLOSED": [{
        "external_id": "sell-aapl-1",
        "ticker": "AAPL",
        "market": "NASDAQ",
        "trade_type": "SELL",
        "quantity": 3,
        "price": 210,
        "currency": "USD",
        "traded_at": "2026-06-18",
        "fee": 1.25,
        "note": "Toss OpenAPI 주문/체결 동기화",
    }])

    res = client.post("/api/holdings/sync-from-toss")

    assert res.json()["deleted"] == 1
    assert client.get("/api/holdings").json() == []
    trades = client.get("/api/trades").json()
    assert len(trades) == 1
    assert trades[0]["trade_type"] == "SELL"
    assert trades[0]["price"] == 210
    assert trades[0]["source"] == "toss"


def test_sync_from_toss_removes_seeded_manual_shadow_for_sold_and_current_tickers(client, monkeypatch):
    import core.repository as repo

    user = repo.get_user_by_email("test@test.com")
    uid = user["id"]
    for ticker, quantity, avg_price in [
        ("327260.KS", 50, 63318),
        ("LITE", 10, 911.56),
        ("AAPL", 7, 150),
    ]:
        repo.upsert_holding(
            uid, ticker, ticker, "KRW" if ticker.endswith(".KS") else "USD",
            quantity, avg_price, source="manual",
        )
        repo.create_trade(
            uid, ticker, "KRX" if ticker.endswith(".KS") else "NASDAQ",
            "BUY", quantity, avg_price,
            "KRW" if ticker.endswith(".KS") else "USD",
            "2024-01-01", sync_holdings=False,
        )

    monkeypatch.setattr("api.routers.holdings.fetch_toss_holdings", lambda: [{
        "ticker": "AAPL",
        "name": "Apple",
        "quantity": 3,
        "avg_price": 190,
        "currency": "USD",
        "market": "NASDAQ",
    }])
    monkeypatch.setattr("api.routers.holdings.fetch_toss_buying_power", lambda currency: 0)
    monkeypatch.setattr("api.routers.holdings.fetch_toss_orders", lambda status="CLOSED": [
        {
            "external_id": "sell-rf",
            "ticker": "327260.KS",
            "market": "KRX",
            "trade_type": "SELL",
            "quantity": 50,
            "price": 64700,
            "currency": "KRW",
            "traded_at": "2026-06-17",
            "fee": 0,
            "note": "Toss OpenAPI 주문/체결 동기화",
        },
        {
            "external_id": "sell-lite",
            "ticker": "LITE",
            "market": "NASDAQ",
            "trade_type": "SELL",
            "quantity": 10,
            "price": 844.6,
            "currency": "USD",
            "traded_at": "2026-06-19",
            "fee": 0,
            "note": "Toss OpenAPI 주문/체결 동기화",
        },
        {
            "external_id": "buy-aapl",
            "ticker": "AAPL",
            "market": "NASDAQ",
            "trade_type": "BUY",
            "quantity": 3,
            "price": 190,
            "currency": "USD",
            "traded_at": "2026-06-18",
            "fee": 0,
            "note": "Toss OpenAPI 주문/체결 동기화",
        },
    ])

    res = client.post("/api/holdings/sync-from-toss")

    assert res.status_code == 200
    holdings = client.get("/api/holdings").json()
    assert [(row["ticker"], row["quantity"]) for row in holdings] == [("AAPL", 3)]
    assert holdings[0]["sources"][0]["source"] == "toss"


def test_patch_holding_source_meta_updates_toss_sector(client):
    items = [
        {"ticker": "0195R0", "name": "TIGER 삼성전자단일종목레버리지", "quantity": 800.0,
         "avg_price": 25345.0, "currency": "KRW", "market": "KOSPI", "sector": None},
    ]
    import core.repository as repo

    user = repo.get_user_by_email("test@test.com")
    repo.upsert_holding(user["id"], source="toss", **items[0])

    res = client.patch("/api/holdings/0195R0/source-meta", json={
        "source": "toss",
        "name": "삼성 레버리지",
        "sector": "반도체",
    })

    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "삼성 레버리지"
    assert body["sector"] == "반도체"
    assert body["sources"][0]["name"] == "삼성 레버리지"
    assert body["sources"][0]["sector"] == "반도체"


def test_patch_holding_source_meta_hides_toss_from_portfolio(client):
    import core.repository as repo

    user = repo.get_user_by_email("test@test.com")
    repo.upsert_holding(
        user["id"],
        "0195R0",
        "TIGER 삼성전자단일종목레버리지",
        "KRW",
        800,
        25345,
        market="KOSPI",
        source="toss",
    )

    res = client.patch("/api/holdings/0195R0/source-meta", json={
        "source": "toss",
        "excluded_from_portfolio": True,
    })

    assert res.status_code == 200
    assert res.json()["sources"][0]["excluded_from_portfolio"] is True
    assert client.get("/api/holdings").json()[0]["ticker"] == "0195R0"
    assert client.get("/api/portfolio/current").json()["rows"] == []
