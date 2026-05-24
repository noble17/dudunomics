"""Dash 엔트리포인트 — 라우팅 + 스케줄러 부트."""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

import dash
from dash import Dash, Input, Output, dcc, html

from core.auth import apply_auth
from core.repository import get_engine
from core.scheduler import create_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# DB 초기화 (스키마 생성)
get_engine()

app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    title="Dudunomics",
    update_title=None,
)

apply_auth(app)

app.layout = html.Div([
    # 네비게이션
    html.Nav([
        html.Div("📈 Dudunomics", style={
            "fontWeight": "bold", "fontSize": "18px", "marginRight": "24px",
        }),
        html.Div([
            dcc.Link(page["name"], href=page["relative_path"],
                     style={"marginRight": "16px", "textDecoration": "none", "color": "#333"})
            for page in sorted(dash.page_registry.values(), key=lambda p: p.get("order", 99))
        ]),
    ], style={
        "display": "flex", "alignItems": "center",
        "padding": "12px 24px",
        "backgroundColor": "white",
        "boxShadow": "0 1px 4px rgba(0,0,0,.1)",
        "position": "sticky", "top": 0, "zIndex": 100,
    }),

    dash.page_container,
], style={"minHeight": "100vh", "backgroundColor": "#f5f5f5", "fontFamily": "sans-serif"})


if __name__ == "__main__":
    scheduler = create_scheduler()
    scheduler.start()

    debug = os.getenv("DEBUG", "false").lower() == "true"
    port = int(os.getenv("PORT", 8050))

    try:
        app.run(debug=debug, host="0.0.0.0", port=port)
    finally:
        scheduler.shutdown()
