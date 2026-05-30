"""KIS Open API 시세 프로바이더 — 순수 REST HTTP 호출 (pykis 미사용).

토큰: POST /oauth2/tokenP (appkey + appsecret만 필요, HTS ID 불필요)
국내: GET /uapi/domestic-stock/v1/quotations/inquire-price         tr_id=FHKST01010100
해외: GET /uapi/overseas-price/v1/quotations/price-detail          tr_id=HHDFS76200200
정보: GET /uapi/domestic-stock/v1/quotations/search-info           tr_id=CTPF1604R
국내일봉: GET /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice  tr_id=FHKST03010100
해외일봉: GET /uapi/overseas-price/v1/quotations/dailyprice        tr_id=HHDFS76200200
"""
import json
import logging
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from core.ids import detect_currency, is_domestic, market_from_ticker, to_kis_domestic
from core.prices.base import Price, PriceProvider

log = logging.getLogger(__name__)

KIS_BASE = "https://openapi.koreainvestment.com:9443"

# pykis MARKET_TYPE → KIS EXCD
_MARKET_TO_EXCD: dict[str, str] = {
    "NASDAQ": "NAS", "NAS": "NAS",
    "NYSE": "NYS",   "NYS": "NYS",
    "AMEX": "AMS",   "AMS": "AMS",
    "TYO": "TSE",    "TSE": "TSE",
    "HKEX": "HKS",   "HKS": "HKS",
    "SSE": "SHS",    "SHS": "SHS",
    "SZSE": "SZS",   "SZS": "SZS",
    "HNX": "HNX",    "HSX": "HSX",
}

_EXCD_TO_MARKET: dict[str, str] = {
    "NAS": "NASDAQ", "NYS": "NYSE", "AMS": "AMEX",
    "TSE": "TYO",    "HKS": "HKEX", "SHS": "SSE",
    "SZS": "SZSE",   "HNX": "HNX",  "HSX": "HSX",
    "NASD": "NASDAQ", "NYSE": "NYSE",
}

_EXCD_TO_CURRENCY: dict[str, str] = {
    "NAS": "USD", "NYS": "USD", "AMS": "USD",
    "TSE": "JPY", "HKS": "HKD", "SHS": "CNY",
    "SZS": "CNY", "HNX": "VND", "HSX": "VND",
}

_DATA_DIR = Path(os.environ.get("DB_PATH", "data/dudunomics.duckdb")).parent
_TOKEN_FILE = _DATA_DIR / "kis_token.json"
_NAME_FILE = _DATA_DIR / "kis_names.json"
_TOKEN_TTL = 23 * 3600  # 23시간 (KIS 24시간 유효, 1시간 여유)
_CANO = "63241945"
_ACNT_PRDT_CD = "01"

# 메모리 1차 캐시 (프로세스 내)
_token_cache: dict = {}
_name_file_cache: dict[str, str] = {}  # 파일 기반 영구 이름 캐시 (메모리 미러)


def _load_names() -> dict[str, str]:
    """파일에서 이름 캐시 로드."""
    global _name_file_cache
    if _name_file_cache:
        return _name_file_cache
    try:
        _name_file_cache = json.loads(_NAME_FILE.read_text())
    except Exception:
        _name_file_cache = {}
    return _name_file_cache


def _save_name(ticker: str, name: str) -> None:
    """이름을 파일 캐시에 저장."""
    names = _load_names()
    names[ticker] = name
    try:
        _NAME_FILE.parent.mkdir(parents=True, exist_ok=True)
        _NAME_FILE.write_text(json.dumps(names, ensure_ascii=False))
    except Exception as e:
        log.warning("이름 캐시 파일 저장 실패: %s", e)


def _load_token_from_file() -> str | None:
    """파일에서 토큰 로드. 만료됐으면 None 반환."""
    try:
        data = json.loads(_TOKEN_FILE.read_text())
        if data.get("expires_at", 0) > time.time():
            _token_cache.update(data)
            return data["token"]
    except Exception:
        pass
    return None


def _save_token_to_file(token: str, expires_at: float) -> None:
    try:
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(json.dumps({"token": token, "expires_at": expires_at}))
    except Exception as e:
        log.warning("KIS 토큰 파일 저장 실패: %s", e)


