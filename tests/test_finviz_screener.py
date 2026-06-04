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


def test_universe_scorer_uses_finviz_bulk(monkeypatch):
    """run_batch가 _sync_quarterly(FMP) 대신 fetch_finviz_bulk를 호출하는지 확인."""
    import pandas as pd
    import math
    from unittest.mock import MagicMock, patch

    finviz_data = {"AAPL": {"eps_qq": 0.15}, "MSFT": {"eps_qq": -0.03}}

    mock_snap = MagicMock()
    mock_snap.ticker = "AAPL"
    mock_snap.forward_pe = 28.0
    mock_snap.trailing_pe = 30.0
    mock_snap.pbr = 40.0
    mock_snap.psr = 8.0
    mock_snap.ev_ebitda = 25.0
    mock_snap.peg = 2.5
    mock_snap.market_cap_m = 3_000_000.0
    mock_snap.operating_cashflow = 100.0
    mock_snap.roe = 1.5
    mock_snap.debt_to_equity = 1.8
    mock_snap.negative_book_value = False
    mock_snap.eps_ttm = 6.0
    mock_snap.forward_eps = 7.0
    mock_snap.company_name = "Apple Inc."
    mock_snap.sector = "Technology"
    mock_snap.industry = "Consumer Electronics"
    mock_snap.fcf_yield = 0.03
    mock_snap.negative_book_value = False

    mock_snap_msft = MagicMock()
    mock_snap_msft.ticker = "MSFT"
    mock_snap_msft.forward_pe = 35.0
    mock_snap_msft.trailing_pe = 38.0
    mock_snap_msft.pbr = 12.0
    mock_snap_msft.psr = 12.0
    mock_snap_msft.ev_ebitda = 30.0
    mock_snap_msft.peg = 2.0
    mock_snap_msft.market_cap_m = 3_200_000.0
    mock_snap_msft.operating_cashflow = 90.0
    mock_snap_msft.roe = 0.4
    mock_snap_msft.debt_to_equity = 0.5
    mock_snap_msft.negative_book_value = False
    mock_snap_msft.eps_ttm = 12.0
    mock_snap_msft.forward_eps = 14.0
    mock_snap_msft.company_name = "Microsoft Corp."
    mock_snap_msft.sector = "Technology"
    mock_snap_msft.industry = "Software"
    mock_snap_msft.fcf_yield = 0.025
    mock_snap_msft.negative_book_value = False

    import core.batch_state as bs_module

    # reload를 patch 블록 밖에서 먼저 실행해 최신 코드(fetch_finviz_bulk 포함)를 로딩
    from core.scoring import universe_scorer
    import importlib; importlib.reload(universe_scorer)

    with patch("core.scoring.universe_scorer.get_tickers", return_value=["AAPL", "MSFT"]), \
         patch("core.scoring.universe_scorer.fetch_ohlcv", return_value=(pd.DataFrame(), [])), \
         patch("core.scoring.universe_scorer.fetch_extended", return_value=[mock_snap, mock_snap_msft]), \
         patch("core.scoring.universe_scorer.fetch_finviz_bulk", return_value=finviz_data) as mock_bulk, \
         patch("core.scoring.universe_scorer.repo.get_quarterly_bulk", return_value={}), \
         patch("core.scoring.universe_scorer.repo.upsert_quant_scores") as mock_upsert, \
         patch("core.scoring.universe_scorer.PriceMomentumFactor") as MockPMF, \
         patch("core.scoring.universe_scorer.ForwardEpsMomentumFactor") as MockFEMF, \
         patch("core.scoring.universe_scorer.TechnicalFactor") as MockTF, \
         patch("core.scoring.universe_scorer.compute_valuation_zscore",
               return_value=pd.Series({"AAPL": 0.5, "MSFT": 0.5})), \
         patch.object(bs_module, "start"), \
         patch.object(bs_module, "update"), \
         patch.object(bs_module, "finish"):
        MockPMF.return_value.compute.return_value = pd.Series({"AAPL": 0.1, "MSFT": 0.2})
        MockFEMF.return_value.compute.return_value = pd.Series({"AAPL": 0.1, "MSFT": 0.2})
        MockTF.compute_raw = MagicMock(return_value={"rsi": 50.0, "above_ma200": True})

        universe_scorer.run_batch("sp500")

    mock_bulk.assert_called_once_with("idx_sp500")
    saved_rows = mock_upsert.call_args.args[0]
    apple = next(row for row in saved_rows if row["ticker"] == "AAPL")
    assert apple["raw_debt_ratio"] == 1.8
