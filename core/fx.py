"""환율 프로바이더 — KIS 우선, yfinance 폴백."""
import logging
import os
from abc import ABC, abstractmethod

from core.data.yf_session import get_session
from core.prices.selection import prefer_toss_market_data

log = logging.getLogger(__name__)


class FxProvider(ABC):
    @abstractmethod
    def get_rate(self, pair: str) -> float:
        """pair: 'USDKRW' → 환율(원/달러) 반환."""
        ...


class KisFxProvider(FxProvider):
    """KIS 환율 시세. 실패 시 yfinance 폴백."""

    def get_rate(self, pair: str) -> float:
        try:
            return self._fetch_kis(pair)
        except Exception as e:
            log.warning("KIS 환율 조회 실패 (%s): %s — yfinance 폴백", pair, e)
            return self._fetch_yfinance(pair)

    def _fetch_kis(self, pair: str) -> float:
        """KIS 해외시세 price-detail 응답의 t_rate 필드로 환율 취득 (pykis 미사용)."""
        if pair != "USDKRW":
            raise ValueError(f"KIS FX: {pair} 미지원, yfinance 폴백")

        from core.prices.kis import KIS_BASE, _get_token, _headers
        token = _get_token()
        if not token:
            raise RuntimeError("KIS 토큰 없음")

        import requests
        res = requests.get(
            f"{KIS_BASE}/uapi/overseas-price/v1/quotations/price-detail",
            params={"AUTH": "", "EXCD": "NAS", "SYMB": "AAPL"},
            headers=_headers("HHDFS76200200", token),
            timeout=10,
        )
        data = res.json()
        if data.get("rt_cd") != "0":
            raise RuntimeError(f"KIS price-detail 오류: {data.get('msg1')}")
        t_rate = float(data["output"].get("t_rate") or 0)
        if t_rate <= 0:
            raise RuntimeError("t_rate 값 없음")
        return t_rate

    def _fetch_yfinance(self, pair: str) -> float:
        import yfinance as yf
        symbol = "KRW=X" if pair == "USDKRW" else f"{pair[:3]}{pair[3:]}=X"
        info = yf.Ticker(symbol, session=get_session()).fast_info
        return float(info.last_price)


class YFinanceFxProvider(FxProvider):
    """yfinance 전용 환율 프로바이더 (KIS 키 없을 때 사용)."""

    def get_rate(self, pair: str) -> float:
        import yfinance as yf
        symbol = "KRW=X" if pair == "USDKRW" else f"{pair[:3]}{pair[3:]}=X"
        info = yf.Ticker(symbol, session=get_session()).fast_info
        return float(info.last_price)


class TossFxProvider(FxProvider):
    """Toss OpenAPI 환율 provider."""

    def get_rate(self, pair: str) -> float:
        from core.prices.toss import fetch_exchange_rate
        return fetch_exchange_rate(pair)


def get_fx_provider() -> FxProvider:
    """환경변수에 따라 환율 provider 선택."""
    if prefer_toss_market_data():
        return TossFxProvider()
    if os.getenv("MARKET_DATA_PROVIDER", "").lower() == "kis" and os.getenv("KIS_APPKEY"):
        return KisFxProvider()
    return YFinanceFxProvider()