def _get_token() -> str | None:
    """KIS 토큰 반환. 메모리 → 파일 → 신규 발급 순으로 시도."""
    now = time.time()

    # 1. 메모리 캐시
    if _token_cache.get("token") and _token_cache.get("expires_at", 0) > now:
        return _token_cache["token"]

    # 2. 파일 캐시 (재시작 후에도 유효한 토큰 재사용)
    token = _load_token_from_file()
    if token:
        log.info("KIS 토큰 파일 캐시 사용")
        return token

    # 3. 신규 발급
    appkey = os.environ.get("KIS_APPKEY", "")
    secretkey = os.environ.get("KIS_SECRETKEY", "")
    if not appkey or not secretkey:
        log.warning("KIS_APPKEY / KIS_SECRETKEY 환경변수 없음")
        return None

    try:
        res = requests.post(
            f"{KIS_BASE}/oauth2/tokenP",
            json={"grant_type": "client_credentials", "appkey": appkey, "appsecret": secretkey},
            timeout=10,
        )
        data = res.json()
        token = data.get("access_token")
        if not token:
            log.warning("KIS 토큰 발급 실패: %s", data)
            return None
        expires_at = now + _TOKEN_TTL
        _token_cache.update({"token": token, "expires_at": expires_at})
        _save_token_to_file(token, expires_at)
        log.info("KIS 토큰 발급 성공 (23시간 캐시)")
        return token
    except Exception as e:
        log.warning("KIS 토큰 오류: %s", e)
        return None


def _headers(tr_id: str, token: str) -> dict:
    return {
        "authorization": f"Bearer {token}",
        "appkey": os.environ.get("KIS_APPKEY", ""),
        "appsecret": os.environ.get("KIS_SECRETKEY", ""),
        "tr_id": tr_id,
        "custtype": "P",
        "content-type": "application/json; charset=utf-8",
    }


