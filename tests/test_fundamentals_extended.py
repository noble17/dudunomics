"""tests/test_fundamentals_extended.py"""
import pytest
import threading
import time
from datetime import date
from unittest.mock import patch


def _make_scraped(**kwargs):
    from core.data.fundamentals_scraper import FundamentalsSnapshot
    defaults = dict(
        ticker="DELL",
        forward_pe=12.0,
        trailing_pe=14.0,
        price_to_book=None,
        price_to_sales=0.5,
        forward_eps=8.5,
        trailing_eps=7.0,
        return_on_equity=None,
        debt_to_equity=300.0,
        operating_cashflow=5_000_000_000,
        short_name="Dell Technologies",
        ev_ebitda=8.5,
        peg=0.8,
        market_cap_m=45_000.0,
        capex=1_200_000_000,
        sector="Technology",
        industry="Computer Hardware",
        negative_book_value=True,
    )
    defaults.update(kwargs)
    return FundamentalsSnapshot(**defaults)


def test_fcf_yield_computed():
    from core.data.fundamentals_extended import _fetch_one
    scraped = _make_scraped()
    with patch("core.data.fundamentals_extended._scrape", return_value=scraped):
        snap = _fetch_one("DELL", date.today())
    assert snap.fcf_yield is not None
    assert pytest.approx(snap.fcf_yield, abs=0.001) == 3_800_000_000 / (45_000 * 1_000_000)


def test_negative_book_value_propagated():
    from core.data.fundamentals_extended import _fetch_one
    scraped = _make_scraped(negative_book_value=True, price_to_book=None)
    with patch("core.data.fundamentals_extended._scrape", return_value=scraped):
        snap = _fetch_one("DELL", date.today())
    assert snap.negative_book_value is True
    assert snap.pbr is None


def test_fcf_yield_none_when_capex_missing():
    from core.data.fundamentals_extended import _fetch_one
    scraped = _make_scraped(capex=None)
    with patch("core.data.fundamentals_extended._scrape", return_value=scraped):
        snap = _fetch_one("DELL", date.today())
    assert snap.fcf_yield is None


def test_no_yfinance_import():
    import ast, pathlib
    src = pathlib.Path("core/data/fundamentals_extended.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            assert not any("yfinance" in n for n in names), "yfinance import found!"


def test_fetch_extended_uses_limited_parallelism(monkeypatch):
    from core.data import fundamentals_extended as fe

    active = 0
    peak = 0
    lock = threading.Lock()

    def fake_fetch_one(ticker, as_of):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.02)
        with lock:
            active -= 1
        return fe.ExtendedSnapshot(ticker=ticker, as_of=as_of)

    monkeypatch.setattr(fe, "_fetch_one", fake_fetch_one)

    rows = fe.fetch_extended(["A", "B", "C", "D", "E", "F"], max_workers=4)

    assert len(rows) == 6
    assert 2 <= peak <= 4
