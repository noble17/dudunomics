from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth.deps import current_user, CurrentUser
from core.ids import is_domestic
from core.data.prices_provider import fetch_ohlcv
from core.indicators import compute_indicators
from api.models import CandleItem, CandlesOut

router = APIRouter(prefix="/api/candles", tags=["candles"])

_PERIOD_DAYS: dict[str, int] = {
    "5D":  7,
    "1M":  35,
    "3M":  95,
    "6M":  185,
    "YTD": 370,
    "1Y":  370,
}
_INDICATOR_LOOKBACK_DAYS = 430


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
    display_start = date(end.year, 1, 1) if period.upper() == "YTD" else end - timedelta(days=days)
    fetch_start = end - timedelta(days=max(days, _INDICATOR_LOOKBACK_DAYS)) if indicators else display_start

    prices, _ = fetch_ohlcv([ticker.upper()], fetch_start, end, cache_only=True)
    if prices.empty:
        return CandlesOut(ticker=ticker.upper(), period=period.upper(), candles=[])

    symbol = ticker.upper()
    df = prices[symbol][["Open", "High", "Low", "Close", "Volume"]].dropna()
    df = _drop_incomplete_daily_rows(df, symbol)
    display_df = df[df.index.date >= display_start]
    if display_df.empty:
        display_df = df

    candles = [
        CandleItem(
            time=ts.strftime("%Y-%m-%d"),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=float(row["Volume"]),
        )
        for ts, row in display_df.iterrows()
    ]

    ind_data = None
    if indicators and len(df) >= 5:
        raw = compute_indicators(df)
        from api.models import IndicatorsData, IndicatorPoint
        display_from = display_df.index.min()
        ind_data = IndicatorsData(
            ma={k: [IndicatorPoint(**p) for p in _filter_points(v, display_from)] for k, v in raw["ma"].items()},
            bollinger={k: [IndicatorPoint(**p) for p in _filter_points(v, display_from)] for k, v in raw["bollinger"].items()},
            rsi=[IndicatorPoint(**p) for p in _filter_points(raw["rsi"], display_from)],
            macd={k: [IndicatorPoint(**p) for p in _filter_points(v, display_from)] for k, v in raw["macd"].items()},
            volume_ma=[IndicatorPoint(**p) for p in _filter_points(raw["volume_ma"], display_from)],
        )

    return CandlesOut(ticker=ticker.upper(), period=period.upper(), candles=candles, indicators=ind_data)


def _filter_points(points: list[dict], start) -> list[dict]:
    if start is None:
        return points
    start_text = start.strftime("%Y-%m-%d")
    return [point for point in points if point["time"] >= start_text]


def _drop_incomplete_daily_rows(df, ticker: str):
    if df.empty:
        return df
    cutoff = _latest_completed_trading_date(ticker)
    return df[df.index.date <= cutoff]


def _latest_completed_trading_date(ticker: str) -> date:
    if is_domestic(ticker):
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        today = now.date()
        return today if now.hour >= 16 else today - timedelta(days=1)

    now = datetime.now(ZoneInfo("America/New_York"))
    today = now.date()
    close_ready = now.hour > 16 or (now.hour == 16 and now.minute >= 30)
    return today if close_ready else today - timedelta(days=1)
