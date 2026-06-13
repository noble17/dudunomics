"""KIS 잔고 조회 함수 테스트 — 외부 HTTP 호출 없음 (mock)."""
from unittest.mock import MagicMock, patch

import pytest


def _domestic_resp(output1: list[dict]) -> MagicMock:
    m = MagicMock()
    m.json.return_value = {
        "rt_cd": "0",
        "msg1": "정상처리",
        "output1": output1,
        "output2": {},
        "output3": {"ctx_area_fk100": "", "ctx_area_nk100": ""},
    }
    m.headers = {"tr_cont": " "}  # 더 이상 페이지 없음
    return m


def _overseas_resp(output1: list[dict]) -> MagicMock:
    m = MagicMock()
    m.json.return_value = {
        "rt_cd": "0",
        "msg1": "정상처리",
        "output1": output1,
        "output2": {},
    }
    m.headers = {"tr_cont": " "}
    return m


class TestFetchBalanceDomestic:
    def test_success(self):
        """정상 응답 → ticker=005930.KS, quantity, avg_price 확인."""
        output1 = [{"pdno": "005930", "prdt_name": "삼성전자", "hldg_qty": "10", "pchs_avg_pric": "70000"}]
        with patch("core.prices.kis._get_token", return_value="fake"), \
             patch("core.prices.kis.requests.get", return_value=_domestic_resp(output1)):
            from core.prices.kis import fetch_balance_domestic
            result = fetch_balance_domestic()

        assert len(result) == 1
        item = result[0]
        assert item["ticker"] == "005930.KS"
        assert item["name"] == "삼성전자"
        assert item["quantity"] == 10.0
        assert item["avg_price"] == 70000.0
        assert item["currency"] == "KRW"
        assert item["market"] == "KRX"

    def test_empty_output(self):
        """output1=[] → 빈 리스트."""
        with patch("core.prices.kis._get_token", return_value="fake"), \
             patch("core.prices.kis.requests.get", return_value=_domestic_resp([])):
            from core.prices.kis import fetch_balance_domestic
            result = fetch_balance_domestic()

        assert result == []

    def test_no_token_returns_empty(self):
        """토큰 없음 → 빈 리스트."""
        with patch("core.prices.kis._get_token", return_value=None):
            from core.prices.kis import fetch_balance_domestic
            result = fetch_balance_domestic()

        assert result == []


class TestFetchBalanceOverseas:
    def test_success_with_market_conversion(self):
        """NASD → NASDAQ market 변환 + 정상 필드 반환."""
        output1 = [
            {
                "ovrs_pdno": "AAPL",
                "ovrs_item_name": "Apple Inc",
                "ovrs_cblc_qty": "5",
                "pchs_avg_pric": "185.0",
                "ovrs_excg_cd": "NASD",
            }
        ]
        with patch("core.prices.kis._get_token", return_value="fake"), \
             patch("core.prices.kis.requests.get", return_value=_overseas_resp(output1)):
            from core.prices.kis import fetch_balance_overseas
            result = fetch_balance_overseas()

        assert len(result) == 1
        item = result[0]
        assert item["ticker"] == "AAPL"
        assert item["name"] == "Apple Inc"
        assert item["quantity"] == 5.0
        assert item["avg_price"] == 185.0
        assert item["currency"] == "USD"
        assert item["market"] == "NASDAQ"

    def test_skips_zero_quantity(self):
        """ovrs_cblc_qty=0 인 종목은 결과에서 제외."""
        output1 = [
            {"ovrs_pdno": "TSLA", "ovrs_item_name": "Tesla", "ovrs_cblc_qty": "0",
             "pchs_avg_pric": "200.0", "ovrs_excg_cd": "NASD"},
            {"ovrs_pdno": "MSFT", "ovrs_item_name": "Microsoft", "ovrs_cblc_qty": "3",
             "pchs_avg_pric": "420.0", "ovrs_excg_cd": "NASD"},
        ]
        with patch("core.prices.kis._get_token", return_value="fake"), \
             patch("core.prices.kis.requests.get", return_value=_overseas_resp(output1)):
            from core.prices.kis import fetch_balance_overseas
            result = fetch_balance_overseas()

        assert len(result) == 1
        assert result[0]["ticker"] == "MSFT"

    def test_no_token_returns_empty(self):
        """토큰 없음 → 빈 리스트."""
        with patch("core.prices.kis._get_token", return_value=None):
            from core.prices.kis import fetch_balance_overseas
            result = fetch_balance_overseas()

        assert result == []


class TestSyncEndpoint:
    def test_sync_from_kis_is_replaced_by_toss(self, client):
        res = client.post("/api/holdings/sync-from-kis")

        assert res.status_code == 200
        assert res.json() == {
            "added": 0,
            "updated": 0,
            "errors": ["KIS 동기화는 Toss 동기화로 대체되었습니다."],
        }
