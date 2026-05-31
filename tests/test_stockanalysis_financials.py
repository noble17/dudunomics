from unittest.mock import patch, MagicMock
import time


def _make_forecast_html() -> str:
    """stockanalysis.com /stocks/aapl/forecast/ 응답 mock HTML.

    실제 stockanalysis.com 페이지 구조:
    - Revenue/EPS 테이블은 data-feature attribute로 식별
    - 헤더: FY2021, FY2022, ..., FY2025E, FY2026E (E = estimate)
    - 'Last Earnings' 날짜 텍스트
    """
    return """<html><body>
    <table data-feature="revenue">
      <thead>
        <tr>
          <th>Revenue</th>
          <th>FY2021</th><th>FY2022</th><th>FY2023</th><th>FY2024</th>
          <th>FY2025E</th><th>FY2026E</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Revenue</td>
          <td>365,817</td><td>394,328</td><td>383,285</td><td>391,035</td>
          <td>415,200</td><td>438,000</td>
        </tr>
      </tbody>
    </table>
    <table data-feature="eps">
      <thead>
        <tr>
          <th>EPS</th>
          <th>FY2021</th><th>FY2022</th><th>FY2023</th><th>FY2024</th>
          <th>FY2025E</th><th>FY2026E</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>EPS</td>
          <td>5.61</td><td>6.11</td><td>6.13</td><td>6.09</td>
          <td>7.20</td><td>8.05</td>
        </tr>
      </tbody>
    </table>
    <div class="text-sm text-gray-500">Last Earnings: <span>May 26, 2026</span></div>
    </body></html>"""


def test_fetch_annual_financials_revenue():
    from core.data import stockanalysis_financials as sa
    with patch.object(sa._CLIENT, "get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, text=_make_forecast_html(), raise_for_status=MagicMock())
        result = sa.fetch_annual_financials("AAPL")
    assert result is not None
    assert len(result["revenue"]) == 6
    fy2024 = next(r for r in result["revenue"] if r["year"] == "2024")
    assert fy2024["value"] == 391035
    assert fy2024["is_estimate"] is False
    fy2025 = next(r for r in result["revenue"] if r["year"] == "2025")
    assert fy2025["is_estimate"] is True


def test_fetch_annual_financials_eps():
    from core.data import stockanalysis_financials as sa
    with patch.object(sa._CLIENT, "get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, text=_make_forecast_html(), raise_for_status=MagicMock())
        result = sa.fetch_annual_financials("AAPL")
    assert result is not None
    fy2024 = next(r for r in result["eps"] if r["year"] == "2024")
    assert abs(fy2024["value"] - 6.09) < 0.01


def test_korean_ticker_returns_none():
    from core.data import stockanalysis_financials as sa
    result = sa.fetch_annual_financials("005930.KS")
    assert result is None


def test_cache_hit_skips_http(tmp_path, monkeypatch):
    from core.data import stockanalysis_financials as sa
    monkeypatch.setattr(sa, "_DB_PATH", tmp_path / "sa_cache.sqlite")
    data = {
        "revenue": [{"year": "2024", "period_end": "2024", "value": 391035, "is_estimate": False}],
        "eps": [], "roe": [], "latest_report_date": "2026.05.26",
    }
    sa._to_cache("AAPL", data)
    with patch.object(sa._CLIENT, "get") as mock_get:
        result = sa.fetch_annual_financials("AAPL")
    mock_get.assert_not_called()
    assert result["revenue"][0]["value"] == 391035
