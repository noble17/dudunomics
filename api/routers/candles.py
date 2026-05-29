from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth.deps import current_user, CurrentUser
from core.data.prices_provider import fetch_ohlcv
from core.indicators import compute_indicators
from api.models import CandleItem, CandlesOut

router = APIRouter(prefix="/api/candles", tags=["candles"])

_PERIOD_DAYS: dict[str, int] = {
    "5D":  7,
    "1M":  35,
    "3M":  95,
    "6M":  185,
    "1Y":  370,
}


@router.get("", response_model=CandlesOut)
def get_candles(
    ticker: str = Query(..., description="티커 심볼 (예: SPY)"),
    period: str = Query("3M", description="기간: 5D | 1M | 3M | 6M | 1Y"),
    indicators: bool = Query(False, description="지표 데이터 포함 여부"),
    user: CurrentUser = Depends(current_user),
) -> CandlesOut:
    days = _PERIOD_DAYS.get(period.upper())
    if days is None:
        raise HTTPException(status_code=422, detail=f"지원하지 않는 period: {period}. 5D|1M|3M|6M|1Y 중 선택.")

    end = date.today()
    start = end - timedelta(days=days)

    prices, _ = fetch_ohlcv([ticker.upper()], start, end)
    if prices.empty:
        return CandlesOut(ticker=ticker.upper(), period=period.upper(), candles=[])

    df = prices[ticker.upper()][["Open", "High", "Low", "Close", "Volume"]].dropna()

    candles = [
        CandleItem(
            time=ts.strftime("%Y-%m-%d"),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=float(row["Volume"]),
        )
        for ts, row in df.iterrows()
    ]

    ind_data = None
    if indicators and len(df) >= 5:
        raw = compute_indicators(df)
        from api.models import IndicatorsData, IndicatorPoint
        ind_data = IndicatorsData(
            ma={k: [IndicatorPoint(**p) for p in v] for k, v in raw["ma"].items()},
            bollinger={k: [IndicatorPoint(**p) for p in v] for k, v in raw["bollinger"].items()},
            rsi=[IndicatorPoint(**p) for p in raw["rsi"]],
            macd={k: [IndicatorPoint(**p) for p in v] for k, v in raw["macd"].items()},
            volume_ma=[IndicatorPoint(**p) for p in raw["volume_ma"]],
        )

    return CandlesOut(ticker=ticker.upper(), period=period.upper(), candles=candles, indicators=ind_data)
