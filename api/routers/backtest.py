from fastapi import APIRouter, Depends, HTTPException
import pandas as pd
import yfinance as yf
from backtesting import Backtest

from api.auth import require_auth
from api.models import BacktestRunIn, BacktestRunOut, StrategiesOut
import core.repository as repo
from core.strategies.base import get_strategy, list_strategies
import core.strategies.sma_crossover  # registers strategy

router = APIRouter(prefix="/api/backtest", tags=["backtest"], dependencies=[Depends(require_auth)])


@router.get("/strategies", response_model=list[StrategiesOut])
def get_strategies():
    return list_strategies()


@router.post("/run", response_model=BacktestRunOut)
def run_backtest(body: BacktestRunIn):
    try:
        df = yf.download(
            body.ticker,
            start=str(body.period_start),
            end=str(body.period_end),
            progress=False,
            auto_adjust=True,
        )
        if df.empty:
            raise HTTPException(status_code=422, detail=f"{body.ticker} 데이터 없음")

        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()

        strat = get_strategy(body.strategy)
        bt_class = strat.to_backtesting_class(body.params)
        bt_obj = Backtest(df, bt_class, cash=10_000_000, commission=0.002)
        stats = bt_obj.run()

        equity = stats._equity_curve["Equity"]
        curve_data = [{"ts": str(t.date()), "equity": float(v)} for t, v in equity.items()]

        run_id = repo.insert_backtest_run(
            strategy=body.strategy,
            params=body.params,
            ticker=body.ticker,
            period_start=body.period_start,
            period_end=body.period_end,
            total_return=float(stats["Return [%]"]),
            mdd=float(stats["Max. Drawdown [%]"]),
            sharpe=float(stats.get("Sharpe Ratio") or 0),
            equity_curve=curve_data,
        )

        from datetime import datetime
        return BacktestRunOut(
            id=run_id,
            ticker=body.ticker,
            strategy=body.strategy,
            params=body.params,
            period_start=body.period_start,
            period_end=body.period_end,
            total_return=float(stats["Return [%]"]),
            mdd=float(stats["Max. Drawdown [%]"]),
            sharpe=float(stats.get("Sharpe Ratio") or 0),
            equity_curve=curve_data,
            created_at=datetime.now(),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
