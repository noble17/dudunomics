"""Holdings Editor 페이지 — 보유 종목 추가/수정/삭제 + 현금 관리."""
import json
from pathlib import Path

import dash
from dash import Input, Output, State, callback, dash_table, dcc, html
from dash.exceptions import PreventUpdate

import core.repository as repo

dash.register_page(__name__, path="/holdings", name="Holdings Editor", order=2)

_COLUMNS = [
    {"name": "티커 (yfinance)", "id": "ticker", "editable": True},
    {"name": "종목명", "id": "name", "editable": True},
    {"name": "통화", "id": "currency", "editable": True, "presentation": "dropdown"},
    {"name": "수량", "id": "quantity", "editable": True, "type": "numeric"},
    {"name": "평균단가", "id": "avg_price", "editable": True, "type": "numeric"},
]

layout = html.Div([
    html.H2("보유 종목 편집", className="page-title"),

    html.Div([
        html.H4("현금"),
        html.Div([
            html.Label("현금(KRW)"),
            dcc.Input(id="cash-krw", type="number", placeholder="0", debounce=True,
                      style={"width": "160px", "marginRight": "16px"}),
            html.Label("현금(USD)"),
            dcc.Input(id="cash-usd", type="number", placeholder="0", debounce=True,
                      style={"width": "120px"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "8px",
                  "marginBottom": "16px"}),
    ]),

    dash_table.DataTable(
        id="holdings-table",
        columns=_COLUMNS,
        data=[],
        editable=True,
        row_deletable=True,
        dropdown={
            "currency": {
                "options": [
                    {"label": "KRW", "value": "KRW"},
                    {"label": "USD", "value": "USD"},
                ]
            }
        },
        style_cell={"textAlign": "left", "padding": "8px"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f5f5f5"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"}
        ],
    ),

    html.Div([
        html.Button("+ 행 추가", id="add-row-btn", n_clicks=0,
                    style={"marginRight": "8px"}),
        html.Button("저장", id="save-btn", n_clicks=0,
                    style={"backgroundColor": "#2196F3", "color": "white",
                           "border": "none", "padding": "8px 16px", "cursor": "pointer"}),
        html.Span(id="save-status", style={"marginLeft": "12px", "color": "green"}),
    ], style={"marginTop": "12px"}),

    dcc.Store(id="holdings-init"),
], style={"maxWidth": "960px", "margin": "0 auto", "padding": "24px"})


@callback(
    Output("holdings-table", "data"),
    Output("cash-krw", "value"),
    Output("cash-usd", "value"),
    Input("holdings-init", "data"),
)
def load_holdings(_):
    rows = repo.get_holdings()
    data = [
        {"ticker": r["ticker"], "name": r["name"], "currency": r["currency"],
         "quantity": r["quantity"], "avg_price": r["avg_price"]}
        for r in rows
    ]
    cash_krw = float(repo.get_meta("cash_krw") or 0)
    cash_usd = float(repo.get_meta("cash_usd") or 0)
    return data, cash_krw, cash_usd


@callback(
    Output("holdings-table", "data", allow_duplicate=True),
    Input("add-row-btn", "n_clicks"),
    State("holdings-table", "data"),
    prevent_initial_call=True,
)
def add_row(n, rows):
    if not n:
        raise PreventUpdate
    rows = rows or []
    rows.append({"ticker": "", "name": "", "currency": "KRW", "quantity": 0, "avg_price": 0})
    return rows


@callback(
    Output("save-status", "children"),
    Input("save-btn", "n_clicks"),
    State("holdings-table", "data"),
    State("cash-krw", "value"),
    State("cash-usd", "value"),
    prevent_initial_call=True,
)
def save_holdings(n, rows, cash_krw, cash_usd):
    if not n:
        raise PreventUpdate

    existing = {r["ticker"] for r in repo.get_holdings()}
    new_tickers = set()

    for row in (rows or []):
        ticker = (row.get("ticker") or "").strip()
        if not ticker:
            continue
        try:
            repo.upsert_holding(
                ticker=ticker,
                name=row.get("name") or ticker,
                currency=row.get("currency") or "KRW",
                quantity=float(row.get("quantity") or 0),
                avg_price=float(row.get("avg_price") or 0),
            )
            new_tickers.add(ticker)
        except Exception as e:
            return f"오류: {e}"

    for removed in existing - new_tickers:
        repo.delete_holding(removed)

    repo.set_meta("cash_krw", str(float(cash_krw or 0)))
    repo.set_meta("cash_usd", str(float(cash_usd or 0)))

    _backup_json()
    return "저장 완료 ✓"


def _backup_json():
    path = Path("data/holdings.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    holdings = repo.get_holdings()
    payload = {
        "holdings": [
            {"ticker": r["ticker"], "name": r["name"], "currency": r["currency"],
             "quantity": r["quantity"], "avg_price": r["avg_price"]}
            for r in holdings
        ],
        "cash_krw": float(repo.get_meta("cash_krw") or 0),
        "cash_usd": float(repo.get_meta("cash_usd") or 0),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
