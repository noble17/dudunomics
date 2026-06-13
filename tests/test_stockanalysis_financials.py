from unittest.mock import patch, MagicMock
import time


def _make_forecast_html() -> str:
    """SvelteKit script embed 형식 mock."""
    return """<html><body>
    <script>
    var data = {table:{annual:{
      eps:[5.61,6.11,6.13,6.09,7.20,8.05],
      dates:["2021-09-25","2022-09-24","2023-09-30","2024-09-28","2025-09-27","2026-09-30"],
      revenue:[365817000000,394328000000,383285000000,391035000000,415200000000,438000000000],
      analysts:[null,null,null,null,50,50]
    }}};
    </script>
    <td>May 26, 2026</td>
    </body></html>"""


def _make_financials_html() -> str:
    """/stocks/{ticker}/financials/ — netIncome script embed 형식."""
    return """<html><body>
    <script>
    var d = {table:{annual:{
      dates:["2021-09-25","2022-09-24","2023-09-30","2024-09-28"],
      netIncome:[94680000000,99803000000,96995000000,93736000000],
      analysts:[null,null,null,null]
    }}};
    </script>
    </body></html>"""


def _make_balance_sheet_html() -> str:
    """/stocks/{ticker}/financials/balance-sheet/ — totalEquity script embed 형식."""
    return """<html><body>
    <script>
    var d = {table:{annual:{
      dates:["2021-09-25","2022-09-24","2023-09-30","2024-09-28"],
      totalEquity:[63090000000,50672000000,62146000000,56950000000],
      analysts:[null,null,null,null]
    }}};
    </script>
    </body></html>"""


def _make_choicestock_html() -> str:
    return """<html><body>
    <span class="chart_unit">최근실적발표 26.05.06 · 단위 : 백만달러</span>
    <script>
      var params = ['2024.06','2025.06','2026.06<br> <span style=\\"font-size:10px\\">(예상)</span>','2027.06<br> <span style=\\"font-size:10px\\">(예상)</span>','2028.06<br> <span style=\\"font-size:10px\\">(예상)</span>',];
      var value = [{y:1359.2,date: '2024.06', change: '-23.08%'},{y:1645,date: '2025.06', change: '+21.03%'},{y:2993.53130,className:'point_color',date: '2026.06 (예상)', change: '+81.98%'},{y:5547.45834,className:'point_color',date: '2027.06 (예상)', change: '+85.31%'},{y:8317.14352,className:'point_color',date: '2028.06 (예상)', change: '+49.93%'},];
      newDetailChart1('containerfinancials1_1', value, params, '매출액', '백만 달러');
    </script>
    <script>
      var params = ['2024.06','2025.06','2026.06<br> <span style=\\"font-size:10px\\">(예상)</span>','2027.06<br> <span style=\\"font-size:10px\\">(예상)</span>','2028.06<br> <span style=\\"font-size:10px\\">(예상)</span>',];
      var value = [{y:-8.12,className:'decrease_color',date: '2024.06', change: '적자지속'},{y:0.37,date: '2025.06', change: '흑자전환'},{y:4.93931,className:'point_color',date: '2026.06 (예상)', change: '+1234.95%'},{y:15.91647,className:'point_color',date: '2027.06 (예상)', change: '+222.24%'},{y:27.75827,className:'point_color',date: '2028.06 (예상)', change: '+74.40%'},];
      newDetailChart1('containerfinancials1_2', value, params, 'EPS', '달러');
    </script>
    <script>
      var params = ['2024.06','2025.06','2026.06<br> <span style=\\"font-size:10px\\">(예상)</span>','2027.06<br> <span style=\\"font-size:10px\\">(예상)</span>','2028.06<br> <span style=\\"font-size:10px\\">(예상)</span>',];
      var value = [{y:-46.3,className:'decrease_color',date: '2024.06', change: '적자지속'},{y:2.7,date: '2025.06', change: '흑자전환'},{y:10.84,className:'point_color',date: '2026.06 (예상)', change: '+301.48%'},{y:25.19,className:'point_color',date: '2027.06 (예상)', change: '+132.38%'},{y:26.92,className:'point_color',date: '2028.06 (예상)', change: '+6.87%'},];
      newDetailChart1('containerfinancials1_3', value, params, 'ROE');
    </script>
    </body></html>"""


