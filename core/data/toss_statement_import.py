"""Toss Securities PDF statement parser for trade import."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from io import BytesIO

from core.ids import to_yf


@dataclass
class ParsedTrade:
    row_id: str
    traded_at: str
    ticker: str
    market: str | None
    trade_type: str
    quantity: float
    price: float
    currency: str
    fee: float
    note: str
    name: str
    raw_symbol: str
    needs_mapping: bool


_SKIP_LINE = re.compile(
    r"거래일자|수량단위|발급기준|조회 기간|요청 고객|성명|계좌|거래내역서|발급번호|종목 전체|원화-외화|거래구분 주식거래"
)
_KR_ROW = re.compile(
    r"^(?P<date>\d{4}\.\d{2}\.\d{2})\s+"
    r"(?P<kind>구매|판매)\s+"
    r"(?P<name>.+?)\s*\(A?(?P<code>[A-Z0-9]{6})\)\s+"
    r"(?P<nums>.+)$"
)
_OVERSEAS_ROW = re.compile(
    r"^(?P<date>\d{4}\.\d{2}\.\d{2})\s+"
    r"(?P<kind>구매|판매)\s+"
    r"(?P<name>.+?)\s*\((?P<isin>[A-Z]{2}[A-Z0-9]{10})\)\s+"
    r"(?P<fx>[\d,.]+)\s+"
    r"(?P<qty>[\d,.]+)\s+"
    r"(?P<tail>.+)$"
)


def _num(value: str) -> float:
    return float(value.replace(",", "").replace("$", "").strip())


def _date(value: str) -> str:
    return value.replace(".", "-")


def _row_id(parts: list[str]) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]


def _read_pdf_text(file_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf 패키지가 필요합니다.") from exc

    reader = PdfReader(BytesIO(file_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _records(text: str) -> list[str]:
    lines = [line.strip() for line in text.replace("\xa0", " ").splitlines() if line.strip()]
    result: list[str] = []
    current: str | None = None
    for line in lines:
        if re.match(r"^\d{4}\.\d{2}\.\d{2}\s+", line):
            if current:
                result.append(current)
            current = line
            continue
        if current and not _SKIP_LINE.search(line):
            if re.match(r"^\d+\s*/", line):
                continue
            current += " " + line
    if current:
        result.append(current)
    return result


def _internal_kr_ticker(code: str) -> str:
    return to_yf(code) if code.isdigit() else code.upper()


def parse_toss_statement_pdf(file_bytes: bytes) -> tuple[list[ParsedTrade], list[str]]:
    text = _read_pdf_text(file_bytes)
    trades: list[ParsedTrade] = []
    errors: list[str] = []

    for index, record in enumerate(_records(text), start=1):
        kr_match = _KR_ROW.match(record)
        if kr_match:
            nums = kr_match.group("nums").split()
            if len(nums) < 4:
                errors.append(f"{index}행: 숫자 컬럼 부족")
                continue
            fee = _num(nums[4]) if len(nums) > 4 else 0.0
            tax = _num(nums[5]) if len(nums) > 5 else 0.0
            code = kr_match.group("code").upper()
            traded_at = _date(kr_match.group("date"))
            trade_type = "BUY" if kr_match.group("kind") == "구매" else "SELL"
            qty = _num(nums[0])
            price = _num(nums[3])
            trades.append(ParsedTrade(
                row_id=_row_id([traded_at, code, trade_type, str(qty), str(price)]),
                traded_at=traded_at,
                ticker=_internal_kr_ticker(code),
                market="KRX",
                trade_type=trade_type,
                quantity=qty,
                price=price,
                currency="KRW",
                fee=fee + tax,
                note=f"Toss PDF import: {kr_match.group('name').strip()}",
                name=kr_match.group("name").strip(),
                raw_symbol=code,
                needs_mapping=False,
            ))
            continue

        overseas_match = _OVERSEAS_ROW.match(record)
        if overseas_match:
            tail = overseas_match.group("tail")
            dollars = re.findall(r"\$\s*([\d,.]+)", tail)
            if len(dollars) < 4:
                errors.append(f"{index}행: 해외 달러 컬럼 부족")
                continue
            isin = overseas_match.group("isin").upper()
            traded_at = _date(overseas_match.group("date"))
            trade_type = "BUY" if overseas_match.group("kind") == "구매" else "SELL"
            qty = _num(overseas_match.group("qty"))
            price = _num(dollars[2])
            fee = _num(dollars[3])
            trades.append(ParsedTrade(
                row_id=_row_id([traded_at, isin, trade_type, str(qty), str(price)]),
                traded_at=traded_at,
                ticker="",
                market="NASDAQ",
                trade_type=trade_type,
                quantity=qty,
                price=price,
                currency="USD",
                fee=fee,
                note=f"Toss PDF import: {overseas_match.group('name').strip()} ({isin})",
                name=overseas_match.group("name").strip(),
                raw_symbol=isin,
                needs_mapping=True,
            ))
            continue

        errors.append(f"{index}행: 파싱 실패")

    return trades, errors
