# tests/test_market_indices.py
"""core/data/market_indices 단위 테스트 — 외부 HTTP 없음 (mock)."""
from unittest.mock import MagicMock, patch
import pytest


def _fmp_quote_resp(symbol: str, price: float, change_pct: float) -> MagicMock:
    m = MagicMock()
    m.json.return_value = [{"symbol": symbol, "price": price, "changePercentage": change_pct}]
    return m


def _fmp_empty_resp() -> MagicMock:
    m = MagicMock()
    m.json.return_value = []
    return m


def _treasury_resp(today: float, prev: float) -> MagicMock:
    m = MagicMock()
    m.json.return_value = [
        {"date": "2026-05-31", "year10": today},
        {"date": "2026-05-30", "year10": prev},
    ]
    return m


def _stooq_resp(open_: float, close: float) -> MagicMock:
    m = MagicMock()
    m.text = (
        "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
        f"CL.F,2026-05-31,23:00:00,{open_},91.0,86.0,{close},\n"
    )
    return m


def _stooq_empty_resp() -> MagicMock:
    m = MagicMock()
    m.text = "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
    return m


@pytest.fixture(autouse=True)
def clear_cache():
    """각 테스트 전후 캐시 초기화 (모듈 레벨 딕셔너리 공유 방지)."""
    import core.data.market_indices as mod
    mod._cache.clear()
    yield
    mod._cache.clear()


class TestFetchFmpQuote:
    def test_returns_price_and_change_pct(self):
        with patch("core.data.market_indices.requests.get",
                   return_value=_fmp_quote_resp("^DJI", 42000.0, 0.5)):
            from core.data.market_indices import _fetch_fmp_quote
            result = _fetch_fmp_quote("^DJI")
        assert result is not None
        assert result["price"] == 42000.0
        assert result["change_pct"] == 0.5

    def test_returns_none_on_empty_response(self):
        with patch("core.data.market_indices.requests.get",
                   return_value=_fmp_empty_resp()):
            from core.data.market_indices import _fetch_fmp_quote
            result = _fetch_fmp_quote("^DJI")
        assert result is None

    def test_returns_none_when_no_api_key(self, monkeypatch):
        monkeypatch.setenv("FMP_API_KEY", "")
        import core.data.market_indices as mod
        result = mod._fetch_fmp_quote("^DJI")
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("core.data.market_indices.requests.get",
                   side_effect=Exception("timeout")):
            from core.data.market_indices import _fetch_fmp_quote
            result = _fetch_fmp_quote("^DJI")
        assert result is None


class TestFetchFmpTreasury10y:
    def test_price_and_change_pct_computed(self):
        with patch("core.data.market_indices.requests.get",
                   return_value=_treasury_resp(4.50, 4.40)):
            from core.data.market_indices import _fetch_fmp_treasury_10y
            result = _fetch_fmp_treasury_10y()
        assert result is not None
        assert result["price"] == pytest.approx(4.50)
        expected_pct = round((4.50 - 4.40) / 4.40 * 100, 4)
        assert result["change_pct"] == pytest.approx(expected_pct)

    def test_returns_none_on_empty_response(self):
        m = MagicMock(); m.json.return_value = []
        with patch("core.data.market_indices.requests.get", return_value=m):
            from core.data.market_indices import _fetch_fmp_treasury_10y
            result = _fetch_fmp_treasury_10y()
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("core.data.market_indices.requests.get",
                   side_effect=Exception("conn error")):
            from core.data.market_indices import _fetch_fmp_treasury_10y
            result = _fetch_fmp_treasury_10y()
        assert result is None


class TestFetchStooqWti:
    def test_returns_close_and_change_pct(self):
        with patch("core.data.market_indices.requests.get",
                   return_value=_stooq_resp(85.0, 87.36)):
            from core.data.market_indices import _fetch_stooq_wti
            result = _fetch_stooq_wti()
        assert result is not None
        assert result["price"] == pytest.approx(87.36)
        expected_pct = round((87.36 - 85.0) / 85.0 * 100, 4)
        assert result["change_pct"] == pytest.approx(expected_pct)

    def test_returns_none_on_empty_csv(self):
        with patch("core.data.market_indices.requests.get",
                   return_value=_stooq_empty_resp()):
            from core.data.market_indices import _fetch_stooq_wti
            result = _fetch_stooq_wti()
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("core.data.market_indices.requests.get",
                   side_effect=Exception("timeout")):
            from core.data.market_indices import _fetch_stooq_wti
            result = _fetch_stooq_wti()
        assert result is None


class TestGetMarketIndices:
    def test_returns_all_five_keys(self):
        with (
            patch("core.data.market_indices._fetch_fmp_quote",
                  side_effect=lambda sym: {"price": 1.0, "change_pct": 0.1}),
            patch("core.data.market_indices._fetch_fmp_treasury_10y",
                  return_value={"price": 4.5, "change_pct": 0.2}),
            patch("core.data.market_indices._fetch_stooq_wti",
                  return_value={"price": 87.0, "change_pct": -0.5}),
        ):
            from core.data.market_indices import get_market_indices
            result = get_market_indices()
        assert set(result.keys()) == {"DJI", "VIX", "GOLD", "US10Y", "WTI"}
