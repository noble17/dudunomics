"""OpenDART 기반 국내 성장주 필수 지표 수집/계산."""
from __future__ import annotations

import os
import re
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any
from xml.etree import ElementTree

import httpx


_BASE = "https://opendart.fss.or.kr/api"
_CLIENT = httpx.Client(timeout=20, follow_redirects=True)


@dataclass(frozen=True)
class DartSnapshot:
    ticker: str
    market_cap_krw: float | None = None
    operating_margin: float | None = None
    current_ratio: float | None = None
    roic: float | None = None
    operating_cashflow: float | None = None
    capex: float | None = None
    fcf_yield: float | None = None
    data_coverage: dict[str, Any] = field(default_factory=dict)


def parse_corp_codes(xml_text: str | bytes) -> dict[str, str]:
    """OpenDART corpCode.xml 내용에서 {stock_code: corp_code}를 만든다."""
    if isinstance(xml_text, bytes):
        xml_text = xml_text.decode("utf-8", errors="ignore")
    root = ElementTree.fromstring(xml_text)
    result: dict[str, str] = {}
    for item in root.findall(".//list"):
        corp_code = (item.findtext("corp_code") or "").strip()
        stock_code = (item.findtext("stock_code") or "").strip()
        if corp_code and stock_code:
            result[stock_code] = corp_code
    return result


def parse_corp_code_zip(content: bytes) -> dict[str, str]:
    with zipfile.ZipFile(BytesIO(content)) as zf:
        name = next((n for n in zf.namelist() if n.lower().endswith(".xml")), None)
        if not name:
            return {}
        return parse_corp_codes(zf.read(name))


def build_snapshot_from_rows(
    ticker: str,
    rows: list[dict],
    *,
    market_cap_krw: float | None,
) -> DartSnapshot:
    income_values = _row_values(rows, {"IS", "CIS"})
    balance_values = _row_values(rows, {"BS"})
    cashflow_values = _row_values(rows, {"CF"})
    revenue = _first(income_values, "매출액", "수익(매출액)", "영업수익")
    operating_income = _first(income_values, "영업이익")
    current_assets = _first(balance_values, "유동자산")
    current_liabilities = _first(balance_values, "유동부채")
    equity = _first(balance_values, "자본총계")
    cash = _first(balance_values, "현금및현금성자산")
    pretax_income = _first(income_values, "법인세비용차감전순이익", "법인세비용차감전 계속사업이익")
    tax_expense = _first(income_values, "법인세비용")
    operating_cashflow = _first(cashflow_values, "영업활동 현금흐름", "영업활동으로 인한 현금흐름")
    capex = _first_matching(cashflow_values, ("유형자산", "취득"))
    debt = sum(v for k, v in balance_values.items() if any(token in k for token in ("차입금", "사채")))

    operating_margin = _safe_div(operating_income, revenue)
    current_ratio = _safe_div(current_assets, current_liabilities)
    effective_tax_rate = _safe_div(tax_expense, pretax_income)
    if effective_tax_rate is None or effective_tax_rate < 0 or effective_tax_rate > 1:
        effective_tax_rate = 0.25

    invested_capital = None
    if equity is not None:
        invested_capital = equity + debt - (cash or 0)
    nopat = operating_income * (1 - effective_tax_rate) if operating_income is not None else None
    roic = _safe_div(nopat, invested_capital)

    capex_abs = abs(capex) if capex is not None else None
    fcf_yield = None
    if operating_cashflow is not None and capex_abs is not None and market_cap_krw:
        fcf_yield = (operating_cashflow - capex_abs) / market_cap_krw

    required = {
        "operating_margin": operating_margin,
        "current_ratio": current_ratio,
        "roic": roic,
        "operating_cashflow": operating_cashflow,
        "capex": capex_abs,
        "fcf_yield": fcf_yield,
    }
    missing = [name for name, value in required.items() if value is None]

    return DartSnapshot(
        ticker=ticker,
        market_cap_krw=market_cap_krw,
        operating_margin=operating_margin,
        current_ratio=current_ratio,
        roic=roic,
        operating_cashflow=operating_cashflow,
        capex=capex_abs,
        fcf_yield=fcf_yield,
        data_coverage={
            "dart_required_complete": not missing,
            "missing": missing,
        },
    )


def fetch_dart_snapshot(
    ticker: str,
    *,
    market_cap_krw: float | None,
    bsns_year: int | None = None,
) -> DartSnapshot:
    """OpenDART에서 국내 성장주 필수 지표를 가져온다."""
    api_key = os.getenv("DART_API_KEY")
    if not api_key:
        raise RuntimeError("DART_API_KEY가 없어 국내 성장주 완전 지원 데이터를 수집할 수 없습니다.")
    code = ticker.upper().split(".")[0]
    corp_code = fetch_corp_code_map(api_key).get(code)
    if not corp_code:
        raise RuntimeError(f"OpenDART corp_code를 찾을 수 없습니다: {ticker}")

    from datetime import date
    year = bsns_year or date.today().year
    rows: list[dict] = []
    for candidate_year in (year, year - 1):
        for report_code in ("11014", "11012", "11013", "11011"):
            rows = _fetch_statement_rows(api_key, corp_code, candidate_year, report_code, "CFS")
            if not rows:
                rows = _fetch_statement_rows(api_key, corp_code, candidate_year, report_code, "OFS")
            if rows:
                break
        if rows:
            break
    return build_snapshot_from_rows(ticker, rows, market_cap_krw=market_cap_krw)


_CORP_CODE_CACHE: dict[str, str] | None = None


def fetch_corp_code_map(api_key: str) -> dict[str, str]:
    global _CORP_CODE_CACHE
    if _CORP_CODE_CACHE is not None:
        return _CORP_CODE_CACHE
    resp = _CLIENT.get(f"{_BASE}/corpCode.xml", params={"crtfc_key": api_key})
    resp.raise_for_status()
    _CORP_CODE_CACHE = parse_corp_code_zip(resp.content)
    return _CORP_CODE_CACHE


def _fetch_statement_rows(
    api_key: str,
    corp_code: str,
    year: int,
    report_code: str,
    fs_div: str,
) -> list[dict]:
    resp = _CLIENT.get(
        f"{_BASE}/fnlttSinglAcntAll.json",
        params={
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": report_code,
            "fs_div": fs_div,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        return []
    return data.get("list") or []


def _row_values(rows: list[dict], statement_divs: set[str] | None = None) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in rows:
        if statement_divs is not None and row.get("sj_div") not in statement_divs:
            continue
        name = _clean_name(str(row.get("account_nm") or ""))
        if not name:
            continue
        value = _parse_amount(row.get("thstrm_add_amount")) if row.get("thstrm_add_amount") else None
        if value is None:
            value = _parse_amount(row.get("thstrm_amount"))
        if value is not None:
            result[name] = value
    return result


def _clean_name(name: str) -> str:
    return re.sub(r"\s+", "", name.replace(" ", ""))


def _parse_amount(raw: Any) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "")
    if not text or text == "-":
        return None
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        return float(text)
    except ValueError:
        return None


def _first(values: dict[str, float], *names: str) -> float | None:
    for name in names:
        cleaned = _clean_name(name)
        if cleaned in values:
            return values[cleaned]
    return None


def _first_matching(values: dict[str, float], tokens: tuple[str, ...]) -> float | None:
    cleaned_tokens = tuple(_clean_name(t) for t in tokens)
    for name, value in values.items():
        if all(token in name for token in cleaned_tokens):
            return value
    return None


def _safe_div(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den
