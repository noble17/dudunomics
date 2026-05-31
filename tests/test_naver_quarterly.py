"""core/data/naver_quarterly 단위 테스트 — 외부 HTTP 없음 (mock)."""
from unittest.mock import MagicMock, patch


def _make_quarter_response() -> MagicMock:
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {
        "itemCode": "005930",
        "financePeriodType": "quarter",
        "financeInfo": {
            "trTitleList": [
                {"key": "202503", "title": "2025.03.", "isConsensus": "N"},
                {"key": "202412", "title": "2024.12.", "isConsensus": "N"},
                {"key": "202409", "title": "2024.09.", "isConsensus": "N"},
                {"key": "202406", "title": "2024.06.", "isConsensus": "N"},
                {"key": "202606", "title": "2026.06.", "isConsensus": "Y"},
            ],
            "rowList": [
                {"title": "EPS", "columns": {"202503": {"value": "6,993"}, "202412": {"value": "2,864"}, "202409": {"value": "1,783"}, "202406": {"value": "733"}, "202606": {"value": "10,565"}}},
                {"title": "ROE", "columns": {"202503": {"value": "19.16"}, "202412": {"value": "10.85"}, "202409": {"value": "8.37"}, "202406": {"value": "7.95"}, "202606": {"value": "-"}}},
                {"title": "부채비율", "columns": {"202503": {"value": "30.15"}, "202412": {"value": "29.94"}, "202409": {"value": "26.64"}, "202406": {"value": "26.36"}, "202606": {"value": "-"}}},
                {"title": "매출액", "columns": {"202503": {"value": "1,338,734"}, "202412": {"value": "938,374"}, "202409": {"value": "860,617"}, "202406": {"value": "745,663"}, "202606": {"value": "1,665,266"}}},
                {"title": "영업이익", "columns": {"202503": {"value": "572,328"}, "202412": {"value": "200,737"}, "202409": {"value": "121,661"}, "202406": {"value": "46,761"}, "202606": {"value": "857,477"}}},
            ],
        },
    }
    return m


def test_fetch_confirmed_quarters_only():
    from core.data.naver_quarterly import fetch_naver_quarterly
    with patch("core.data.naver_quarterly.requests.get") as mock_get:
        mock_get.return_value = _make_quarter_response()
        rows = fetch_naver_quarterly("005930.KS")
    periods = [r["period"] for r in rows]
    assert "2026Q2" not in periods
    assert "2025Q1" in periods
    assert "2024Q4" in periods
    assert len(rows) == 4


def test_period_format_conversion():
    from core.data.naver_quarterly import fetch_naver_quarterly
    with patch("core.data.naver_quarterly.requests.get") as mock_get:
        mock_get.return_value = _make_quarter_response()
        rows = fetch_naver_quarterly("005930.KS")
    row = next(r for r in rows if r["period"] == "2025Q1")
    assert row["eps"] == 6993.0
    assert row["roe"] == 19.16
    assert row["debt_ratio"] == 30.15
    assert row["revenue"] == 1338734.0
    assert row["op_income"] == 572328.0
    assert row["ticker"] == "005930.KS"
    assert row["source"] == "naver"


def test_dash_values_become_none():
    from core.data.naver_quarterly import fetch_naver_quarterly
    with patch("core.data.naver_quarterly.requests.get") as mock_get:
        mock_get.return_value = _make_quarter_response()
        rows = fetch_naver_quarterly("005930.KS")
    for row in rows:
        assert row["period"] != "2026Q2"


def test_non_korean_ticker_returns_empty():
    from core.data.naver_quarterly import fetch_naver_quarterly
    assert fetch_naver_quarterly("AAPL") == []