def _make_mock_get():
    """URL에 따라 적절한 HTML을 반환하는 mock get 함수."""
    def side_effect(url, **kwargs):
        mock = MagicMock(raise_for_status=MagicMock())
        if "choicestock.co.kr" in url:
            mock.text = "<html></html>"
        elif "/balance-sheet/" in url:
            mock.text = _make_balance_sheet_html()
        elif "/financials/" in url:
            mock.text = _make_financials_html()
        else:
            mock.text = _make_forecast_html()
        return mock
    return side_effect


def _make_mock_get_with_choicestock():
    def side_effect(url, **kwargs):
        mock = MagicMock(raise_for_status=MagicMock())
        if "choicestock.co.kr" in url:
            mock.text = _make_choicestock_html()
        elif "/balance-sheet/" in url:
            mock.text = _make_balance_sheet_html()
        elif "/financials/" in url:
            mock.text = _make_financials_html()
        else:
            mock.text = _make_forecast_html()
        return mock
    return side_effect


def test_fetch_annual_financials_revenue(tmp_path, monkeypatch):
    from core.data import stockanalysis_financials as sa
    monkeypatch.setattr(sa, "_DB_PATH", tmp_path / "sa_cache.sqlite")
    with patch.object(sa._CLIENT, "get", side_effect=_make_mock_get()):
        result = sa.fetch_annual_financials("AAPL")
    assert result is not None
    assert len(result["revenue"]) == 6
    fy2024 = next(r for r in result["revenue"] if r["year"] == "2024")
    assert fy2024["value"] == 391035
    assert fy2024["is_estimate"] is False
    fy2025 = next(r for r in result["revenue"] if r["year"] == "2025")
    assert fy2025["is_estimate"] is True


def test_fetch_annual_financials_eps(tmp_path, monkeypatch):
    from core.data import stockanalysis_financials as sa
    monkeypatch.setattr(sa, "_DB_PATH", tmp_path / "sa_cache.sqlite")
    with patch.object(sa._CLIENT, "get", side_effect=_make_mock_get()):
        result = sa.fetch_annual_financials("AAPL")
    assert result is not None
    fy2024 = next(r for r in result["eps"] if r["year"] == "2024")
    assert abs(fy2024["value"] - 6.09) < 0.01


def test_fetch_annual_financials_merges_choicestock_estimates(tmp_path, monkeypatch):
    from core.data import stockanalysis_financials as sa
    monkeypatch.setattr(sa, "_DB_PATH", tmp_path / "sa_cache.sqlite")
    with patch.object(sa._CLIENT, "get", side_effect=_make_mock_get_with_choicestock()):
        result = sa.fetch_annual_financials("LITE")
    revenue_by_year = {row["year"]: row for row in result["revenue"]}
    eps_by_year = {row["year"]: row for row in result["eps"]}
    roe_by_year = {row["year"]: row for row in result["roe"]}
    assert revenue_by_year["2027"]["value"] == 5547.45834
    assert revenue_by_year["2028"]["value"] == 8317.14352
    assert eps_by_year["2027"]["value"] == 15.91647
    assert eps_by_year["2027"]["is_estimate"] is True
    assert eps_by_year["2028"]["value"] == 27.75827
    assert roe_by_year["2027"]["value"] == 25.19
    assert roe_by_year["2028"]["value"] == 26.92
    assert result["latest_report_date"] == "2026.05.06"


