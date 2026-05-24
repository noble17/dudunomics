"""KIS Open API 시세 프로바이더 — 국내 + 해외."""
import logging
import os
from functools import lru_cache

from core.ids import detect_currency, is_domestic, to_kis_domestic, to_kis_overseas
from core.prices.base import Price, PriceProvider

log = logging.getLogger(__name__)


def _get_api():
    """python-kis API 객체를 싱글턴으로 반환."""
    try:
        import mojito  # noqa: F401 — python-kis가 mojito 기반인지 확인용
    except ImportError:
        pass
    try:
        from pykis import PyKis
        env = os.getenv("KIS_ENV", "real")
        api = PyKis(
            appkey=os.environ["KIS_APPKEY"],
            secretkey=os.environ["KIS_SECRETKEY"],
            account=os.environ["KIS_ACCOUNT_NO"],
            virtual=env != "real",
        )
        return api
    except Exception as e:
        log.warning("KIS API 초기화 실패: %s", e)
        return None


class KISPriceProvider(PriceProvider):
    """KIS Open API로 국내·해외 현재가를 조회한다.

    KIS 초기화 실패 또는 API 오류 시 yfinance 폴백을 사용한다.
    """

    def get_current_price(self, ticker: str) -> Price:
        prices = self.get_current_prices([ticker])
        if ticker in prices:
            return prices[ticker]
        raise RuntimeError(f"시세 조회 실패: {ticker}")

    def get_current_prices(self, tickers: list[str]) -> dict[str, Price]:
        result: dict[str, Price] = {}
        api = _get_api()

        for ticker in tickers:
            try:
                if api is not None:
                    price = (
                        self._fetch_domestic(api, ticker)
                        if is_domestic(ticker)
                        else self._fetch_overseas(api, ticker)
                    )
                else:
                    price = self._fetch_yfinance(ticker)
                result[ticker] = price
            except Exception as e:
                log.warning("시세 조회 실패 (%s): %s — yfinance 폴백", ticker, e)
                try:
                    result[ticker] = self._fetch_yfinance(ticker)
                except Exception as e2:
                    log.error("yfinance 폴백도 실패 (%s): %s", ticker, e2)
        return result

    def _fetch_domestic(self, api, ticker: str) -> Price:
        code, _ = to_kis_domestic(ticker)
        stock = api.stock(code)
        q = stock.quote()
        return Price(
            ticker=ticker,
            current=float(q.price),
            currency="KRW",
            change_pct=float(q.change_rate) if hasattr(q, "change_rate") else None,
        )

    def _fetch_overseas(self, api, ticker: str) -> Price:
        exchange, code = to_kis_overseas(ticker)
        stock = api.stock(f"{exchange}:{code}")
        q = stock.quote()
        return Price(
            ticker=ticker,
            current=float(q.price),
            currency="USD",
            change_pct=float(q.change_rate) if hasattr(q, "change_rate") else None,
        )

    def _fetch_yfinance(self, ticker: str) -> Price:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        current = float(info.last_price)
        return Price(
            ticker=ticker,
            current=current,
            currency=detect_currency(ticker),
        )
