from unittest.mock import patch, MagicMock


def _make_page_html(tickers_epsqq: list[tuple[str, str]], total: int = None) -> str:
    """Finviz screener HTML mock — new UI structure (screener_table class).

    헤더: Ticker, Company, Sector, Industry, Country, Market Cap, EPS Q/Q
    데이터: td[0]=ticker, ..., td[6]=EPS Q/Q
    """
    if total is None:
        total = len(tickers_epsqq)
    rows_html = ""
    for ticker, eps_qq in tickers_epsqq:
        rows_html += f"""
        <tr class="styled-row is-bordered">
          <td>{ticker}</td>
          <td>Tech Company</td>
          <td>Technology</td>
          <td>Software</td>
          <td>USA</td>
          <td>300B</td>
          <td>{eps_qq}</td>
        </tr>"""
    return f"""<html><body>
      <div id="screener-total" class="count-text">#1 / {total} Total</div>
      <table class="styled-table-new is-rounded is-tabular-nums w-full screener_table">
        <thead>
          <tr>
            <th class="table-header">Ticker</th>
            <th class="table-header">Company</th>
            <th class="table-header">Sector</th>
            <th class="table-header">Industry</th>
            <th class="table-header">Country</th>
            <th class="table-header">Market Cap</th>
            <th class="table-header">EPS Q/Q</th>
          </tr>
        </thead>
        {rows_html}
      </table>
    </body></html>"""


def _make_mock_response(tickers_epsqq, total=None):
    m = MagicMock()
    m.status_code = 200
    m.text = _make_page_html(tickers_epsqq, total=total)
    m.raise_for_status = MagicMock()
    return m


def test_fetch_finviz_bulk_basic():
    from core.data import finviz_screener
    with patch.object(finviz_screener._CLIENT, "get") as mock_get:
        mock_get.return_value = _make_mock_response([("AAPL", "15.23%"), ("MSFT", "-3.50%")])
        result = finviz_screener.fetch_finviz_bulk("idx_sp500")
    assert "AAPL" in result
    assert abs(result["AAPL"]["eps_qq"] - 0.1523) < 0.001
    assert abs(result["MSFT"]["eps_qq"] - (-0.035)) < 0.001


def test_fetch_finviz_bulk_handles_dash():
    from core.data import finviz_screener
    with patch.object(finviz_screener._CLIENT, "get") as mock_get:
        mock_get.return_value = _make_mock_response([("TSLA", "-")])
        result = finviz_screener.fetch_finviz_bulk("idx_sp500")
    assert result["TSLA"]["eps_qq"] is None


def test_fetch_finviz_bulk_paginates():
    """Fetches second page when first page is full (20 rows)."""
    from core.data import finviz_screener
    page1 = _make_mock_response(
        [("T" + str(i), "10%") for i in range(20)],
        total=21,
    )
    page2 = _make_mock_response([("ZZZZ", "5%")], total=21)
    call_count = 0

    def _side_effect(url, **kwargs):
        nonlocal call_count
        call_count += 1
        return page1 if call_count == 1 else page2

    with patch.object(finviz_screener._CLIENT, "get", side_effect=_side_effect):
        result = finviz_screener.fetch_finviz_bulk("idx_sp500")
    assert call_count == 2
    assert "ZZZZ" in result
