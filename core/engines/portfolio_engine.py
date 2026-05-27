"""포트폴리오 백테스트 엔진 (pandas/numpy 자체 구현)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

import pandas as pd

from core.engines.metrics import compute_metrics, per_ticker_contribution


@dataclass
class BacktestContext:
    prices: pd.DataFrame                      # MultiIndex (ticker, field)
    fundamentals: pd.DataFrame | None = None  # 2단계용
    market_index: pd.Series | None = None     # 3단계용
    cash: float = 10_000_000.0
    commission: float = 0.002
    rebalance: str = "none"                   # "none" | "monthly"
    risk_options: Any = None                  # 3단계 RiskOptions


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    weights_history: pd.DataFrame
    per_ticker_contribution: dict[str, float]
    rebalance_log: list[dict]
    metrics: dict
    warnings: list[str]


def _safe_price(close: pd.DataFrame, day: pd.Timestamp, ticker: str) -> float:
    try:
        v = close.loc[day, ticker]
        return float(v) if pd.notna(v) else 0.0
    except (KeyError, TypeError):
        return 0.0


def _get_close(prices: pd.DataFrame) -> pd.DataFrame:
    """prices MultiIndex에서 Close 컬럼 추출 (대소문자 방어)."""
    for col in ("Close", "close"):
        try:
            return prices.xs(col, axis=1, level=1)
        except KeyError:
            continue
    raise ValueError("Close 컬럼 없음")


def run_equal_weight_buy_hold(
    ctx: BacktestContext, warns: list[str] | None = None
) -> BacktestResult:
    """동일 비중 Buy & Hold 백테스트.

    모든 종목에 1/N 비중으로 첫 거래일 시초가(Close 대리) 매수 후 보유.
    수수료는 매수 시 1회 차감.
    """
    if warns is None:
        warns = []

    prices = ctx.prices
    tickers = prices.columns.get_level_values(0).unique().tolist()
    n = len(tickers)

    if n == 0:
        empty = pd.Series(dtype=float)
        return BacktestResult(
            equity_curve=empty,
            weights_history=pd.DataFrame(),
            per_ticker_contribution={},
            rebalance_log=[],
            metrics=compute_metrics(empty),
            warnings=warns + ["보유 종목 없음"],
        )

    try:
        close = _get_close(prices)
    except ValueError as e:
        empty = pd.Series(dtype=float)
        return BacktestResult(
            equity_curve=empty,
            weights_history=pd.DataFrame(),
            per_ticker_contribution={},
            rebalance_log=[],
            metrics=compute_metrics(empty),
            warnings=warns + [str(e)],
        )

    close = close[tickers].ffill().dropna(how="all")

    if ctx.risk_options is not None:
        from core.engines.risk import compute_weights
        first_ts = close.index[0]
        initial_weights = compute_weights(tickers, prices, first_ts, ctx.risk_options, ctx.market_index)
    else:
        weight = 1.0 / n
        initial_weights = pd.Series({t: weight for t in tickers})

    if close.empty:
        empty = pd.Series(dtype=float)
        return BacktestResult(
            equity_curve=empty,
            weights_history=pd.DataFrame(),
            per_ticker_contribution={},
            rebalance_log=[],
            metrics=compute_metrics(empty),
            warnings=warns + ["종가 데이터 없음"],
        )

    # 매수 1회 수수료 차감
    invested = ctx.cash * (1 - ctx.commission)

    first_close = close.iloc[0]
    shares: dict[str, float] = {}
    for t in tickers:
        price = float(first_close[t])
        w = float(initial_weights.get(t, 0.0))
        if price > 0 and w > 0:
            shares[t] = (invested * w) / price
        else:
            shares[t] = 0.0

    equity_parts = pd.DataFrame({t: close[t] * shares[t] for t in tickers})
    equity_curve = equity_parts.sum(axis=1)

    # 일별 비중 (0으로 나누기 방지)
    total = equity_curve.replace(0, float("nan"))
    weights_history = equity_parts.div(total, axis=0).fillna(0.0)

    if ctx.risk_options is not None and ctx.risk_options.market_filter:
        cash_weight = (1.0 - weights_history.sum(axis=1)).clip(lower=0.0)
        weights_history["cash_weight"] = cash_weight

    contribution = per_ticker_contribution(prices, tickers, initial_weights, invested)

    return BacktestResult(
        equity_curve=equity_curve,
        weights_history=weights_history,
        per_ticker_contribution=contribution,
        rebalance_log=[],
        metrics=compute_metrics(equity_curve),
        warnings=warns,
    )


def run_with_rebalance(
    ctx: BacktestContext,
    selector: Callable[[list[str], date], dict[str, float]],
    warns: list[str] | None = None,
) -> BacktestResult:
    """월별 리밸런싱 백테스트.

    selector(tickers, as_of) → {ticker: weight} 매 월말 시그널 날짜 기준 호출.
    다음 거래일 open(Close 대리)에 매도·매수 체결. 양방향 수수료 적용.
    """
    from core.engines.rebalance import monthly_signal_dates, next_trading_day

    if warns is None:
        warns = []

    if ctx.prices.empty:
        empty = pd.Series(dtype=float)
        return BacktestResult(
            equity_curve=empty,
            weights_history=pd.DataFrame(),
            per_ticker_contribution={},
            rebalance_log=[],
            metrics=compute_metrics(empty),
            warnings=warns + ["보유 종목 없음"],
        )

    try:
        close = _get_close(ctx.prices)
    except ValueError as e:
        empty = pd.Series(dtype=float)
        return BacktestResult(
            equity_curve=empty,
            weights_history=pd.DataFrame(),
            per_ticker_contribution={},
            rebalance_log=[],
            metrics=compute_metrics(empty),
            warnings=warns + [str(e)],
        )

    close = close.ffill().dropna(how="all")
    if close.empty:
        empty = pd.Series(dtype=float)
        return BacktestResult(
            equity_curve=empty,
            weights_history=pd.DataFrame(),
            per_ticker_contribution={},
            rebalance_log=[],
            metrics=compute_metrics(empty),
            warnings=warns + ["종가 데이터 없음"],
        )

    trading_days = close.index
    all_tickers = close.columns.tolist()
    commission = ctx.commission
    first_day = trading_days[0]

    # 월말 시그널 → 다음 거래일 진입 맵핑 (첫 거래일 제외)
    rebalance_entries: dict[pd.Timestamp, pd.Timestamp] = {}
    for sig in monthly_signal_dates(trading_days):
        entry = next_trading_day(sig, trading_days)
        if entry is not None and entry != first_day:
            rebalance_entries[entry] = sig

    # 초기 매수 (첫 거래일)
    initial_target = selector(all_tickers, first_day.date())
    total_w = sum(initial_target.values()) or 1.0
    initial_target = {t: w / total_w for t, w in initial_target.items() if w > 0}
    selected = list(initial_target.keys())
    if ctx.risk_options is not None and selected:
        from core.engines.risk import compute_weights
        risk_w = compute_weights(selected, ctx.prices, first_day, ctx.risk_options, ctx.market_index)
        initial_target = risk_w.to_dict()

    shares: dict[str, float] = {}
    invested = ctx.cash * (1 - commission)
    for t, w in initial_target.items():
        price = _safe_price(close, first_day, t)
        if price > 0:
            shares[t] = (invested * w) / price

    equity_values: list[float] = []
    weights_records: list[dict] = []
    rebalance_log: list[dict] = []

    for day in trading_days:
        if day in rebalance_entries:
            sig_date = rebalance_entries[day]

            # 청산 (매도 수수료)
            sell_value = sum(_safe_price(close, day, t) * shares.get(t, 0) for t in shares)
            proceeds = sell_value * (1 - commission)

            # 새 목표 비중 계산
            new_target = selector(all_tickers, sig_date.date())
            total_w = sum(new_target.values()) or 1.0
            new_weights = {t: w / total_w for t, w in new_target.items() if w > 0}
            new_selected = list(new_weights.keys())
            if ctx.risk_options is not None and new_selected:
                from core.engines.risk import compute_weights
                risk_w = compute_weights(new_selected, ctx.prices, day, ctx.risk_options, ctx.market_index)
                new_weights = risk_w.to_dict()

            # 재매수 (매수 수수료)
            shares = {}
            invest = proceeds * (1 - commission)
            for t, w in new_weights.items():
                price = _safe_price(close, day, t)
                if price > 0:
                    shares[t] = (invest * w) / price

            rebalance_log.append({
                "date": str(day.date()),
                "signal_date": str(sig_date.date()),
                "holdings": list(shares.keys()),
                "weights": {t: round(new_weights.get(t, 0.0), 4) for t in shares},
                "portfolio_value_before": round(sell_value, 0),
                **({"cash_weight": round(max(0.0, 1.0 - sum(new_weights.values())), 4)} if ctx.risk_options is not None else {}),
            })

        # 일별 자산 가치
        eq = sum(_safe_price(close, day, t) * shares.get(t, 0.0) for t in shares)
        equity_values.append(eq)

        # 일별 비중
        total_eq = eq if eq > 0 else float("nan")
        weights_records.append({
            t: _safe_price(close, day, t) * shares[t] / total_eq
            for t in shares
        })

    equity_curve = pd.Series(equity_values, index=trading_days)
    weights_history = pd.DataFrame(weights_records, index=trading_days).fillna(0.0)
    if ctx.risk_options is not None and ctx.risk_options.market_filter:
        weights_history["cash_weight"] = (1.0 - weights_history.sum(axis=1)).clip(lower=0.0)

    contribution = per_ticker_contribution(
        ctx.prices,
        all_tickers,
        pd.Series({t: 1.0 / len(all_tickers) for t in all_tickers}),
        ctx.cash,
    )

    return BacktestResult(
        equity_curve=equity_curve,
        weights_history=weights_history,
        per_ticker_contribution=contribution,
        rebalance_log=rebalance_log,
        metrics=compute_metrics(equity_curve),
        warnings=warns,
    )
