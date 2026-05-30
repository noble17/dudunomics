"""KIS 해외 일봉 OHLCV 테스트 — 외부 HTTP 호출 없음 (mock)."""
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _row(xymd: str, clos: float = 150.0) -> dict:
    return {
        "xymd": xymd,
        "open": str(round(clos * 0.99, 2)),
        "high": str(round(clos * 1.01, 2)),
        "low":  str(round(clos * 0.98, 2)),
        "clos": str(clos),
        "tvol": "1000000",
    }


def _resp(rows: list[dict], keyb: str = "") -> MagicMock:
    m = MagicMock()
    m.json.return_value = {
        "rt_cd": "0",
        "msg1": "정상처리",
        "output1": {"keyb": keyb},
        "output2": rows,
    }
    return m


# ── fetch_ohlcv_overseas 단위 테스트 ─────────────────────────────────────────

class TestFetchOhlcvOverseas:
    START = date(2025, 1, 2)
    END   = date(2025, 3, 31)

    def test_success_single_page(self):
        """정상 5행 응답 → DataFrame shape/columns 검증."""
        rows = [_row(f"202503{d:02d}") for d in [31, 28, 27, 26, 25]]
        with patch("core.prices.kis._get_token", return_value="fake"), \
             patch("core.prices.kis.requests.get", return_value=_resp(rows)):
            from core.prices.kis import fetch_ohlcv_overseas
            df = fetch_ohlcv_overseas("AAPL", self.START, self.END, market="NASDAQ")

        assert not df.empty
        assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert len(df) == 5
        assert df.index.is_monotonic_increasing

    def test_pagination_two_pages(self):
        """2페이지 응답(keyb 있음→없음) → 행 합산 검증."""
        page1_rows = [_row(f"202503{d:02d}") for d in range(28, 20, -1)]  # 8행
        page2_rows = [_row(f"202501{d:02d}") for d in range(31, 23, -1)]  # 8행

        responses = [
            _resp(page1_rows, keyb="NEXTPAGE"),
            _resp(page2_rows, keyb=""),
        ]
        with patch("core.prices.kis._get_token", return_value="fake"), \
             patch("core.prices.kis.requests.get", side_effect=responses):
            from core.prices.kis import fetch_ohlcv_overseas
            df = fetch_ohlcv_overseas("AAPL", date(2025, 1, 1), self.END)

        assert len(df) == 16
        assert df.index.is_monotonic_increasing

    def test_empty_output2_returns_empty_df(self):
        """output2=[] → 빈 DataFrame 반환."""
        with patch("core.prices.kis._get_token", return_value="fake"), \
             patch("core.prices.kis.requests.get", return_value=_resp([])):
            from core.prices.kis import fetch_ohlcv_overseas
            df = fetch_ohlcv_overseas("AAPL", self.START, self.END)

        assert df.empty

    def test_no_token_returns_empty_df(self):
        """KIS_APPKEY 없음(토큰 None) → 빈 DataFrame, requests.get 미호출."""
        with patch("core.prices.kis._get_token", return_value=None), \
             patch("core.prices.kis.requests.get") as mock_get:
            from core.prices.kis import fetch_ohlcv_overseas
            df = fetch_ohlcv_overseas("AAPL", self.START, self.END)

        assert df.empty
        mock_get.assert_not_called()


# ── ohlcv_cache 통합 테스트 ───────────────────────────────────────────────────

class TestOhlcvCacheKisIntegration:
    START = date(2025, 1, 2)
    END   = date(2025, 3, 31)

    def _fake_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "Open": [150.0], "High": [155.0], "Low": [148.0],
            "Close": [152.0], "Volume": [1_000_000],
        }, index=pd.to_datetime(["2025-03-31"]))

    def test_uses_kis_for_overseas(self, fresh_db):
        """해외 ticker → KIS fetch 호출, yfinance bulk 미호출."""
        with patch("core.prices.kis.fetch_ohlcv_overseas", return_value=self._fake_df()) as mock_kis, \
             patch("core.data.ohlcv_cache._fetch_yfinance_bulk") as mock_yf:
            from core.data.ohlcv_cache import _fetch_and_store
            _fetch_and_store(["AAPL"], self.START, self.END)

        mock_kis.assert_called_once_with("AAPL", self.START, self.END)
        mock_yf.assert_not_called()

    def test_fallback_to_yfinance_when_kis_empty(self, fresh_db):
        """KIS → 빈 DataFrame → yfinance bulk 호출 확인."""
        with patch("core.prices.kis.fetch_ohlcv_overseas", return_value=pd.DataFrame()), \
             patch("core.data.ohlcv_cache._fetch_yfinance_bulk", return_value={"AAPL": self._fake_df()}) as mock_yf, \
             patch("core.data.ohlcv_cache._store_df"):
            from core.data.ohlcv_cache import _fetch_and_store
            _fetch_and_store(["AAPL"], self.START, self.END)

        mock_yf.assert_called_once_with(["AAPL"], self.START, self.END)
