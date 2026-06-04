"""미국 FMP 및 국내 KIS 목표주가 컨센서스 조회."""
from __future__ import annotations

import calendar
import os
import re
import time
from datetime import date, datetime
from datetime import timedelta
from statistics import median
from typing import Any

import requests
from selectolax.parser import HTMLParser

_FMP_URL = "https://financialmodelingprep.com/stable/price-target-consensus"
_FINVIZ_URL = "https://finviz.com/stock?t={ticker}&p=d"
_STOCKANALYSIS_URL = "https://stockanalysis.com/stocks/{ticker}/forecast/"
_FINVIZ_DATE_FORMAT = "%b-%d-%y"
_PUBLIC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; dudunomics/1.0; research use)",
    "Accept-Language": "en-US,en;q=0.9",
}
_KIS_PATH = "/uapi/domestic-stock/v1/quotations/invest-opinion"
_SHORT_CACHE_TTL_SECONDS = 5 * 60

_daily_cache: dict[tuple[date, str], dict] = {}
_fallback_daily_cache: dict[tuple[date, str, str], dict] = {}
_short_cache: dict[str, tuple[float, dict]] = {}
_fmp_rate_limited_on: date | None = None
_fallback_rate_limited_on: dict[str, date] = {}


def _reset_cache() -> None:
    """테스트 및 운영 진단용 메모리 캐시 초기화."""
    global _fmp_rate_limited_on
    _daily_cache.clear()
    _fallback_daily_cache.clear()
    _short_cache.clear()
    _fallback_rate_limited_on.clear()
    _fmp_rate_limited_on = None


def _result(status: str, message: str, source: str, **values: Any) -> dict:
    result = {
        "consensus_status": status,
        "consensus_message": message,
        "consensus_source": source,
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
    }
    result.update(values)
    return result


