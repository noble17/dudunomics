from datetime import date
from unittest.mock import MagicMock, patch

import pytest

import core.data.price_target_consensus as consensus
from core.data.price_target_consensus import (
    _fetch_fmp,
    _reset_cache,
    aggregate_kis_reports,
    fetch_price_target_consensus,
)


@pytest.fixture(autouse=True)
def reset_cache():
    _reset_cache()


def _response(data, status_code=200, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = data
    response.text = text
    return response


class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 6, 2)


def test_fmp_success_maps_consensus_fields(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    response = _response([{
        "symbol": "AAPL",
        "targetConsensus": 240.5,
        "targetMedian": 245,
        "targetLow": 190,
        "targetHigh": 300,
    }])

    with patch("core.data.price_target_consensus.requests.get", return_value=response):
        result = fetch_price_target_consensus("aapl")

    assert result == {
        "consensus_status": "ok",
        "consensus_message": "애널리스트 목표주가 컨센서스입니다.",
        "consensus_source": "FMP",
        "retry_after": None,
        "current_price": None,
        "target_mean": 240.5,
        "target_median": 245,
        "target_low": 190,
        "target_high": 300,
        "upside_pct": None,
        "analyst_count": None,
        "consensus_as_of": None,
        "fallback_used": False,
        "consensus_attempts": [{"source": "FMP", "status": "ok"}],
    }


def test_us_subscription_limit_falls_back_to_finviz(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    responses = [
        _response({}, status_code=402),
        _response(None, text="""
            <table class="snapshot-table2">
              <tr><td>Target Price</td><td><b>767.73</b></td></tr>
            </table>
            <table>
              <tr>
                <td>May-29-26</td><td>Reiterated</td><td>Susquehanna</td>
                <td>Positive</td><td>$600 → $1750</td>
              </tr>
              <tr>
                <td>May-28-26</td><td>Reiterated</td><td>DA Davidson</td>
                <td>Buy</td><td>$1000 → $1500</td>
              </tr>
              <tr>
                <td>May-27-26</td><td>Reiterated</td><td>Barclays</td>
                <td>Overweight</td><td>$675 → $1175</td>
              </tr>
              <tr>
                <td>Apr-27-26</td><td>Initiated</td><td>Melius</td>
                <td>Buy</td><td></td>
              </tr>
            </table>
        """),
    ]

    with patch("core.data.price_target_consensus.requests.get", side_effect=responses) as mock_get:
        result = fetch_price_target_consensus("MU")

    assert result["consensus_status"] == "ok"
    assert result["consensus_source"] == "FINVIZ"
    assert result["target_mean"] == 767.73
    assert result["target_median"] == 1500
    assert result["target_low"] == 1175
    assert result["target_high"] == 1750
    assert result["analyst_count"] == 3
    assert result["consensus_as_of"] == "2026-05-29"
    assert result["fallback_used"] is True
    assert result["consensus_attempts"] == [
        {"source": "FMP", "status": "subscription_limited"},
        {"source": "FINVIZ", "status": "ok"},
    ]
    assert mock_get.call_args_list[1].args[0] == "https://finviz.com/stock?t=MU&p=d"


def test_finviz_rating_targets_ignore_targets_on_different_price_scale(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    responses = [
        _response({}, status_code=402),
        _response(None, text="""
            <table class="snapshot-table2">
              <tr><td>Target Price</td><td>1746.83</td></tr>
            </table>
            <table>
              <tr><td>May-27-26</td><td>Reiterated</td><td>Analyst A</td><td>Buy</td><td>$1800 → $2300</td></tr>
              <tr><td>May-20-26</td><td>Reiterated</td><td>Analyst B</td><td>Buy</td><td>$1500</td></tr>
              <tr><td>Apr-20-26</td><td>Reiterated</td><td>Old Scale</td><td>Buy</td><td>$32 → $180</td></tr>
              <tr><td>Jan-20-26</td><td>Reiterated</td><td>Stale Analyst</td><td>Buy</td><td>$900</td></tr>
            </table>
        """),
    ]

    with patch("core.data.price_target_consensus.requests.get", side_effect=responses):
        result = fetch_price_target_consensus("SNDK")

    assert result["target_median"] == 1900
    assert result["target_low"] == 1500
    assert result["target_high"] == 2300
    assert result["analyst_count"] == 2


def test_us_finviz_failure_falls_back_to_stockanalysis(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    responses = [
        _response(None, text="<html><body>No target</body></html>"),
        _response(None, text="""
            <html><body>
              <p>The average price target is $1,234.56.</p>
            </body></html>
        """),
    ]

    with patch("core.data.price_target_consensus.requests.get", side_effect=responses) as mock_get:
        result = fetch_price_target_consensus("MU")

    assert result["consensus_status"] == "ok"
    assert result["consensus_source"] == "STOCKANALYSIS"
    assert result["target_mean"] == 1234.56
    assert result["fallback_used"] is True
    assert result["consensus_attempts"] == [
        {"source": "FMP", "status": "missing_key"},
        {"source": "FINVIZ", "status": "no_data"},
        {"source": "STOCKANALYSIS", "status": "ok"},
    ]
    assert mock_get.call_args_list[1].args[0] == "https://stockanalysis.com/stocks/mu/forecast/"


def test_us_fallback_provider_results_use_daily_cache(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    responses = [
        _response(None, text="<table><tr><td>Target Price</td><td>500</td></tr></table>"),
    ]

    with patch("core.data.price_target_consensus.requests.get", side_effect=responses) as mock_get:
        first = fetch_price_target_consensus("MU")
        second = fetch_price_target_consensus("MU")

    assert second == first
    mock_get.assert_called_once()


def test_finviz_http_429_blocks_finviz_for_day_but_stockanalysis_still_runs(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    responses = [
        _response(None, status_code=429),
        _response(None, text="<p>The average price target is $700.</p>"),
        _response(None, text="<p>The average price target is $800.</p>"),
    ]

    with patch("core.data.price_target_consensus.requests.get", side_effect=responses) as mock_get:
        first = fetch_price_target_consensus("MU")
        second = fetch_price_target_consensus("NVDA")

    assert first["target_mean"] == 700
    assert second["target_mean"] == 800
    assert second["consensus_attempts"][:2] == [
        {"source": "FMP", "status": "missing_key"},
        {"source": "FINVIZ", "status": "rate_limited"},
    ]
    assert mock_get.call_count == 3


def test_stockanalysis_http_429_blocks_stockanalysis_for_day(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    responses = [
        _response(None, text="<html></html>"),
        _response(None, status_code=429),
        _response(None, text="<html></html>"),
    ]

    with patch("core.data.price_target_consensus.requests.get", side_effect=responses) as mock_get:
        first = fetch_price_target_consensus("MU")
        second = fetch_price_target_consensus("NVDA")

    assert first["consensus_status"] == "rate_limited"
    assert first["consensus_source"] == "STOCKANALYSIS"
    assert second["consensus_status"] == "rate_limited"
    assert second["consensus_source"] == "STOCKANALYSIS"
    assert mock_get.call_count == 3


def test_kis_result_includes_default_fallback_metadata():
    result = aggregate_kis_reports([])

    assert result["fallback_used"] is False
    assert result["consensus_attempts"] == []


def test_fmp_plan_ticker_row_is_not_rate_limited(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    response = _response([{"symbol": "PLAN", "targetConsensus": "120.5"}])

    with patch("core.data.price_target_consensus.requests.get", return_value=response):
        result = _fetch_fmp("PLAN")

    assert result["consensus_status"] == "ok"
    assert result["target_mean"] == 120.5


def test_fmp_calls_expected_url_and_params(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")

    with patch(
        "core.data.price_target_consensus.requests.get",
        return_value=_response([]),
    ) as mock_get:
        _fetch_fmp("AAPL")

    mock_get.assert_called_once_with(
        "https://financialmodelingprep.com/stable/price-target-consensus",
        params={"symbol": "AAPL", "apikey": "secret"},
        timeout=10,
    )


def test_fmp_same_ticker_uses_daily_cache(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    response = _response([{"targetConsensus": 240}])

    with patch("core.data.price_target_consensus.requests.get", return_value=response) as mock_get:
        first = _fetch_fmp("AAPL")
        second = _fetch_fmp("AAPL")

    assert first == second
    mock_get.assert_called_once()


def test_fmp_http_429_blocks_other_us_tickers_for_the_day(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    response = _response({}, status_code=429)

    with patch("core.data.price_target_consensus.requests.get", return_value=response) as mock_get:
        first = _fetch_fmp("AAPL")
        second = _fetch_fmp("MSFT")

    assert first["consensus_status"] == "rate_limited"
    assert second["consensus_status"] == "rate_limited"
    mock_get.assert_called_once()


def test_fmp_non_json_http_429_is_rate_limited(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    response = _response(None, status_code=429)
    response.json.side_effect = ValueError("not json")

    with patch("core.data.price_target_consensus.requests.get", return_value=response):
        result = _fetch_fmp("AAPL")

    assert result["consensus_status"] == "rate_limited"


def test_fmp_limit_blocks_other_us_tickers_for_the_day(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    response = _response({"Error Message": "Rate limit reached. Please upgrade your plan."})

    with patch("core.data.price_target_consensus.requests.get", return_value=response) as mock_get:
        first = _fetch_fmp("AAPL")
        second = _fetch_fmp("MSFT")

    assert first["consensus_status"] == "rate_limited"
    assert second["consensus_status"] == "rate_limited"
    assert second["retry_after"] is None
    mock_get.assert_called_once()


def test_fmp_service_upgrade_message_is_temporary_error_without_global_block(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    responses = [
        _response({"Error Message": "Service upgrade scheduled tonight"}),
        _response([]),
    ]

    with patch("core.data.price_target_consensus.requests.get", side_effect=responses) as mock_get:
        first = _fetch_fmp("AAPL")
        second = _fetch_fmp("MSFT")

    assert first["consensus_status"] == "temporary_error"
    assert second["consensus_status"] == "no_data"
    assert mock_get.call_count == 2


def test_fmp_success_cache_survives_later_rate_limit(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    responses = [
        _response([{"targetConsensus": 240}]),
        _response({}, status_code=429),
    ]

    with patch("core.data.price_target_consensus.requests.get", side_effect=responses) as mock_get:
        success = _fetch_fmp("AAPL")
        limited = _fetch_fmp("MSFT")
        cached = _fetch_fmp("AAPL")

    assert success["consensus_status"] == "ok"
    assert limited["consensus_status"] == "rate_limited"
    assert cached == success
    assert mock_get.call_count == 2


def test_fmp_http_error_uses_short_cache(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    response = _response({}, status_code=500)

    with patch("core.data.price_target_consensus.requests.get", return_value=response) as mock_get:
        first = _fetch_fmp("AAPL")
        second = _fetch_fmp("AAPL")

    assert first["consensus_status"] == "temporary_error"
    assert second == first
    mock_get.assert_called_once()


def test_fmp_subscription_limit_is_cached_per_ticker_without_blocking_others(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    responses = [
        _response({
            "Error Message": (
                "Premium Query Parameter: 'Special Endpoint : This value set for "
                "'symbol' is not available under your current subscription"
            ),
        }, status_code=402),
        _response([]),
    ]

    with patch("core.data.price_target_consensus.requests.get", side_effect=responses) as mock_get:
        limited = _fetch_fmp("MU")
        cached = _fetch_fmp("MU")
        other = _fetch_fmp("AAPL")

    assert limited["consensus_status"] == "subscription_limited"
    assert limited["consensus_message"] == "현재 FMP 요금제에서 이 종목의 목표주가 조회를 지원하지 않습니다."
    assert cached == limited
    assert other["consensus_status"] == "no_data"
    assert mock_get.call_count == 2


def test_fmp_non_limit_dict_payload_uses_short_cache(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    response = _response({"Error Message": "internal upstream failure"})

    with patch("core.data.price_target_consensus.requests.get", return_value=response) as mock_get:
        first = _fetch_fmp("AAPL")
        second = _fetch_fmp("AAPL")

    assert first["consensus_status"] == "temporary_error"
    assert second == first
    mock_get.assert_called_once()


@pytest.mark.parametrize("payload", [[None], ["bad-row"]])
def test_fmp_non_dict_first_row_uses_short_cache(monkeypatch, payload):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    response = _response(payload)

    with patch("core.data.price_target_consensus.requests.get", return_value=response) as mock_get:
        first = _fetch_fmp("AAPL")
        second = _fetch_fmp("AAPL")

    assert first["consensus_status"] == "temporary_error"
    assert second == first
    mock_get.assert_called_once()


def test_fmp_empty_list_uses_daily_cache(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    response = _response([])

    with patch("core.data.price_target_consensus.requests.get", return_value=response) as mock_get:
        first = _fetch_fmp("AAPL")
        second = _fetch_fmp("AAPL")

    assert first["consensus_status"] == "no_data"
    assert second == first
    mock_get.assert_called_once()


@pytest.mark.parametrize("payload", [[{}], [{
    "targetConsensus": "bad",
    "targetMedian": "0",
    "targetLow": None,
    "targetHigh": "",
}]])
def test_fmp_row_without_valid_targets_uses_no_data_daily_cache(monkeypatch, payload):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    response = _response(payload)

    with patch("core.data.price_target_consensus.requests.get", return_value=response) as mock_get:
        first = _fetch_fmp("AAPL")
        second = _fetch_fmp("AAPL")

    assert first["consensus_status"] == "no_data"
    assert second == first
    mock_get.assert_called_once()


def test_fmp_target_fields_are_normalized_to_positive_numbers(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    response = _response([{
        "targetConsensus": "1,200.5",
        "targetMedian": "0",
        "targetLow": "900",
        "targetHigh": "bad",
    }])

    with patch("core.data.price_target_consensus.requests.get", return_value=response):
        result = _fetch_fmp("AAPL")

    assert result["consensus_status"] == "ok"
    assert result["target_mean"] == 1200.5
    assert result["target_median"] is None
    assert result["target_low"] == 900
    assert result["target_high"] is None


def test_fmp_missing_key_skips_request(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)

    with patch("core.data.price_target_consensus.requests.get") as mock_get:
        result = _fetch_fmp("AAPL")

    assert result["consensus_status"] == "missing_key"
    mock_get.assert_not_called()


@pytest.mark.parametrize("status_code", [401, 403])
def test_fmp_http_auth_error_is_missing_key(monkeypatch, status_code):
    monkeypatch.setenv("FMP_API_KEY", "secret")

    with patch(
        "core.data.price_target_consensus.requests.get",
        return_value=_response({}, status_code=status_code),
    ):
        result = _fetch_fmp("AAPL")

    assert result["consensus_status"] == "missing_key"
    assert result["consensus_message"] == "FMP API 키가 없거나 유효하지 않습니다."


def test_aggregate_kis_reports_uses_recent_latest_report_per_firm():
    rows = [
        {"stck_bsop_date": "20260601", "hts_goal_prc": "80000", "mbcr_name": "A", "stck_prdy_clpr": "60000"},
        {"stck_bsop_date": "20260501", "hts_goal_prc": "70000", "mbcr_name": "A", "stck_prdy_clpr": "59000"},
        {"stck_bsop_date": "20260401", "hts_goal_prc": "100000", "mbcr_name": "B", "stck_prdy_clpr": "58000"},
        {"stck_bsop_date": "20251130", "hts_goal_prc": "200000", "mbcr_name": "C", "stck_prdy_clpr": "57000"},
        {"stck_bsop_date": "20260601", "hts_goal_prc": "0", "mbcr_name": "D", "stck_prdy_clpr": "60000"},
    ]

    result = aggregate_kis_reports(rows, today=date(2026, 6, 2))

    assert result["consensus_status"] == "ok"
    assert result["consensus_source"] == "KIS"
    assert result["current_price"] == 60000
    assert result["target_mean"] == 90000
    assert result["target_median"] == 90000
    assert result["target_low"] == 80000
    assert result["target_high"] == 100000
    assert result["upside_pct"] == 50
    assert result["analyst_count"] == 2
    assert result["consensus_as_of"] == "2026-06-01"


def test_aggregate_kis_reports_returns_no_data_when_no_valid_rows():
    result = aggregate_kis_reports(
        [{"stck_bsop_date": "20260601", "hts_goal_prc": "0", "mbcr_name": "A"}],
        today=date(2026, 6, 2),
    )

    assert result["consensus_status"] == "no_data"
    assert result["target_mean"] is None
    assert result["analyst_count"] == 0


def test_aggregate_kis_reports_does_not_restore_older_positive_target():
    result = aggregate_kis_reports(
        [
            {"stck_bsop_date": "20260601", "hts_goal_prc": "0", "mbcr_name": "A"},
            {"stck_bsop_date": "20260501", "hts_goal_prc": "70000", "mbcr_name": "A"},
        ],
        today=date(2026, 6, 2),
    )

    assert result["consensus_status"] == "no_data"
    assert result["analyst_count"] == 0


def test_kis_fetch_calls_invest_opinion_with_expected_params():
    response = _response({
        "rt_cd": "0",
        "output": [{
            "stck_bsop_date": "20260601",
            "hts_goal_prc": "80000",
            "mbcr_name": "A",
            "stck_prdy_clpr": "60000",
        }],
    })

    with patch("core.prices.kis._get_token", return_value="token"), \
         patch("core.prices.kis._headers", return_value={"tr_id": "FHKST663300C0"}) as mock_headers, \
         patch("core.data.price_target_consensus.date", FixedDate), \
         patch("core.data.price_target_consensus.requests.get", return_value=response) as mock_get:
        result = fetch_price_target_consensus("005930.KS")

    assert result["target_mean"] == 80000
    mock_headers.assert_called_once_with("FHKST663300C0", "token")
    assert mock_get.call_args.args[0].endswith("/uapi/domestic-stock/v1/quotations/invest-opinion")
    assert mock_get.call_args.kwargs["params"] == {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_COND_SCR_DIV_CODE": "16633",
        "FID_INPUT_ISCD": "005930",
        "FID_INPUT_DATE_1": "20251202",
        "FID_INPUT_DATE_2": "20260602",
    }


def test_kis_kq_ticker_uses_domestic_route():
    response = _response({"rt_cd": "0", "output": []})

    with patch("core.prices.kis._get_token", return_value="token"), \
         patch("core.data.price_target_consensus.requests.get", return_value=response) as mock_get:
        result = fetch_price_target_consensus("035720.KQ")

    assert result["consensus_source"] == "KIS"
    assert mock_get.call_args.kwargs["params"]["FID_INPUT_ISCD"] == "035720"


def test_kis_missing_token_skips_request():
    with patch("core.prices.kis._get_token", return_value=None), \
         patch("core.data.price_target_consensus.requests.get") as mock_get:
        result = fetch_price_target_consensus("005930.KS")

    assert result["consensus_status"] == "missing_key"
    mock_get.assert_not_called()


def test_kis_rate_limit_uses_short_cache():
    response = _response({"rt_cd": "1", "msg1": "rate limit reached"}, status_code=429)

    with patch("core.prices.kis._get_token", return_value="token"), \
         patch("core.data.price_target_consensus.requests.get", return_value=response) as mock_get:
        first = fetch_price_target_consensus("005930.KS")
        second = fetch_price_target_consensus("005930.KS")

    assert first["consensus_status"] == "rate_limited"
    assert second == first
    mock_get.assert_called_once()


def test_kis_non_json_http_429_is_rate_limited():
    response = _response(None, status_code=429)
    response.json.side_effect = ValueError("not json")

    with patch("core.prices.kis._get_token", return_value="token"), \
         patch("core.data.price_target_consensus.requests.get", return_value=response):
        result = fetch_price_target_consensus("005930.KS")

    assert result["consensus_status"] == "rate_limited"


def test_kis_temporary_error_uses_short_cache():
    response = _response({"rt_cd": "1", "msg1": "temporary error"}, status_code=500)

    with patch("core.prices.kis._get_token", return_value="token"), \
         patch("core.data.price_target_consensus.requests.get", return_value=response) as mock_get:
        first = fetch_price_target_consensus("005930.KS")
        second = fetch_price_target_consensus("005930.KS")

    assert first["consensus_status"] == "temporary_error"
    assert second == first
    mock_get.assert_called_once()


@pytest.mark.parametrize("status_code", [401, 403])
def test_kis_http_auth_error_is_missing_key(status_code):
    response = _response({}, status_code=status_code)

    with patch("core.prices.kis._get_token", return_value="token"), \
         patch("core.data.price_target_consensus.requests.get", return_value=response):
        result = fetch_price_target_consensus("005930.KS")

    assert result["consensus_status"] == "missing_key"
    assert result["consensus_message"] == "KIS API 키가 없거나 유효하지 않습니다."


@pytest.mark.parametrize("message", [
    "유효하지 않은 token입니다.",
    "appkey 인증에 실패했습니다.",
])
def test_kis_nonzero_rt_cd_auth_message_is_missing_key(message):
    response = _response({"rt_cd": "1", "msg1": message})

    with patch("core.prices.kis._get_token", return_value="token"), \
         patch("core.data.price_target_consensus.requests.get", return_value=response):
        result = fetch_price_target_consensus("005930.KS")

    assert result["consensus_status"] == "missing_key"
    assert result["consensus_message"] == "KIS API 키가 없거나 유효하지 않습니다."


@pytest.mark.parametrize("message", [
    "인증 서버 일시 장애입니다.",
    "token 발급 서버가 일시적으로 응답하지 않습니다.",
    "token 발급 서버에 여유가 없습니다.",
    "인증 서버에 연결할 수 없습니다.",
    "인증 정보를 확인해 주세요.",
])
def test_kis_transient_auth_server_message_is_temporary_error(message):
    response = _response({"rt_cd": "1", "msg1": message})

    with patch("core.prices.kis._get_token", return_value="token"), \
         patch("core.data.price_target_consensus.requests.get", return_value=response):
        result = fetch_price_target_consensus("005930.KS")

    assert result["consensus_status"] == "temporary_error"


@pytest.mark.parametrize("payload", [[], {"rt_cd": "0", "output": {}}, {"rt_cd": "0", "output": [None]}])
def test_kis_malformed_payload_uses_short_cache(payload):
    response = _response(payload)

    with patch("core.prices.kis._get_token", return_value="token"), \
         patch("core.data.price_target_consensus.requests.get", return_value=response) as mock_get:
        first = fetch_price_target_consensus("005930.KS")
        second = fetch_price_target_consensus("005930.KS")

    assert first["consensus_status"] == "temporary_error"
    assert second == first
    mock_get.assert_called_once()


@pytest.mark.parametrize("rows", [[], [{
    "stck_bsop_date": "20260601",
    "hts_goal_prc": "80000",
    "mbcr_name": "A",
    "stck_prdy_clpr": "60000",
}]])
def test_kis_normal_result_uses_daily_cache(rows):
    response = _response({"rt_cd": "0", "output": rows})

    with patch("core.prices.kis._get_token", return_value="token"), \
         patch("core.data.price_target_consensus.requests.get", return_value=response) as mock_get:
        first = fetch_price_target_consensus("005930.KS")
        second = fetch_price_target_consensus("005930.KS")

    assert second == first
    mock_get.assert_called_once()


def test_fetch_prunes_stale_daily_and_expired_short_cache(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret")
    consensus._daily_cache[(date(2026, 6, 1), "OLD")] = {"consensus_status": "ok"}
    consensus._short_cache["OLD"] = (0, {"consensus_status": "temporary_error"})

    with patch("core.data.price_target_consensus.date", FixedDate), \
         patch("core.data.price_target_consensus.time.monotonic", return_value=10), \
         patch("core.data.price_target_consensus.requests.get", return_value=_response([])):
        fetch_price_target_consensus("AAPL")

    assert consensus._daily_cache == {(date(2026, 6, 2), "AAPL"): {
        "consensus_status": "no_data",
        "consensus_message": "미국 목표주가 컨센서스 데이터가 없습니다.",
        "consensus_source": "FMP",
        "retry_after": None,
        "current_price": None,
        "target_mean": None,
        "target_median": None,
        "target_low": None,
        "target_high": None,
        "upside_pct": None,
        "analyst_count": None,
        "consensus_as_of": None,
        "fallback_used": False,
        "consensus_attempts": [],
    }}
    assert consensus._short_cache == {}
