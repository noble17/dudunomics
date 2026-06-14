"""ChoiceStock public summary page collector.

정책:
- 비로그인 공개 summary HTML만 요청한다.
- 종목당 하루 1회만 외부 요청하고 이후에는 DuckDB 캐시를 사용한다.
- 점수/분석문구/디자인은 저장하지 않고, 재무 숫자와 뉴스 링크만 저장한다.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

import core.repository as repo

log = logging.getLogger(__name__)

BASE_URL = "https://www.choicestock.co.kr"
SOURCE_NAME = "ChoiceStock public page"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; dudunomics/1.0; personal research)",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}
_CLIENT = httpx.Client(headers=_HEADERS, timeout=15, follow_redirects=True)
_SKIP_SUFFIXES = (".KS", ".KQ", ".T", ".HK", ".SS", ".SZ")


def is_supported_public_ticker(ticker: str) -> bool:
    upper = ticker.upper()
    if any(upper.endswith(suffix) for suffix in _SKIP_SUFFIXES):
        return False
    return not upper.isdigit()


def _parse_float(text: str | None) -> float | None:
    if text is None:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if not cleaned or cleaned in {"-", "."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_chart(html: str, container_id: str) -> list[dict[str, Any]]:
    scripts = re.findall(r"<script[^>]*>(?P<script>.*?)</script>", html, re.DOTALL)
    script = next((s for s in scripts if f"newDetailChart1('{container_id}'" in s), None)
    if not script:
        return []
    match = re.search(r"var value = \[(?P<value>.*?)\];", script, re.DOTALL)
    if not match:
        return []

    rows: list[dict[str, Any]] = []
    for item in re.finditer(r"\{(?P<body>.*?)}", match.group("value"), re.DOTALL):
        body = item.group("body")
        y_match = re.search(r"y\s*:\s*(?P<value>-?\d+(?:\.\d+)?)", body)
        date_match = re.search(r"date\s*:\s*'(?P<date>[^']+)'", body)
        if not y_match or not date_match:
            continue
        raw_period = date_match.group("date")
        year = raw_period[:4]
        if not year.isdigit():
            continue
        rows.append({
            "year": year,
            "period_end": raw_period.replace(" (예상)", ""),
            "value": float(y_match.group("value")),
            "is_estimate": "예상" in raw_period,
            "source": SOURCE_NAME,
        })
    return rows


def _parse_latest_report_date(html: str) -> str | None:
    match = re.search(r"최근실적발표\s*(?P<date>\d{2}\.\d{2}\.\d{2})", html)
    if not match:
        return None
    yy, mm, dd = match.group("date").split(".")
    return f"20{yy}.{mm}.{dd}"


def _parse_metrics(html: str) -> dict[str, Any]:
    tree = HTMLParser(html)
    table = tree.css_first(".financial_table_inner")
    result: dict[str, Any] = {
        "market_cap_m": None,
        "trailing_pe": None,
        "forward_pe": None,
        "peg": None,
        "price_to_sales": None,
        "as_of": None,
        "source": SOURCE_NAME,
    }
    if not table:
        return result

    text = table.text(separator=" ", strip=True)
    patterns = {
        "market_cap_m": r"시가총액\s+([\d,.\-]+)",
        "trailing_pe": r"\bPER\s+([\d,.\-]+)",
        "forward_pe": r"PER\(F\)\s+([\d,.\-]+)",
        "peg": r"\bPEG\s+([\d,.\-]+)",
        "price_to_sales": r"\bPSR\s+([\d,.\-]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            result[key] = _parse_float(match.group(1))

    as_of_match = re.search(r"(?P<date>\d{2}\.\d{2}\.\d{2})\s*기준", text)
    if as_of_match:
        yy, mm, dd = as_of_match.group("date").split(".")
        result["as_of"] = f"20{yy}.{mm}.{dd}"
    return result


def _parse_news(html: str) -> list[dict[str, Any]]:
    tree = HTMLParser(html)
    area = tree.css_first(".new_area")
    if not area:
        return []

    items: list[dict[str, Any]] = []
    for node in area.css(".list"):
        onclick = node.attributes.get("onclick", "")
        href_match = re.search(r"location\.href\s*=\s*'(?P<href>[^']+)'", onclick)
        title_node = node.css_first(".txt p.txt")
        date_node = node.css_first(".day p")
        tag_node = node.css_first(".tag")
        if not href_match or not title_node:
            continue
        items.append({
            "title": title_node.text(strip=True),
            "published_date": date_node.text(strip=True) if date_node else None,
            "url": urljoin(BASE_URL, href_match.group("href")),
            "site": SOURCE_NAME,
            "tag": tag_node.text(strip=True) if tag_node else None,
        })
    return items


def parse_public_summary(html: str, ticker: str, source_url: str) -> dict[str, Any]:
    """공개 summary HTML에서 내부 계산용 숫자와 뉴스 링크만 추출한다."""
    return {
        "ticker": ticker.upper(),
        "source": SOURCE_NAME,
        "source_url": source_url,
        "fetched_date": str(date.today()),
        "latest_report_date": _parse_latest_report_date(html),
        "revenue": _parse_chart(html, "containerfinancials1_1"),
        "eps": _parse_chart(html, "containerfinancials1_2"),
        "roe": _parse_chart(html, "containerfinancials1_3"),
        "metrics": _parse_metrics(html),
        "news": _parse_news(html),
    }


def get_public_summary(ticker: str, force: bool = False) -> dict[str, Any] | None:
    """오늘 수집분이 있으면 DB에서 반환하고, 없으면 공개 HTML을 1회 요청한다."""
    upper = ticker.upper()
    if not is_supported_public_ticker(upper):
        return None
    today = date.today()
    if not force:
        cached = repo.get_choicestock_public_snapshot(upper, today)
        if cached:
            return cached

    source_url = f"{BASE_URL}/search/summary/{upper}"
    try:
        resp = _CLIENT.get(source_url)
        resp.raise_for_status()
    except Exception as e:
        log.debug("ChoiceStock public summary fetch 실패 (%s): %s", upper, e)
        return repo.get_latest_choicestock_public_snapshot(upper)

    data = parse_public_summary(resp.text, upper, source_url)
    if data["revenue"] or data["eps"] or data["roe"] or data["metrics"] or data["news"]:
        repo.upsert_choicestock_public_snapshot(upper, today, source_url, data)
    return data
