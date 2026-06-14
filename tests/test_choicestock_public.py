from unittest.mock import MagicMock, patch


def _summary_html() -> str:
    return """<html><body>
    <span class="chart_unit">최근실적발표 26.05.06 · 단위 : 백만달러</span>
    <script>
      var params = ['2024.06','2025.06','2026.06<br> <span style=\\"font-size:10px\\">(예상)</span>'];
      var value = [{y:1359.2,date: '2024.06', change: '-23.08%'},{y:1645,date: '2025.06', change: '+21.03%'},{y:2993.53130,className:'point_color',date: '2026.06 (예상)', change: '+81.98%'}];
      newDetailChart1('containerfinancials1_1', value, params, '매출액', '백만 달러');
    </script>
    <script>
      var params = ['2024.06','2025.06','2026.06<br> <span style=\\"font-size:10px\\">(예상)</span>'];
      var value = [{y:-8.12,date: '2024.06'},{y:0.37,date: '2025.06'},{y:4.93931,date: '2026.06 (예상)'}];
      newDetailChart1('containerfinancials1_2', value, params, 'EPS', '달러');
    </script>
    <script>
      var params = ['2024.06','2025.06','2026.06<br> <span style=\\"font-size:10px\\">(예상)</span>'];
      var value = [{y:-46.3,date: '2024.06'},{y:2.7,date: '2025.06'},{y:10.84,date: '2026.06 (예상)'}];
      newDetailChart1('containerfinancials1_3', value, params, 'ROE');
    </script>
    <div class="financial_table_inner">
      <div class="table_row full"><span class="label">시가총액</span><strong class="value">71,697</strong></div>
      <div class="table_row half"><span class="label">PER</span><strong class="value"><b>163.60</b>배</strong></div>
      <div class="table_row half"><span class="label">PER(F)</span><strong class="value"><b>56.84</b>배</strong></div>
      <div class="table_row half"><span class="label">PEG</span><strong class="value"><b>0.74</b>배</strong></div>
      <div class="table_row half"><span class="label">PSR</span><strong class="value"><b>28.80</b>배</strong></div>
      <div class="table_footer"><span class="date">26.06.12 기준</span></div>
    </div>
    <div class="main_mid new_area">
      <div class="list" onclick="location.href ='/stock/news_view/150978?bu=/search/summary/LITE'">
        <span class="tag">루멘텀홀딩스</span>
        <div class="txt"><p class="txt">루멘텀홀딩스, AI 성장 전략 제시</p></div>
        <div class="day"><p>2026.06.10 03:06</p></div>
      </div>
    </div>
    </body></html>"""


def test_parse_public_summary_extracts_numbers_and_news():
    from core.data.choicestock_public import parse_public_summary

    result = parse_public_summary(_summary_html(), "LITE", "https://www.choicestock.co.kr/search/summary/LITE")

    assert result["latest_report_date"] == "2026.05.06"
    assert result["revenue"][2]["value"] == 2993.5313
    assert result["revenue"][2]["is_estimate"] is True
    assert result["eps"][0]["value"] == -8.12
    assert result["roe"][2]["value"] == 10.84
    assert result["metrics"]["market_cap_m"] == 71697
    assert result["metrics"]["trailing_pe"] == 163.6
    assert result["metrics"]["forward_pe"] == 56.84
    assert result["metrics"]["peg"] == 0.74
    assert result["metrics"]["price_to_sales"] == 28.8
    assert result["metrics"]["as_of"] == "2026.06.12"
    assert result["news"][0]["title"] == "루멘텀홀딩스, AI 성장 전략 제시"
    assert result["news"][0]["url"].startswith("https://www.choicestock.co.kr/stock/news_view/")


def test_get_public_summary_uses_daily_db_cache():
    from core.data import choicestock_public as choice

    mock = MagicMock()
    mock.text = _summary_html()
    mock.raise_for_status = MagicMock()

    with patch.object(choice._CLIENT, "get", return_value=mock) as get:
        first = choice.get_public_summary("LITE")
        second = choice.get_public_summary("LITE")

    assert first["metrics"]["market_cap_m"] == 71697
    assert second["metrics"]["market_cap_m"] == 71697
    assert get.call_count == 1