class KISPriceProvider(PriceProvider):
    """KIS Open API 직접 REST 호출. 실패 시 yfinance fallback."""

    def get_current_price(self, ticker: str) -> Price:
        prices = self.get_current_prices([ticker])
        if ticker in prices:
            return prices[ticker]
        raise RuntimeError(f"시세 조회 실패: {ticker}")

    def get_current_prices(
        self,
        tickers: list[str],
        markets: dict[str, str | None] | None = None,
    ) -> dict[str, Price]:
        result: dict[str, Price] = {}
        token = _get_token()

        for ticker in tickers:
            mkt = (markets or {}).get(ticker)
            try:
                if token:
                    price = (
                        self._fetch_domestic(ticker, token)
                        if is_domestic(ticker)
                        else self._fetch_overseas(ticker, mkt, token)
                    )
                else:
                    price = self._fetch_yfinance(ticker)
                result[ticker] = price
            except Exception as e:
                log.warning("시세 조회 실패 (%s): %s — yfinance 폴백", ticker, e)
                try:
                    result[ticker] = self._fetch_yfinance(ticker)
                except Exception as e2:
                    log.error("yfinance 폴백도 실패 (%s): %s", ticker, e2)

        return result

    # ── lookup ──────────────────────────────────────────────────────────────

    def lookup(self, ticker: str, market: str | None = None) -> dict | None:
        """티커 기본 정보 조회. KIS 우선, 실패 시 yfinance fallback."""
        t = ticker.strip().upper()
        pykis_market = market or market_from_ticker(t)
        token = _get_token()

        if token:
            if is_domestic(t):
                result = self._lookup_domestic(t, token)
                if result:
                    return result
            else:
                result = self._lookup_overseas(t, pykis_market, token)
                if result:
                    # KIS는 market/currency만 제공, 이름은 캐시 or yfinance로 보완
                    if result["name"] == t:
                        result["name"] = self._get_name(t, result["market"])
                    return result

        return self._lookup_yfinance(ticker, pykis_market)

    def _get_name(self, ticker: str, market: str | None) -> str:
        """종목명 반환. 파일 캐시 우선, 없으면 yfinance 조회 후 파일에 저장."""
        names = _load_names()
        if ticker in names:
            return names[ticker]
        yf_result = self._lookup_yfinance(ticker, market)
        name = (yf_result or {}).get("name") or ticker
        if name != ticker:
            _save_name(ticker, name)
        return name

    def _lookup_domestic(self, ticker: str, token: str) -> dict | None:
        """국내 종목 기본정보 조회 (CTPF1604R)."""
        try:
            code, _ = to_kis_domestic(ticker)
            res = requests.get(
                f"{KIS_BASE}/uapi/domestic-stock/v1/quotations/search-info",
                params={"PDNO": code, "PRDT_TYPE_CD": "300"},
                headers=_headers("CTPF1604R", token),
                timeout=10,
            )
            data = res.json()
            if data.get("rt_cd") != "0":
                log.debug("lookup 국내 실패 (%s): %s", ticker, data.get("msg1"))
                return None
            output = data.get("output", {})
            name = output.get("prdt_abrv_name") or output.get("prdt_name") or ticker
            return {"ticker": ticker, "name": name, "market": "KRX", "currency": "KRW"}
        except Exception as e:
            log.warning("_lookup_domestic 예외 (%s): %s", ticker, e)
            return None

    def _lookup_overseas(self, ticker: str, market: str | None, token: str) -> dict | None:
        """해외 종목 조회 — 지정 거래소 우선, 가격 없으면 NAS→NYS→AMS 순차 폴백."""
        _all = ["NAS", "NYS", "AMS"]
        if market:
            first = _MARKET_TO_EXCD.get(market.upper())
            excd_list = ([first] if first else []) + [e for e in _all if e != first]
        else:
            excd_list = _all

        for excd in excd_list:
            try:
                res = requests.get(
                    f"{KIS_BASE}/uapi/overseas-price/v1/quotations/price-detail",
                    params={"AUTH": "", "EXCD": excd, "SYMB": ticker},
                    headers=_headers("HHDFS76200200", token),
                    timeout=10,
                )
                data = res.json()
                if data.get("rt_cd") != "0":
                    continue
                output = data.get("output", {})
                last = float(output.get("last") or 0)
                if last <= 0:
                    continue
                resolved_market = _EXCD_TO_MARKET.get(excd, excd)
                currency = _EXCD_TO_CURRENCY.get(excd, "USD")
                return {
                    "ticker": ticker,
                    "name": ticker,  # 이름은 caller(_get_name)에서 보완
                    "market": resolved_market,
                    "currency": currency,
                }
            except Exception as e:
                log.debug("_lookup_overseas 예외 (%s/%s): %s", ticker, excd, e)

        return None

    def _lookup_yfinance(self, ticker: str, market: str | None = None) -> dict | None:
        """yfinance Search 기반 lookup. Ticker.info보다 rate limit 관대함."""
        _exch_map = {
            "NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ",
            "NYQ": "NYSE", "ASE": "AMEX",
            "KSC": "KRX", "KOE": "KRX",
            "JPX": "TYO", "TYO": "TYO",
        }
        try:
            import yfinance as yf
            result = yf.Search(ticker, max_results=5, news_count=0, raise_errors=False)
            for q in (result.quotes or []):
                if q.get("symbol", "").upper() != ticker.upper():
                    continue
                name = q.get("shortname") or q.get("longname") or ""
                if not name:
                    continue
                exch = q.get("exchange") or ""
                currency = detect_currency(ticker)
                resolved = market or _exch_map.get(exch, exch)
                return {"ticker": ticker, "name": name, "market": resolved, "currency": currency}
        except Exception as e:
            log.debug("_lookup_yfinance(Search) 실패 (%s): %s", ticker, e)
        return None

    # ── search ──────────────────────────────────────────────────────────────

    # Yahoo Finance exch 코드 → KIS market 코드 (국장/미장만 지원)
    _EXCH_TO_MARKET: dict[str, str] = {
        "KSC": "KRX",    # 한국거래소 (KOSPI)
        "KOE": "KRX",    # 코스닥
        "NMS": "NASDAQ", # NASDAQ Global Select
        "NGM": "NASDAQ", # NASDAQ Global Market
        "NCM": "NASDAQ", # NASDAQ Capital Market
        "BTS": "AMEX",   # BATS Trading (SNXX, UVXY 등 ETF) — KIS는 AMS로 조회
        "NYQ": "NYSE",
        "PCX": "AMEX",   # NYSE Arca (SPY, GLD, IWM 등 ETF) — KIS는 AMS로 조회
        "ASE": "AMEX",   # NYSE American (AMEX)
    }

    def search(self, query: str, max_results: int = 20) -> list[dict]:
        """키워드 종목 검색 (Yahoo Finance autocomplete v6 + v1 중복 이름 보완).

        국장(KRX)과 미장(NASDAQ/NYSE/AMEX)만 반환. market 필드 포함.
        """
        try:
            res = requests.get(
                "https://query2.finance.yahoo.com/v6/finance/autocomplete",
                params={"query": query, "region": "KR", "lang": "ko"},
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
                timeout=8,
            )
            res.raise_for_status()
            results = res.json().get("ResultSet", {}).get("Result", [])
            hits = []
            for q in results:
                sym = q.get("symbol", "")
                if not sym:
                    continue
                exch = q.get("exch") or ""
                market = self._EXCH_TO_MARKET.get(exch)
                if not market:
                    continue  # 국장/미장 이외 제외
                hits.append({
                    "ticker": sym,
                    "name": q.get("name") or "",
                    "exchange": q.get("exchDisp") or exch,
                    "market": market,
                    "type": q.get("typeDisp") or q.get("type") or "",
                })
                if len(hits) >= 8:
                    break

            # 같은 이름이 중복되면 v1/finance/search로 shortname 보완 (우선주 구분)
            name_counts: dict[str, int] = {}
            for h in hits:
                name_counts[h["name"]] = name_counts.get(h["name"], 0) + 1
            dups = {n for n, c in name_counts.items() if c > 1}
            if dups:
                for h in hits:
                    if h["name"] not in dups:
                        continue
                    try:
                        r2 = requests.get(
                            "https://query1.finance.yahoo.com/v1/finance/search",
                            params={"q": h["ticker"], "lang": "ko-KR", "region": "KR",
                                    "quotesCount": 3, "newsCount": 0},
                            headers={"User-Agent": "Mozilla/5.0"},
                            timeout=5,
                        )
                        for q2 in r2.json().get("quotes", []):
                            if q2.get("symbol") != h["ticker"]:
                                continue
                            shortname = q2.get("shortname") or ""
                            # "(NP)" 패턴을 한국어 "N우"로 변환
                            import re
                            m = re.search(r"\((\d*)P\)", shortname)
                            if m:
                                n = m.group(1)
                                # "1P" → "우", "2P" → "2우"
                                suffix = "우" if n in ("", "1") else f"{n}우"
                                # "(주)" 같은 접미 괄호 앞에 삽입
                                m2 = re.match(r'^(.+?)(\([^)]+\))$', h["name"])
                                if m2:
                                    h["name"] = f"{m2.group(1)}{suffix}{m2.group(2)}"
                                else:
                                    h["name"] = f"{h['name']}{suffix}"
                            break
                    except Exception:
                        pass

            return hits
        except Exception as e:
            log.warning("search 실패 (%s): %s", query, e)
            return []

    # ── 시세 조회 내부 메서드 ────────────────────────────────────────────────

    def _fetch_domestic(self, ticker: str, token: str) -> Price:
        code, _ = to_kis_domestic(ticker)
        res = requests.get(
            f"{KIS_BASE}/uapi/domestic-stock/v1/quotations/inquire-price",
            params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code},
            headers=_headers("FHKST01010100", token),
            timeout=10,
        )
        data = res.json()
        if data.get("rt_cd") != "0":
            raise RuntimeError(f"KIS 국내 시세 오류 ({ticker}): {data.get('msg1')}")
        output = data["output"]
        return Price(
            ticker=ticker,
            current=float(output["stck_prpr"]),
            currency="KRW",
            change_pct=float(output.get("prdy_ctrt") or 0),
        )

    def _fetch_overseas(self, ticker: str, market: str | None, token: str) -> Price:
        pykis_market = market or market_from_ticker(ticker)
        first_excd = _MARKET_TO_EXCD.get((pykis_market or "NASDAQ").upper(), "NAS")
        excd_list = [first_excd] + [e for e in ["NAS", "NYS", "AMS"] if e != first_excd]

        for excd in excd_list:
            try:
                res = requests.get(
                    f"{KIS_BASE}/uapi/overseas-price/v1/quotations/price-detail",
                    params={"AUTH": "", "EXCD": excd, "SYMB": ticker},
                    headers=_headers("HHDFS76200200", token),
                    timeout=10,
                )
                data = res.json()
                if data.get("rt_cd") != "0":
                    continue
                output = data["output"]
                last = float(output.get("last") or 0)
                if last <= 0:
                    continue
                base = float(output.get("base") or 0)
                chg_pct = ((last - base) / base * 100) if base > 0 else 0
                currency = _EXCD_TO_CURRENCY.get(excd, "USD")
                return Price(ticker=ticker, current=last, currency=currency, change_pct=chg_pct)
            except Exception as e:
                log.debug("_fetch_overseas 예외 (%s/%s): %s", ticker, excd, e)

        raise RuntimeError(f"KIS 해외 시세 없음: {ticker} (NAS/NYS/AMS 모두 실패)")

    def _fetch_yfinance(self, ticker: str) -> Price:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        return Price(
            ticker=ticker,
            current=float(info.last_price),
            currency=detect_currency(ticker),
        )


