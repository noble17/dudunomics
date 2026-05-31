import logging
from fastapi import APIRouter, Depends
from core.auth.deps import current_user, CurrentUser
from core.prices.kis import KISPriceProvider
from core.prices.upbit import UpbitProvider
from core.fx import get_fx_provider
from core.data.market_indices import get_market_indices
from api.models import QuoteItem, QuotesOut

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quotes", tags=["quotes"])

_kis = KISPriceProvider()
_fx = get_fx_provider()
_upbit = UpbitProvider()


def _make_item(price: float, change_pct: float) -> QuoteItem:
    return QuoteItem(
        price=price,
        change_abs=round(price * change_pct / 100, 4),
        change_pct=round(change_pct, 4),
    )


@router.get("", response_model=QuotesOut)
def get_quotes(user: CurrentUser = Depends(current_user)):
    result = QuotesOut()

    # SPY / QQQ
    try:
        prices = _kis.get_current_prices(["SPY", "QQQ"])
        if "SPY" in prices:
            p = prices["SPY"]
            result.SPY = _make_item(p.current, p.change_pct or 0.0)
        if "QQQ" in prices:
            p = prices["QQQ"]
            result.QQQ = _make_item(p.current, p.change_pct or 0.0)
    except Exception as e:
        log.warning("SPY/QQQ 조회 실패: %s", e)

    # USD/KRW
    try:
        rate = _fx.get_rate("USDKRW")
        result.USDKRW = QuoteItem(price=rate, change_abs=0.0, change_pct=0.0)
    except Exception as e:
        log.warning("USDKRW 조회 실패: %s", e)

    # BTC
    try:
        btc = _upbit.get_btc_krw()
        result.BTC = _make_item(btc.current, btc.change_pct or 0.0)
    except Exception as e:
        log.warning("BTC 조회 실패: %s", e)

    # DJI / VIX / US10Y / WTI / GOLD
    try:
        indices = get_market_indices()
        for key, val in indices.items():
            if val is not None:
                setattr(result, key, _make_item(val["price"], val["change_pct"]))
    except Exception as e:
        log.warning("market_indices 조회 실패: %s", e)

    return result