def _months_before(day: date, months: int) -> date:
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def _number(value: Any) -> float | None:
    try:
        number = float(str(value).replace(",", ""))
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def _is_rate_limited(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    texts = [
        str(data[key]).lower()
        for key in ("Error Message", "message", "msg1", "error")
        if key in data
    ]
    return any(
        term in text
        for text in texts
        for term in ("rate limit", "limit reached", "quota", "upgrade your plan")
    )


def _is_auth_error(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    text = str(data.get("msg1", "")).lower()
    has_auth_subject = any(term in text for term in ("인증", "token", "appkey"))
    has_failure_context = any(
        term in text
        for term in (
            "유효하지 않",
            "invalid",
            "만료",
            "expired",
            "실패",
            "fail",
            "missing",
            "not found",
            "설정되지 않",
            "존재하지 않",
        )
    )
    return has_auth_subject and has_failure_context


def _short_cached(ticker: str) -> dict | None:
    cached = _short_cache.get(ticker)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    _short_cache.pop(ticker, None)
    return None


def _cache_short(ticker: str, result: dict) -> dict:
    _short_cache[ticker] = (time.monotonic() + _SHORT_CACHE_TTL_SECONDS, result)
    return result


def _prune_cache() -> None:
    today = date.today()
    now = time.monotonic()
    for key in list(_daily_cache):
        if key[0] != today:
            _daily_cache.pop(key)
    for key in list(_fallback_daily_cache):
        if key[0] != today:
            _fallback_daily_cache.pop(key)
    for ticker, cached in list(_short_cache.items()):
        if cached[0] <= now:
            _short_cache.pop(ticker)


def aggregate_kis_reports(rows: list[dict], today: date | None = None) -> dict:
    """최근 6개월 KIS 리포트를 증권사별 최신 의견으로 집계한다."""
    today = today or date.today()
    cutoff = _months_before(today, 6)
    latest_by_firm: dict[str, tuple[date, dict]] = {}

    for row in rows:
        try:
            report_date = datetime.strptime(str(row.get("stck_bsop_date", "")), "%Y%m%d").date()
        except ValueError:
            continue
        firm = str(row.get("mbcr_name", "")).strip()
        if not firm or not cutoff <= report_date <= today:
            continue
        previous = latest_by_firm.get(firm)
        if not previous or report_date > previous[0]:
            latest_by_firm[firm] = (report_date, row)

    reports = [
        (report_date, target, row)
        for report_date, row in latest_by_firm.values()
        if (target := _number(row.get("hts_goal_prc")))
    ]
    if not reports:
        return _result(
            "no_data",
            "최근 6개월 내 유효한 목표주가 리포트가 없습니다.",
            "KIS",
            analyst_count=0,
        )

    targets = [report[1] for report in reports]
    latest_report = max(reports, key=lambda report: report[0])
    current_price = _number(latest_report[2].get("stck_prdy_clpr"))
    target_mean = sum(targets) / len(targets)
    upside_pct = ((target_mean - current_price) / current_price * 100) if current_price else None
    return _result(
        "ok",
        "최근 6개월 증권사 목표주가 컨센서스입니다.",
        "KIS",
        current_price=current_price,
        target_mean=target_mean,
        target_median=median(targets),
        target_low=min(targets),
        target_high=max(targets),
        upside_pct=upside_pct,
        analyst_count=len(targets),
        consensus_as_of=latest_report[0].isoformat(),
    )


def fetch_price_target_consensus(ticker: str) -> dict:
    """티커 시장에 맞는 목표주가 컨센서스를 조회한다."""
    _prune_cache()
    normalized = ticker.strip().upper()
    if normalized.endswith((".KS", ".KQ")):
        return _fetch_kis(normalized)
    return _fetch_us(normalized)


def _with_attempts(result: dict, attempts: list[dict], fallback_used: bool) -> dict:
    return {**result, "fallback_used": fallback_used, "consensus_attempts": attempts}


def _fetch_us(ticker: str) -> dict:
    attempts = []
    fmp = _fetch_fmp(ticker)
    attempts.append({"source": "FMP", "status": fmp["consensus_status"]})
    if fmp["consensus_status"] == "ok":
        return _with_attempts(fmp, attempts, False)

    finviz = _fetch_finviz(ticker)
    attempts.append({"source": "FINVIZ", "status": finviz["consensus_status"]})
    if finviz["consensus_status"] == "ok":
        return _with_attempts(finviz, attempts, True)

    stockanalysis = _fetch_stockanalysis(ticker)
    attempts.append({"source": "STOCKANALYSIS", "status": stockanalysis["consensus_status"]})
    return _with_attempts(stockanalysis, attempts, True)


def _fallback_cached(source: str, ticker: str) -> dict | None:
    return _fallback_daily_cache.get((date.today(), source, ticker))


def _cache_fallback(source: str, ticker: str, result: dict) -> dict:
    _fallback_daily_cache[(date.today(), source, ticker)] = result
    return result


def _fetch_finviz(ticker: str) -> dict:
    source = "FINVIZ"
    today = date.today()
    cached = _fallback_cached(source, ticker)
    if cached:
        return cached
    if _fallback_rate_limited_on.get(source) == today:
        return _result("rate_limited", "Finviz 조회 한도에 도달했습니다.", source)

    try:
        response = requests.get(_FINVIZ_URL.format(ticker=ticker), headers=_PUBLIC_HEADERS, timeout=10)
    except Exception:
        return _cache_fallback(source, ticker, _result("temporary_error", "Finviz 목표주가 조회 중 일시적인 오류가 발생했습니다.", source))
    if response.status_code == 429:
        _fallback_rate_limited_on[source] = today
        return _result("rate_limited", "Finviz 조회 한도에 도달했습니다.", source)
    if response.status_code >= 400:
        return _cache_fallback(source, ticker, _result("temporary_error", "Finviz 목표주가 조회 중 일시적인 오류가 발생했습니다.", source))

    cells = HTMLParser(response.text).css("td")
    target = next(
        (_number(cells[index + 1].text(strip=True)) for index, cell in enumerate(cells[:-1]) if cell.text(strip=True) == "Target Price"),
        None,
    )
    if target:
        history = _parse_finviz_rating_targets(response.text, target)
        return _cache_fallback(source, ticker, _result("ok", "Finviz 공개 목표주가입니다.", source, target_mean=target, **history))
    return _cache_fallback(source, ticker, _result("no_data", "Finviz 목표주가 데이터가 없습니다.", source))


def _parse_finviz_rating_targets(html: str, reference_target: float | None = None) -> dict:
    reports: list[tuple[date, str, float]] = []
    tree = HTMLParser(html)
    for row in tree.css("tr"):
        cells = [cell.text(strip=True) for cell in row.css("td")]
        if len(cells) < 5:
            continue
        report_date = _parse_finviz_date(cells[0])
        target = _parse_finviz_target_change(cells[4])
        analyst = cells[2].strip()
        if report_date and analyst and target:
            reports.append((report_date, analyst, target))

    if not reports:
        return {}

    latest_by_analyst: dict[str, tuple[date, float]] = {}
    for report_date, analyst, target in reports:
        previous = latest_by_analyst.get(analyst)
        if previous is None or report_date > previous[0]:
            latest_by_analyst[analyst] = (report_date, target)

    latest_reports = list(latest_by_analyst.values())
    latest_date = max(report_date for report_date, _ in latest_reports)
    recent_reports = [
        report
        for report in latest_reports
        if report[0] >= latest_date - timedelta(days=90)
    ]
    if recent_reports:
        latest_reports = recent_reports
    if reference_target:
        same_scale = [
            report
            for report in latest_reports
            if reference_target * 0.25 <= report[1] <= reference_target * 2.5
        ]
        if same_scale:
            latest_reports = same_scale
    targets = [target for _, target in latest_reports]
    return {
        "target_median": median(targets),
        "target_low": min(targets),
        "target_high": max(targets),
        "analyst_count": len(targets),
        "consensus_as_of": latest_date.isoformat(),
    }


def _parse_finviz_date(value: str) -> date | None:
    try:
        return datetime.strptime(value.strip(), _FINVIZ_DATE_FORMAT).date()
    except ValueError:
        return None


def _parse_finviz_target_change(value: str) -> float | None:
    matches = re.findall(r"\$([\d,]+(?:\.\d+)?)", value)
    return _number(matches[-1]) if matches else None


def _fetch_stockanalysis(ticker: str) -> dict:
    source = "STOCKANALYSIS"
    today = date.today()
    cached = _fallback_cached(source, ticker)
    if cached:
        return cached
    if _fallback_rate_limited_on.get(source) == today:
        return _result("rate_limited", "StockAnalysis 조회 한도에 도달했습니다.", source)

    try:
        response = requests.get(_STOCKANALYSIS_URL.format(ticker=ticker.lower()), headers=_PUBLIC_HEADERS, timeout=10)
    except Exception:
        return _cache_fallback(source, ticker, _result("temporary_error", "StockAnalysis 목표주가 조회 중 일시적인 오류가 발생했습니다.", source))
    if response.status_code == 429:
        _fallback_rate_limited_on[source] = today
        return _result("rate_limited", "StockAnalysis 조회 한도에 도달했습니다.", source)
    if response.status_code >= 400:
        return _cache_fallback(source, ticker, _result("temporary_error", "StockAnalysis 목표주가 조회 중 일시적인 오류가 발생했습니다.", source))

    text = HTMLParser(response.text).text(separator=" ", strip=True)
    match = re.search(r"average price target(?: is| of)?\s*\$([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
    target = _number(match.group(1)) if match else None
    if target:
        return _cache_fallback(source, ticker, _result("ok", "StockAnalysis 공개 평균 목표주가입니다.", source, target_mean=target))
    return _cache_fallback(source, ticker, _result("no_data", "StockAnalysis 목표주가 데이터가 없습니다.", source))


def _fetch_fmp(ticker: str) -> dict:
    global _fmp_rate_limited_on
    today = date.today()
    cached = _daily_cache.get((today, ticker))
    if cached:
        return cached
    cached = _short_cached(ticker)
    if cached:
        return cached
    if _fmp_rate_limited_on == today:
        return _result("rate_limited", "FMP API 호출 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.", "FMP")
    api_key = os.environ.get("FMP_API_KEY")
    if not api_key:
        return _result("missing_key", "FMP_API_KEY가 설정되지 않아 미국 목표주가를 조회할 수 없습니다.", "FMP")

    try:
        response = requests.get(_FMP_URL, params={"symbol": ticker, "apikey": api_key}, timeout=10)
    except Exception:
        return _cache_short(ticker, _result("temporary_error", "FMP 목표주가 조회 중 일시적인 오류가 발생했습니다.", "FMP"))

    if response.status_code == 429:
        _fmp_rate_limited_on = today
        return _result("rate_limited", "FMP API 호출 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.", "FMP")
    if response.status_code in (401, 403):
        return _result("missing_key", "FMP API 키가 없거나 유효하지 않습니다.", "FMP")
    if response.status_code == 402:
        result = _result(
            "subscription_limited",
            "현재 FMP 요금제에서 이 종목의 목표주가 조회를 지원하지 않습니다.",
            "FMP",
        )
        _daily_cache[(today, ticker)] = result
        return result
    try:
        data = response.json()
    except Exception:
        return _cache_short(ticker, _result("temporary_error", "FMP 목표주가 조회 중 일시적인 오류가 발생했습니다.", "FMP"))
    if _is_rate_limited(data):
        _fmp_rate_limited_on = today
        return _result("rate_limited", "FMP API 호출 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.", "FMP")
    if response.status_code >= 400:
        return _cache_short(ticker, _result("temporary_error", "FMP 목표주가 조회 중 일시적인 오류가 발생했습니다.", "FMP"))
    if data == []:
        result = _result("no_data", "미국 목표주가 컨센서스 데이터가 없습니다.", "FMP")
    elif not isinstance(data, list) or not isinstance(data[0], dict):
        return _cache_short(ticker, _result("temporary_error", "FMP 목표주가 조회 중 일시적인 오류가 발생했습니다.", "FMP"))
    else:
        row = data[0]
        targets = {
            "target_mean": _number(row.get("targetConsensus")),
            "target_median": _number(row.get("targetMedian")),
            "target_low": _number(row.get("targetLow")),
            "target_high": _number(row.get("targetHigh")),
        }
        if any(targets.values()):
            result = _result("ok", "애널리스트 목표주가 컨센서스입니다.", "FMP", **targets)
        else:
            result = _result("no_data", "미국 목표주가 컨센서스 데이터가 없습니다.", "FMP")
    _daily_cache[(today, ticker)] = result
    return result


def _fetch_kis(ticker: str) -> dict:
    from core.prices.kis import KIS_BASE, _get_token, _headers

    today = date.today()
    cached = _daily_cache.get((today, ticker))
    if cached:
        return cached
    cached = _short_cached(ticker)
    if cached:
        return cached

    token = _get_token()
    if not token:
        return _result("missing_key", "KIS 인증 정보가 없어 국내 목표주가를 조회할 수 없습니다.", "KIS")

    code = ticker[:-3]
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_COND_SCR_DIV_CODE": "16633",
        "FID_INPUT_ISCD": code,
        "FID_INPUT_DATE_1": _months_before(today, 6).strftime("%Y%m%d"),
        "FID_INPUT_DATE_2": today.strftime("%Y%m%d"),
    }
    try:
        response = requests.get(
            f"{KIS_BASE}{_KIS_PATH}",
            params=params,
            headers=_headers("FHKST663300C0", token),
            timeout=10,
        )
    except Exception:
        return _cache_short(ticker, _result("temporary_error", "KIS 목표주가 조회 중 일시적인 오류가 발생했습니다.", "KIS"))

    if response.status_code == 429:
        return _cache_short(ticker, _result("rate_limited", "KIS API 호출 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.", "KIS"))
    if response.status_code in (401, 403):
        return _result("missing_key", "KIS API 키가 없거나 유효하지 않습니다.", "KIS")
    try:
        data = response.json()
    except Exception:
        return _cache_short(ticker, _result("temporary_error", "KIS 목표주가 조회 중 일시적인 오류가 발생했습니다.", "KIS"))
    if _is_rate_limited(data):
        return _cache_short(ticker, _result("rate_limited", "KIS API 호출 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.", "KIS"))
    if isinstance(data, dict) and str(data.get("rt_cd", "0")) != "0" and _is_auth_error(data):
        return _result("missing_key", "KIS API 키가 없거나 유효하지 않습니다.", "KIS")
    if response.status_code >= 400 or not isinstance(data, dict) or str(data.get("rt_cd", "0")) != "0":
        return _cache_short(ticker, _result("temporary_error", "KIS 목표주가 조회 중 일시적인 오류가 발생했습니다.", "KIS"))
    rows = data.get("output")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return _cache_short(ticker, _result("temporary_error", "KIS 목표주가 조회 중 일시적인 오류가 발생했습니다.", "KIS"))

    result = aggregate_kis_reports(rows, today=today)
    _daily_cache[(today, ticker)] = result
    return result