# ── 역사 OHLCV (모듈 레벨 함수) ────────────────────────────────────────────────

def fetch_ohlcv_domestic(ticker: str, start: date, end: date) -> pd.DataFrame:
    """KIS 국내주식 일봉 OHLCV. 100일 단위 자동 페이지네이션.

    Returns DataFrame with DatetimeIndex, columns: Open High Low Close Volume
    빈 DataFrame이면 KIS 조회 실패 (토큰 없음 / 데이터 없음).
    """
    token = _get_token()
    if not token:
        return pd.DataFrame()

    code, _ = to_kis_domestic(ticker)
    all_rows: list[dict] = []
    chunk_end = end

    while chunk_end >= start:
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": chunk_end.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "1",
        }
        res = requests.get(
            f"{KIS_BASE}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            params=params,
            headers=_headers("FHKST03010100", token),
            timeout=10,
        )
        data = res.json()
        if data.get("rt_cd") != "0":
            log.warning("KIS 국내 일봉 오류 (%s): %s", ticker, data.get("msg1"))
            break

        rows = data.get("output2") or []
        if not rows:
            break

        dates_seen: list[date] = []
        for row in rows:
            dt_str = row.get("stck_bsop_date", "")
            if not dt_str:
                continue
            dt = datetime.strptime(dt_str, "%Y%m%d").date()
            if dt < start:
                continue
            dates_seen.append(dt)
            all_rows.append({
                "date": dt,
                "Open": float(row.get("stck_oprc") or 0),
                "High": float(row.get("stck_hgpr") or 0),
                "Low": float(row.get("stck_lwpr") or 0),
                "Close": float(row.get("stck_clpr") or 0),
                "Volume": int(row.get("acml_vol") or 0),
            })

        if not dates_seen or min(dates_seen) <= start:
            break
        chunk_end = min(dates_seen) - timedelta(days=1)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates("date").sort_values("date")
    df.index = pd.to_datetime(df.pop("date"))
    return df