def test_fetch_annual_financials_roe(tmp_path, monkeypatch):
    from core.data import stockanalysis_financials as sa
    monkeypatch.setattr(sa, "_DB_PATH", tmp_path / "sa_cache.sqlite")
    with patch.object(sa._CLIENT, "get", side_effect=_make_mock_get()):
        result = sa.fetch_annual_financials("AAPL")
    assert result is not None
    roe = result["roe"]
    assert len(roe) == 4  # FY2021~FY2024, 예상치 없음
    fy2024 = next(r for r in roe if r["year"] == "2024")
    # 93,736 / 56,950 * 100 ≈ 164.60
    assert abs(fy2024["value"] - round(93736 / 56950 * 100, 2)) < 0.01
    assert fy2024["is_estimate"] is False


def test_roe_skips_estimates(tmp_path, monkeypatch):
    """예상치(FY2025E 등)는 ROE 계산에서 제외."""
    from core.data import stockanalysis_financials as sa
    monkeypatch.setattr(sa, "_DB_PATH", tmp_path / "sa_cache.sqlite")

    def side_effect_with_estimates(url, **kwargs):
        mock = MagicMock(raise_for_status=MagicMock())
        if "/balance-sheet/" in url:
            mock.text = """<html><body><script>
            var d={table:{annual:{dates:["2024-09-28","2025-09-27"],totalEquity:[56950000000,60000000000],analysts:[null,50]}}};
            </script></body></html>"""
        elif "/financials/" in url:
            mock.text = """<html><body><script>
            var d={table:{annual:{dates:["2024-09-28","2025-09-27"],netIncome:[93736000000,100000000000],analysts:[null,50]}}};
            </script></body></html>"""
        else:
            mock.text = _make_forecast_html()
        return mock

    with patch.object(sa._CLIENT, "get", side_effect=side_effect_with_estimates):
        result = sa.fetch_annual_financials("AAPL")
    roe = result["roe"]
    assert len(roe) == 1
    assert roe[0]["year"] == "2024"


def test_roe_graceful_on_parse_failure(tmp_path, monkeypatch):
    """balance-sheet 파싱 실패 시 roe=[] 반환, 나머지 데이터 정상."""
    from core.data import stockanalysis_financials as sa
    monkeypatch.setattr(sa, "_DB_PATH", tmp_path / "sa_cache.sqlite")

    def side_effect_no_equity(url, **kwargs):
        mock = MagicMock(raise_for_status=MagicMock())
        if "/balance-sheet/" in url:
            mock.text = "<html><body><p>no table</p></body></html>"
        elif "/financials/" in url:
            mock.text = _make_financials_html()
        else:
            mock.text = _make_forecast_html()
        return mock

    with patch.object(sa._CLIENT, "get", side_effect=side_effect_no_equity):
        result = sa.fetch_annual_financials("AAPL")
    assert result is not None
    assert result["roe"] == []
    assert len(result["revenue"]) == 6


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
        "_v": sa._CACHE_VER,
    }
    sa._to_cache("AAPL", data)
    with patch.object(sa._CLIENT, "get") as mock_get:
        result = sa.fetch_annual_financials("AAPL")
    mock_get.assert_not_called()
    assert result["revenue"][0]["value"] == 391035


def test_cache_invalidated_on_version_mismatch(tmp_path, monkeypatch):
    """캐시 버전 불일치 시 HTTP 재요청."""
    import sqlite3, json as _json
    from core.data import stockanalysis_financials as sa
    db_path = tmp_path / "sa_cache.sqlite"
    monkeypatch.setattr(sa, "_DB_PATH", db_path)

    # _to_cache는 항상 _CACHE_VER를 덮어쓰므로 직접 SQLite에 구버전 삽입
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE sa_financials (ticker TEXT PRIMARY KEY, data TEXT, ts REAL)")
    old_json = _json.dumps({"revenue": [], "eps": [], "roe": [], "latest_report_date": None, "_v": 0})
    conn.execute("INSERT INTO sa_financials VALUES (?, ?, ?)", ("AAPL", old_json, time.time()))
    conn.commit()
    conn.close()

    with patch.object(sa._CLIENT, "get", side_effect=_make_mock_get()) as mock_get:
        result = sa.fetch_annual_financials("AAPL")
    assert mock_get.called
    assert len(result["revenue"]) == 6
