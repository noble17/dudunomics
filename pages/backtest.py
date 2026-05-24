"""SMA 백테스트 페이지."""
from datetime import date, timedelta

import dash
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from backtesting import Backtest
from dash import Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate

import core.repository as repo
from core.strategies.base import get_strategy, list_strategies

# 전략 등록
import core.strategies.sma_crossover  # noqa: F401

dash.register_page(__name__, path="/backtest", name="Backtest", order=3)


def layout():
    strategies = list_strategies()
    strat_options = [{"label": s["name"], "value": s["name"]} for s in strategies]
    default_strat = strategies[0]["name"] if strategies else None

    return html.Div([
        html.H2("백테스트 (단순 SMA)", className="page-title"),

        html.Div([
            html.Div([
                html.Label("티커 (yfinance 형식)"),
                dcc.Input(id="bt-ticker", type="text", value="005930.KS",
                          style={"width": "180px"}),
            ], style={"marginBottom": "12px"}),

            html.Div([
                html.Label("기간"),
                dcc.DatePickerRange(
                    id="bt-period",
                    start_date=(date.today() - timedelta(days=365 * 3)).isoformat(),
                    end_date=date.today().isoformat(),
                    max_date_allowed=date.today().isoformat(),
                    style={"marginLeft": "8px"},
                ),
            ], style={"marginBottom": "12px"}),

            html.Div([
                html.Label("전략"),
                dcc.Dropdown(id="bt-strategy", options=strat_options, value=default_strat,
                             clearable=False, style={"width": "220px", "marginLeft": "8px"}),
            ], style={"marginBottom": "12px", "display": "flex", "alignItems": "center"}),

            html.Div(id="bt-params-form", style={"marginBottom": "12px"}),

            html.Button("실행", id="bt-run-btn", n_clicks=0,
                        style={"backgroundColor": "#4CAF50", "color": "white",
                               "border": "none", "padding": "8px 20px", "cursor": "pointer"}),
            html.Span(id="bt-status", style={"marginLeft": "12px", "color": "#999"}),
        ], style={"background": "white", "padding": "20px", "borderRadius": "8px",
                  "boxShadow": "0 1px 4px rgba(0,0,0,.1)", "marginBottom": "24px"}),

        html.Div(id="bt-result"),
    ], style={"maxWidth": "1100px", "margin": "0 auto", "padding": "24px"})


@callback(
    Output("bt-params-form", "children"),
    Input("bt-strategy", "value"),
)
def render_params_form(strategy_name):
    if not strategy_name:
        return []
    strat = get_strategy(strategy_name)
    inputs = []
    for key, schema in strat.params_schema.items():
        inputs.append(html.Div([
            html.Label(schema["label"], style={"width": "120px", "display": "inline-block"}),
            dcc.Input(
                id={"type": "bt-param", "key": key},
                type="number",
                value=schema["default"],
                min=schema.get("min"),
                max=schema.get("max"),
                style={"width": "80px"},
            ),
        ], style={"marginBottom": "6px"}))
    return inputs


@callback(
    Output("bt-result", "children"),
    Output("bt-status", "children"),
    Input("bt-run-btn", "n_clicks"),
    State("bt-ticker", "value"),
    State("bt-period", "start_date"),
    State("bt-period", "end_date"),
    State("bt-strategy", "value"),
    State({"type": "bt-param", "key": dash.ALL}, "value"),
    State({"type": "bt-param", "key": dash.ALL}, "id"),
    prevent_initial_call=True,
)
def run_backtest(n, ticker, start_date, end_date, strategy_name, param_values, param_ids):
    if not n:
        raise PreventUpdate

    ticker = (ticker or "").strip()
    if not ticker:
        return html.Div("티커를 입력하세요.", style={"color": "red"}), ""

    params = {pid["key"]: val for pid, val in zip(param_ids, param_values)}

    try:
        df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
        if df.empty:
            return html.Div(f"{ticker} 데이터 없음", style={"color": "red"}), ""

        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()

        strat = get_strategy(strategy_name)
        bt_class = strat.to_backtesting_class(params)
        bt_obj = Backtest(df, bt_class, cash=10_000_000, commission=0.002)
        stats = bt_obj.run()

        equity = stats._equity_curve["Equity"]
        curve_data = [{"ts": str(t), "equity": float(v)} for t, v in equity.items()]

        total_return = float(stats["Return [%]"])
        mdd = float(stats["Max. Drawdown [%]"])
        sharpe = float(stats.get("Sharpe Ratio", 0) or 0)

        run_id = repo.insert_backtest_run(
            strategy=strategy_name, params=params, ticker=ticker,
            period_start=pd.Timestamp(start_date).date(),
            period_end=pd.Timestamp(end_date).date(),
            total_return=total_return, mdd=mdd, sharpe=sharpe,
            equity_curve=curve_data,
        )

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[d["ts"] for d in curve_data],
            y=[d["equity"] for d in curve_data],
            mode="lines", name="자산곡선",
        ))
        fig.update_layout(title=f"{ticker} — {strategy_name} 백테스트", height=400,
                          yaxis_title="자산(KRW)")

        kpi_style = {"display": "flex", "gap": "16px", "marginBottom": "16px"}
        result = html.Div([
            html.Div([
                _kpi("총 수익률", f"{total_return:+.2f}%"),
                _kpi("MDD", f"{mdd:.2f}%"),
                _kpi("Sharpe", f"{sharpe:.2f}"),
            ], style=kpi_style),
            dcc.Graph(figure=fig),
            html.Div(f"Run ID: {run_id}", style={"color": "#999", "fontSize": "12px"}),
        ])
        return result, "완료"

    except Exception as e:
        return html.Div(f"오류: {e}", style={"color": "red"}), ""


def _kpi(label, value):
    return html.Div([
        html.Div(label, style={"fontSize": "12px", "color": "#757575"}),
        html.Div(value, style={"fontSize": "20px", "fontWeight": "bold"}),
    ], style={"background": "white", "borderRadius": "8px", "padding": "12px 16px",
              "boxShadow": "0 1px 4px rgba(0,0,0,.1)", "minWidth": "140px"})