# ── 역사 OHLCV 해외 (모듈 레벨 함수) ────────────────────────────────────────────

def _fetch_ohlcv_overseas_single(
    ticker: str,
    excd: str,
    start: date,
    end: date,
    token: str,
) -> pd.DataFrame:
    """단일 EXCD로 KIS 해외 일봉 조회. 페이지네이션 최대 5회."""
    all_rows: list[dict] = []
    keyb = ""

    for _ in range(5):
        try:
            res = requests.get(
                f"{KIS_BASE}/uapi/overseas-price/v1/quotations/dailyprice",
                params={
                    "AUTH": "",
                    "EXCD": excd,
                    "SYMB": ticker,
                    "GUBN": "0",
                    "BYMD": end.strftime("%Y%m%d"),
                    "MODP": "1",
                    "KEYB": keyb,
                },
                headers=_headers("HHDFS76240000", token),
                timeout=10,
            )
            data = res.json()
        except Exception as e:
            log.warning("KIS 해외 일봉 예외 (%s/%s): %s", ticker, excd, e)
            return pd.DataFrame()

        if data.get("rt_cd") != "0":
            log.debug("KIS 해외 일봉 오류 (%s/%s): %s", ticker, excd, data.get("msg1"))
            return pd.DataFrame()

        rows = data.get("output2") or []
        reached_start = False
        for row in rows:
            dt_str = row.get("xymd", "")
            if not dt_str:
                continue
            clos = float(row.get("clos") or 0)
            if clos <= 0:
                continue
            dt = datetime.strptime(dt_str, "%Y%m%d").date()
            if dt < start:
                reached_start = True
                continue
            all_rows.append({
                "date": dt,
                "Open":   float(row.get("open") or 0),
                "High":   float(row.get("high") or 0),
                "Low":    float(row.get("low") or 0),
                "Close":  clos,
                "Volume": int(row.get("tvol") or 0),
            })

        if reached_start or not rows:
            break

        keyb = (data.get("output1") or {}).get("keyb", "")
        if not keyb:
            break

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates("date").sort_values("date")
    df.index = pd.to_datetime(df.pop("date"))
    return df


