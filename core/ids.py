"""종목 ID 정규화 — DB/UI는 yfinance 형식, KIS 호출 직전에만 변환."""


def to_yf(ticker: str) -> str:
    """KIS 형식 → yfinance 형식.

    '005930'      → '005930.KS'
    '035720'      → '035720.KS'  (KOSDAQ도 .KS 입력 시 그대로)
    '005930.KS'   → '005930.KS'  (이미 변환된 경우)
    'AAPL'        → 'AAPL'
    """
    t = ticker.strip().upper()
    if "." in t:
        return t
    if t.isdigit() and len(t) == 6:
        return f"{t}.KS"
    return t


def to_kis_domestic(ticker: str) -> tuple[str, str]:
    """yfinance 형식 → KIS 국내 (종목코드, 시장구분).

    '005930.KS' → ('005930', 'J')   KOSPI
    '035720.KQ' → ('035720', 'Q')   KOSDAQ
    """
    t = ticker.strip().upper()
    if t.endswith(".KS"):
        return t[:-3], "J"
    if t.endswith(".KQ"):
        return t[:-3], "Q"
    raise ValueError(f"국내 종목이 아닙니다: {ticker}")


def to_kis_overseas(ticker: str) -> tuple[str, str]:
    """yfinance 형식 → KIS 해외 (거래소코드, 종목코드).

    'AAPL'  → ('NASD', 'AAPL')
    'MSFT'  → ('NASD', 'MSFT')
    현재는 미국 나스닥 기본값; 필요 시 거래소 매핑 테이블 확장.
    """
    t = ticker.strip().upper()
    return "NASD", t


def detect_currency(ticker: str) -> str:
    """티커로 기준 통화 추론."""
    t = ticker.strip().upper()
    if t.endswith(".KS") or t.endswith(".KQ"):
        return "KRW"
    return "USD"


def is_domestic(ticker: str) -> bool:
    t = ticker.strip().upper()
    return t.endswith(".KS") or t.endswith(".KQ")
