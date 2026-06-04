# tests/test_naver_fundamentals.py
"""core/data/naver_fundamentals 단위 테스트 — 외부 HTTP 없음 (mock)."""
from datetime import date
from unittest.mock import MagicMock, patch
import pytest


def _naver_resp(per: float, pbr: float, eps: float) -> MagicMock:
    m = MagicMock()
    m.json.return_value = {
        "marketSum": 1853270318,
        "per": per,
        "eps": eps,
        "pbr": pbr,
        "now": 317000,
        "diff": 17500,
        "rate": 5.84,
        "quant": 32804208,
        "amount": 10306931,
        "high": 319000,
        "low": 305500,
        "risefall": 2,
    }
    return m


@pytest.fixture(autouse=True)
def clear_cache():
    """각 테스트 전후 캐시 초기화."""
    import core.data.naver_fundamentals as mod
    mod._cache.clear()
    yield
    mod._cache.clear()


class TestTickerToCode:
    def test_ks_suffix(self):
        from core.data.naver_fundamentals import _ticker_to_code
        assert _ticker_to_code("005930.KS") == "005930"

    def test_kq_suffix(self):
        from core.data.naver_fundamentals import _ticker_to_code
        assert _ticker_to_code("035720.KQ") == "035720"

    def test_lowercase_ks(self):
        from core.data.naver_fundamentals import _ticker_to_code
        assert _ticker_to_code("005930.ks") == "005930"

    def test_us_ticker_returns_none(self):
        from core.data.naver_fundamentals import _ticker_to_code
        assert _ticker_to_code("AAPL") is None
        assert _ticker_to_code("SPY") is None
        assert _ticker_to_code("005930") is None  # 접미사 없음


class TestFetchNaverSummary:
    def test_returns_per_pbr_eps(self):
        with patch("core.data.naver_fundamentals.requests.get",
                   return_value=_naver_resp(25.62, 4.41, 12372.0)):
            from core.data.naver_fundamentals import fetch_naver_summary
            result = fetch_naver_summary("005930.KS")
        assert result is not None
        assert result["per"] == pytest.approx(25.62)
        assert result["pbr"] == pytest.approx(4.41)
        assert result["eps"] == pytest.approx(12372.0)
        assert result["market_cap_krw"] == pytest.approx(1_853_270_318_000_000.0)

    def test_zero_values_become_none(self):
        m = MagicMock()
        m.json.return_value = {"per": 0, "pbr": 0, "eps": 0}
        with patch("core.data.naver_fundamentals.requests.get", return_value=m):
            from core.data.naver_fundamentals import fetch_naver_summary
            result = fetch_naver_summary("000660.KS")
        assert result is not None
        assert result["per"] is None
        assert result["pbr"] is None
        assert result["eps"] is None

    def test_non_korean_returns_none(self):
        from core.data.naver_fundamentals import fetch_naver_summary
        assert fetch_naver_summary("AAPL") is None
        assert fetch_naver_summary("SPY") is None

    def test_returns_none_on_exception(self):
        with patch("core.data.naver_fundamentals.requests.get",
                   side_effect=Exception("timeout")):
            from core.data.naver_fundamentals import fetch_naver_summary
            result = fetch_naver_summary("005930.KS")
        assert result is None

    def test_kq_ticker_uses_correct_code(self):
        with patch("core.data.naver_fundamentals.requests.get",
                   return_value=_naver_resp(18.5, 2.1, 5000.0)) as mock_get:
            from core.data.naver_fundamentals import fetch_naver_summary
            fetch_naver_summary("035720.KQ")
        first_call = mock_get.call_args_list[0]
        assert first_call[1]["params"]["itemcode"] == "035720"


class TestExtendedSnapshotIntegration:
    def test_ks_ticker_populated_from_naver(self):
        import core.data.naver_fundamentals as nav_mod
        nav_mod._cache.clear()
        with patch("core.data.naver_fundamentals.requests.get",
                   return_value=_naver_resp(25.62, 4.41, 12372.0)):
            from core.data.fundamentals_extended import _fetch_one
            snap = _fetch_one("005930.KS", date.today())
        assert snap.ticker == "005930.KS"
        assert snap.trailing_pe == pytest.approx(25.62)
        assert snap.pbr == pytest.approx(4.41)
        assert snap.eps_ttm == pytest.approx(12372.0)

    def test_ks_ticker_empty_on_naver_failure(self):
        import core.data.naver_fundamentals as nav_mod
        nav_mod._cache.clear()
        with patch("core.data.naver_fundamentals.requests.get",
                   side_effect=Exception("network error")):
            from core.data.fundamentals_extended import _fetch_one
            snap = _fetch_one("005930.KS", date.today())
        assert snap.ticker == "005930.KS"
        assert snap.trailing_pe is None
        assert snap.pbr is None

    def test_us_ticker_unaffected(self):
        """미국 종목은 기존 scraper 경로 유지 — naver 호출 없음."""
        with patch("core.data.fundamentals_extended._scrape", return_value=None):
            from core.data.fundamentals_extended import _fetch_one
            snap = _fetch_one("AAPL", date.today())
        assert snap.ticker == "AAPL"
        assert snap.error == "scrape_failed"
