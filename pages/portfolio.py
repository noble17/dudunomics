"""Portfolio 페이지 — KPI + 비중 차트 + 보유종목 테이블 + 30일 수익률 곡선 (30초 갱신)."""
import json
from datetime import datetime

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

import core.repository as repo
from core.fx import get_fx_provider
from core.ids import detect_currency
from core.prices.kis import KISPriceProvider

dash.register_page(__name__, path="/", name="Portfolio", order=1)

_price_provider = KISPriceProvider()
_fx_provider = get_fx_provider()


def layout():
    return html.Div([
        dcc.Interval(id="portfolio-interval", interval=30_000, n_intervals=0),

        html.Div([
            html.H2("포트폴리오", style={"marginBottom": "4px"}),
            html.Div([
                html.Label("기준 통화:"),
                dcc.RadioItems(
                    id="currency-toggle",
                    options=[{"label": "KRW", "value": "KRW"}, {"label": "USD", "value": "USD"}],
                    value="KRW",
                    inline=True,
                    style={"marginLeft": "8px"},
                ),
                html.Label("비중 분모:", style={"marginLeft": "24px"}),
                dcc.RadioItems(
                    id="weight-toggle",
                    options=[
                        {"label": "주식만", "value": "equity"},
                        {"label": "주식+현금", "value": "total"},
                    ],
                    value="equity",
                    inline=True,
                    style={"marginLeft": "8px"},
                ),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px"}),
        ]),

        # KPI 카드 4개
        html.Div(id="kpi-cards", style={"display": "flex", "gap": "16px", "marginBottom": "24px"}),

        html.Div([
            # 비중 파이차트
            html.Div(dcc.Graph(id="weight-pie"), style={"flex": "1"}),
            # 30일 수익률 곡선
            html.Div(dcc.Graph(id="equity-curve"), style={"flex": "2"}),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "24px"}),

        # 보유종목 테이블
        dash_table.DataTable(
            id="holdings-display",
            columns=[
                {"name": "티커", "id": "ticker"},
                {"name": "종목명", "id": "name"},
                {"name": "수량", "id": "quantity"},
                {"name": "평균단가", "id": "avg_price"},
                {"name": "현재가", "id": "current_price"},
                {"name": "평가금액", "id": "market_value"},
                {"name": "수익률(%)", "id": "return_pct"},
                {"name": "비중(%)", "id": "weight_pct"},
            ],
            style_cell={"textAlign": "right", "padding": "8px"},
            style_cell_conditional=[{"if": {"column_id": ["ticker", "name"]},
                                      "textAlign": "left"}],
            style_header={"fontWeight": "bold", "backgroundColor": "#f5f5f5"},
            style_data_conditional=[
                {"if": {"filter_query": "{return_pct} > 0", "column_id": "return_pct"},
                 "color": "#e53935"},
                {"if": {"filter_query": "{return_pct} < 0", "column_id": "return_pct"},
                 "color": "#1e88e5"},
            ],
        ),

        html.Div(id="last-updated", style={"marginTop": "8px", "color": "#999", "fontSize": "12px"}),
    ], style={"maxWidth": "1200px", "margin": "0 auto", "padding": "24px"})


@callback(
    Output("kpi-cards", "children"),
    Output("weight-pie", "figure"),
    Output("equity-curve", "figure"),
    Output("holdings-display", "data"),
    Output("last-updated", "children"),
    Input("portfolio-interval", "n_intervals"),
    Input("currency-toggle", "value"),
    Input("weight-toggle", "value"),
)
def refresh(_, currency, weight_mode):
    holdings = repo.get_holdings()
    if not holdings:
        return [_empty_kpi()], go.Figure(), go.Figure(), [], "보유 종목 없음"

    tickers = [h["ticker"] for h in holdings]
    prices = _price_provider.get_current_prices(tickers)

    usdkrw = _get_usdkrw()
    cash_krw = float(repo.get_meta("cash_krw") or 0)
    cash_usd = float(repo.get_meta("cash_usd") or 0)
    cash_total_krw = cash_krw + cash_usd * usdkrw

    rows = []
    total_equity_krw = 0.0

    for h in holdings:
        ticker = h["ticker"]
        if ticker not in prices:
            continue
        p = prices[ticker]
        mv = p.current * h["quantity"]
        mv_krw = mv if p.currency == "KRW" else mv * usdkrw
        mv_disp = mv_krw if currency == "KRW" else mv_krw / usdkrw

        cost = h["avg_price"] * h["quantity"]
        ret_pct = (p.current - h["avg_price"]) / h["avg_price"] * 100 if h["avg_price"] else 0

        total_equity_krw += mv_krw
        rows.append({
            "ticker": ticker,
            "name": h["name"],
            "quantity": h["quantity"],
            "avg_price": _fmt(h["avg_price"]),
            "current_price": _fmt(p.current),
            "market_value": _fmt(mv_disp),
            "_mv_krw": mv_krw,
            "return_pct": round(ret_pct, 2),
        })

    total_with_cash_krw = total_equity_krw + cash_total_krw
    denom_krw = total_equity_krw if weight_mode == "equity" else total_with_cash_krw

    for r in rows:
        r["weight_pct"] = round(r["_mv_krw"] / denom_krw * 100, 2) if denom_krw else 0
        del r["_mv_krw"]

    # KPI
    disp = lambda v: v if currency == "KRW" else v / usdkrw
    sym = "₩" if currency == "KRW" else "$"
    total_cost_krw = sum(
        h["avg_price"] * h["quantity"] * (1 if detect_currency(h["ticker"]) == "KRW" else usdkrw)
        for h in holdings
    )
    total_ret = (total_equity_krw - total_cost_krw) / total_cost_krw * 100 if total_cost_krw else 0

    kpis = [
        _kpi("평가액", f"{sym}{disp(total_equity_krw):,.0f}"),
        _kpi("현금포함", f"{sym}{disp(total_with_cash_krw):,.0f}"),
        _kpi("수익률", f"{total_ret:+.2f}%", color="#e53935" if total_ret > 0 else "#1e88e5"),
        _kpi("현금", f"{sym}{disp(cash_total_krw):,.0f}"),
    ]

    # 비중 파이
    pie = go.Figure(go.Pie(
        labels=[r["ticker"] for r in rows],
        values=[r["weight_pct"] for r in rows],
        hole=0.4,
    ))
    pie.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=280,
                      title="비중", showlegend=True)

    # 30일 수익률 곡선
    curve_fig = _build_equity_curve(currency, usdkrw, cash_total_krw)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return kpis, pie, curve_fig, rows, f"마지막 갱신: {now}"


def _get_usdkrw() -> float:
    cached = repo.get_latest_fx_rate("USDKRW")
    if cached:
        return cached
    try:
        rate = _fx_provider.get_rate("USDKRW")
        return rate
    except Exception:
        return 1350.0


def _build_equity_curve(currency: str, usdkrw: float, cash_total_krw: float) -> go.Figure:
    snapshots = repo.get_snapshots(limit=400)
    if not snapshots:
        fig = go.Figure()
        fig.update_layout(title="30일 수익률 곡선", height=280,
                          margin=dict(t=30, b=0, l=0, r=0))
        return fig

    df = pd.DataFrame(snapshots).sort_values("ts")
    col = "total_equity_krw" if currency == "KRW" else "total_equity_usd"
    sym = "₩" if currency == "KRW" else "$"
    fig = go.Figure(go.Scatter(x=df["ts"], y=df[col], mode="lines", name="평가액"))
    fig.update_layout(title="수익률 곡선", height=280,
                      margin=dict(t=30, b=0, l=0, r=0),
                      yaxis_title=sym)
    return fig


def _kpi(label: str, value: str, color: str = "#212121") -> html.Div:
    return html.Div([
        html.Div(label, style={"fontSize": "12px", "color": "#757575"}),
        html.Div(value, style={"fontSize": "22px", "fontWeight": "bold", "color": color}),
    ], style={
        "background": "white", "borderRadius": "8px", "padding": "16px 20px",
        "boxShadow": "0 1px 4px rgba(0,0,0,.1)", "minWidth": "160px",
    })


def _empty_kpi() -> html.Div:
    return html.Div("Holdings 탭에서 보유 종목을 추가하세요.",
                    style={"color": "#999", "padding": "16px"})


def _fmt(v) -> str:
    try:
        f = float(v)
        return f"{f:,.2f}" if f < 100_000 else f"{f:,.0f}"
    except Exception:
        return str(v)
