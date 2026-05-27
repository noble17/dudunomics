from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
import pandas as pd
import yfinance as yf
from backtesting import Backtest

from api.auth import require_auth
from api.models import BacktestRunIn, BacktestRunOut, StrategiesOut
import core.repository as repo
from core.strategies.base import get_strategy, list_strategies
import core.strategies.sma_crossover        # noqa: F401 — registers SMA Crossover
import core.strategies.equal_weight         # noqa: F401 — registers Equal Weight
import core.strategies.factor_rebalance     # noqa: F401 — registers Forward 팩터 리밸런싱
from core.data.prices_provider import fetch_ohlcv
from core.engines.portfolio_engine import BacktestContext

router = APIRouter(prefix="/api/backtest", tags=["backtest"], dependencies=[Depends(require_auth)])


@router.get("/strategies", response_model=list[StrategiesOut])
def get_strategies():
    return list_strategies()


@router.post("/run", response_model=BacktestRunOut)
def run_backtest(body: BacktestRunIn):
    try:
        strat = get_strategy(body.strategy)

        if strat.engine == "portfolio":
            return _run_portfolio(body, strat)
        else:
            return _run_backtesting(body, strat)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _run_backtesting(body: BacktestRunIn, strat) -> BacktestRunOut:
    """기존 backtesting.py 라이브러리 경로 — 단일 티커 SMA 등."""
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

    return BacktestRunOut(
        id=run_id,
        ticker=body.ticker,
        tickers=body.tickers,
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


def _run_portfolio(body: BacktestRunIn, strat) -> BacktestRunOut:
    """자체 portfolio 엔진 경로 — Equal Weight 등 멀티 자산 전략."""
    tickers = body.tickers or []
    if not tickers:
        raise HTTPException(status_code=422, detail="tickers 필수")

    prices, warns = fetch_ohlcv(tickers, body.period_start, body.period_end)

    if prices.empty:
        detail = "; ".join(warns) if warns else "가격 데이터 없음"
        raise HTTPException(status_code=422, detail=detail)

    market_index = None
    if body.risk_options is not None and body.risk_options.market_filter:
        from core.data.index_provider import fetch_market_index, resolve_index_symbol
        index_sym = resolve_index_symbol(tickers, body.risk_options.market_filter_index)
        market_index = fetch_market_index(index_sym, body.period_start, body.period_end)

    ctx = BacktestContext(
        prices=prices,
        risk_options=body.risk_options,
        market_index=market_index,
    )
    result = strat.run_portfolio(ctx, body.params)
    result.warnings = warns + result.warnings

    # equity curve 직렬화
    curve_data = [
        {"ts": str(t.date()), "equity": float(v)}
        for t, v in result.equity_curve.items()
    ]

    # weights_history 직렬화 (날짜 + 종목별 비중)
    wh_data: list[dict] = []
    for ts, row in result.weights_history.iterrows():
        entry = {"ts": str(ts.date())}
        entry.update({t: round(float(row[t]), 6) for t in row.index})
        wh_data.append(entry)

    m = result.metrics
    run_id = repo.insert_backtest_run(
        strategy=body.strategy,
        params=body.params,
        ticker=tickers[0],
        period_start=body.period_start,
        period_end=body.period_end,
        total_return=m.get("total_return", 0.0),
        mdd=m.get("mdd", 0.0),
        sharpe=m.get("sharpe", 0.0),
        equity_curve=curve_data,
        tickers=tickers,
        cagr=m.get("cagr"),
        weights_history=wh_data,
        contribution=result.per_ticker_contribution,
        warnings=result.warnings,
        risk_options=body.risk_options.model_dump() if body.risk_options else None,
    )

    return BacktestRunOut(
        id=run_id,
        ticker=tickers[0],
        tickers=tickers,
        strategy=body.strategy,
        params=body.params,
        period_start=body.period_start,
        period_end=body.period_end,
        total_return=m.get("total_return", 0.0),
        mdd=m.get("mdd", 0.0),
        sharpe=m.get("sharpe", 0.0),
        cagr=m.get("cagr"),
        equity_curve=curve_data,
        per_ticker_contribution=result.per_ticker_contribution,
        weights_history=wh_data,
        rebalance_log=result.rebalance_log,
        warnings=result.warnings,
        created_at=datetime.now(),
    )
