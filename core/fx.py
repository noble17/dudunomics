"""환율 프로바이더 — KIS 우선, yfinance 폴백."""
import logging
import os
from abc import ABC, abstractmethod

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
        from pykis import PyKis
        env = os.getenv("KIS_ENV", "real")
        api = PyKis(
            appkey=os.environ["KIS_APPKEY"],
            secretkey=os.environ["KIS_SECRETKEY"],
            account=os.environ["KIS_ACCOUNT_NO"],
            virtual=env != "real",
        )
        # KIS 환율: USD/KRW
        rate_info = api.forex_rate("USD")
        return float(rate_info.rate)

    def _fetch_yfinance(self, pair: str) -> float:
        import yfinance as yf
        symbol = "KRW=X" if pair == "USDKRW" else f"{pair[:3]}{pair[3:]}=X"
        info = yf.Ticker(symbol).fast_info
        return float(info.last_price)


class YFinanceFxProvider(FxProvider):
    """yfinance 전용 환율 프로바이더 (KIS 키 없을 때 사용)."""

    def get_rate(self, pair: str) -> float:
        import yfinance as yf
        symbol = "KRW=X" if pair == "USDKRW" else f"{pair[:3]}{pair[3:]}=X"
        info = yf.Ticker(symbol).fast_info
        return float(info.last_price)


def get_fx_provider() -> FxProvider:
    """환경변수에 KIS 키가 있으면 KisFxProvider, 없으면 YFinanceFxProvider."""
    if os.getenv("KIS_APPKEY"):
        return KisFxProvider()
    return YFinanceFxProvider()