def fetch_ohlcv_overseas(
    ticker: str,
    start: date,
    end: date,
    market: str | None = None,
) -> pd.DataFrame:
    """KIS 해외주식 일봉 OHLCV. 미장(NAS/NYS/AMS) 대상, 최대 5페이지(500일).

    Returns DataFrame with DatetimeIndex, columns: Open High Low Close Volume
    빈 DataFrame이면 KIS 조회 실패 (caller에서 yfinance fallback).
    """
    token = _get_token()
    if not token:
        return pd.DataFrame()

    if market:
        first = _MARKET_TO_EXCD.get(market.upper())
        excd_list = [first] if first else ["NAS", "NYS", "AMS"]
    else:
        excd_list = ["NAS", "NYS", "AMS"]

    for excd in excd_list:
        df = _fetch_ohlcv_overseas_single(ticker, excd, start, end, token)
        if not df.empty:
            return df

    return pd.DataFrame()


# ── 계좌 잔고 조회 (모듈 레벨 함수) ────────────────────────────────────────────

def fetch_balance_domestic() -> list[dict]:
    """KIS 국내 계좌 잔고 조회. 토큰 없음 or 오류 시 빈 리스트."""
    token = _get_token()
    if not token:
        return []

    results: list[dict] = []
    ctx_fk = ""
    ctx_nk = ""

    for _ in range(10):
        res = requests.get(
            f"{KIS_BASE}/uapi/domestic-stock/v1/trading/inquire-balance",
            params={
                "CANO": _CANO,
                "ACNT_PRDT_CD": _ACNT_PRDT_CD,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "05",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": ctx_fk,
                "CTX_AREA_NK100": ctx_nk,
            },
            headers=_headers("TTTC8434R", token),
            timeout=10,
        )
        data = res.json()
        if data.get("rt_cd") != "0":
            log.warning("KIS 국내 잔고 오류: %s", data.get("msg1"))
            break

        for item in data.get("output1") or []:
            qty = float(item.get("hldg_qty") or 0)
            if qty <= 0:
                continue
            code = item.get("pdno", "")
            results.append({
                "ticker": f"{code}.KS",
                "name": item.get("prdt_name") or code,
                "quantity": qty,
                "avg_price": float(item.get("pchs_avg_pric") or 0),
                "currency": "KRW",
                "market": "KRX",
            })

        tr_cont = res.headers.get("tr_cont", " ")
        if tr_cont not in ("F", "M"):
            break
        output3 = data.get("output3") or {}
        ctx_fk = output3.get("ctx_area_fk100", "")
        ctx_nk = output3.get("ctx_area_nk100", "")

    return results


def fetch_balance_overseas() -> list[dict]:
    """KIS 해외 계좌 잔고 조회 (전 거래소). 토큰 없음 or 오류 시 빈 리스트."""
    token = _get_token()
    if not token:
        return []

    results: list[dict] = []
    ctx_fk = ""
    ctx_nk = ""

    for _ in range(10):
        res = requests.get(
            f"{KIS_BASE}/uapi/overseas-stock/v1/trading/inquire-balance",
            params={
                "CANO": _CANO,
                "ACNT_PRDT_CD": _ACNT_PRDT_CD,
                "OVRS_EXCG_CD": "__ALL__",
                "TR_CRCY_CD": "USD",
                "CTX_AREA_FK200": ctx_fk,
                "CTX_AREA_NK200": ctx_nk,
            },
            headers=_headers("TTTS3012R", token),
            timeout=10,
        )
        data = res.json()
        if data.get("rt_cd") != "0":
            log.warning("KIS 해외 잔고 오류: %s", data.get("msg1"))
            break

        for item in data.get("output1") or []:
            qty = float(item.get("ovrs_cblc_qty") or 0)
            if qty <= 0:
                continue
            excd = item.get("ovrs_excg_cd", "")
            market = _EXCD_TO_MARKET.get(excd, excd)
            results.append({
                "ticker": item.get("ovrs_pdno", ""),
                "name": item.get("ovrs_item_name") or item.get("ovrs_pdno", ""),
                "quantity": qty,
                "avg_price": float(item.get("pchs_avg_pric") or 0),
                "currency": "USD",
                "market": market,
            })

        tr_cont = res.headers.get("tr_cont", " ")
        if tr_cont not in ("F", "M"):
            break
        output2 = data.get("output2") or {}
        ctx_fk = output2.get("ctx_area_fk200", "")
        ctx_nk = output2.get("ctx_area_nk200", "")

    return results
