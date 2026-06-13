from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_data_sources_inventory_is_exposed_in_app_and_docs():
    app_inventory = ROOT / "frontend" / "lib" / "data-sources.ts"
    docs_inventory = ROOT / "docs" / "data-sources.md"

    assert app_inventory.exists()
    assert docs_inventory.exists()

    app_text = app_inventory.read_text(encoding="utf-8")
    docs_text = docs_inventory.read_text(encoding="utf-8")

    expected_sources = [
        "KIS Open API",
        "Yahoo Finance",
        "FMP",
        "Finviz",
        "StockAnalysis",
        "Naver Finance",
        "OpenDART",
        "Upbit",
        "Toss OpenAPI",
    ]

    for source in expected_sources:
        assert source in app_text
        assert source in docs_text
