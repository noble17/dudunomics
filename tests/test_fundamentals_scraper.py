"""tests/test_fundamentals_scraper.py"""
import pytest


def test_parse_market_cap_m_billions():
    from core.data.fundamentals_scraper import _parse_market_cap_m
    assert _parse_market_cap_m("45.2B") == pytest.approx(45_200.0)


def test_parse_market_cap_m_trillions():
    from core.data.fundamentals_scraper import _parse_market_cap_m
    assert _parse_market_cap_m("1.05T") == pytest.approx(1_050_000.0)


def test_parse_market_cap_m_millions():
    from core.data.fundamentals_scraper import _parse_market_cap_m
    assert _parse_market_cap_m("250.00M") == pytest.approx(250.0)


def test_parse_market_cap_m_none():
    from core.data.fundamentals_scraper import _parse_market_cap_m
    assert _parse_market_cap_m("") is None
    assert _parse_market_cap_m("-") is None


def test_negative_book_value_detection(monkeypatch):
    from core.data.fundamentals_scraper import _fetch_finviz

    html = """
    <table class="snapshot-table2">
      <tr><td>P/E</td><td>12.5</td><td>P/B</td><td>-</td>
          <td>EV/EBITDA</td><td>8.5</td><td>PEG</td><td>0.8</td>
          <td>Market Cap</td><td>45.2B</td><td>Sector</td><td>Technology</td>
          <td>Industry</td><td>Computer Hardware</td></tr>
    </table>
    """

    class FakeResponse:
        text = html
        def raise_for_status(self): pass

    urls = []
    monkeypatch.setattr(
        "core.data.fundamentals_scraper._CLIENT",
        type("C", (), {"get": lambda self, u: urls.append(u) or FakeResponse()})()
    )

    snap = _fetch_finviz("DELL")
    assert urls == ["https://finviz.com/stock?t=DELL&p=d"]
    assert snap.negative_book_value is True
    assert snap.price_to_book is None
    assert snap.ev_ebitda == pytest.approx(8.5)
    assert snap.peg == pytest.approx(0.8)
    assert snap.market_cap_m == pytest.approx(45_200.0)
    assert snap.sector == "Technology"
    assert snap.industry == "Computer Hardware"


def test_supplement_stockanalysis_capex(monkeypatch):
    from core.data.fundamentals_scraper import _supplement_stockanalysis, FundamentalsSnapshot

    html = """
    <table>
      <tr><td>Operating Cash Flow</td><td>5.0B</td></tr>
      <tr><td>Capital Expenditures</td><td>-1.2B</td></tr>
    </table>
    """

    class FakeResponse:
        text = html
        def raise_for_status(self): pass

    monkeypatch.setattr(
        "core.data.fundamentals_scraper._CLIENT",
        type("C", (), {"get": lambda self, u: FakeResponse()})()
    )

    snap = FundamentalsSnapshot(ticker="DELL")
    _supplement_stockanalysis(snap)
    assert snap.operating_cashflow == pytest.approx(5_000_000_000)
    assert snap.capex == pytest.approx(1_200_000_000)
