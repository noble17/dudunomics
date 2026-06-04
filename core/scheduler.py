"""APScheduler 잡 정의 — snapshot(5분), fundamentals(1일, Phase β), universe(1일, γ)."""
import logging
import os
from datetime import date, datetime, timedelta

import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler

import core.repository as repo
from core.ema_scan import run_ema_scan, _load_tickers as _load_ema_tickers
from core.fx import get_fx_provider
from core.indicators import compute_indicators
from core.data.prices_provider import fetch_ohlcv
from core.prices.kis import KISPriceProvider

log = logging.getLogger(__name__)

_price_provider = KISPriceProvider()
_fx_provider = get_fx_provider()


def snapshot_job():
    """보유 종목 있는 사용자 전원에 대해 현재가 + 환율 → portfolio_snapshots (5분 주기)."""
    try:
        usdkrw = _fx_provider.get_rate("USDKRW")
        ts = datetime.now().replace(second=0, microsecond=0)
        repo.insert_fx_rate(ts=ts, pair="USDKRW", rate=usdkrw)

        user_ids = repo.get_active_user_ids_with_holdings()
        if not user_ids:
            return

        for user_id in user_ids:
            _snapshot_for_user(user_id, usdkrw, ts)

        log.info("snapshot_job 완료: 사용자 %d명", len(user_ids))
    except Exception as e:
        log.error("snapshot_job 오류: %s", e)


def _snapshot_for_user(user_id: int, usdkrw: float, ts: datetime):
    try:
        holdings = repo.get_holdings(user_id)
        if not holdings:
            return

        tickers = [h["ticker"] for h in holdings]
        markets = {h["ticker"]: h.get("market") for h in holdings}
        prices = _price_provider.get_current_prices(tickers, markets=markets)

        cash_krw = float(repo.get_meta(user_id, "cash_krw") or 0)
        cash_usd = float(repo.get_meta(user_id, "cash_usd") or 0)

        total_equity_krw = 0.0
        total_equity_usd = 0.0
        holdings_snapshot = []

        for h in holdings:
            ticker = h["ticker"]
            if ticker not in prices:
                continue
            p = prices[ticker]
            mv = p.current * h["quantity"]
            if p.currency == "KRW":
                mv_krw, mv_usd = mv, mv / usdkrw
            else:
                mv_krw, mv_usd = mv * usdkrw, mv
            total_equity_krw += mv_krw
            total_equity_usd += mv_usd
            holdings_snapshot.append({
                "ticker": ticker, "price": p.current, "currency": p.currency,
                "quantity": h["quantity"], "mv_krw": mv_krw,
            })

        cash_total_krw = cash_krw + cash_usd * usdkrw
        cash_total_usd = cash_krw / usdkrw + cash_usd

        repo.insert_snapshot(
            user_id=user_id,
            ts=ts,
            total_equity_krw=total_equity_krw,
            total_with_cash_krw=total_equity_krw + cash_total_krw,
            cash_krw=cash_total_krw,
            total_equity_usd=total_equity_usd,
            total_with_cash_usd=total_equity_usd + cash_total_usd,
            cash_usd=cash_total_usd,
            usdkrw=usdkrw,
            holdings_json=holdings_snapshot,
        )
    except Exception as e:
        log.error("_snapshot_for_user(user_id=%d) 오류: %s", user_id, e)


def prices_refresh_kr_job():
    """KR EMA 유니버스 OHLCV 강제 갱신 — EMA 스캔 전 15:45 실행."""
    tickers = _load_ema_tickers("KR")
    end = date.today()
    start = end - timedelta(days=130)
    _BATCH = 50
    log.info("prices_refresh_kr: %d개 종목 강제 갱신 시작", len(tickers))
    for i in range(0, len(tickers), _BATCH):
        batch = tickers[i:i + _BATCH]
        try:
            fetch_ohlcv(batch, start, end, force=True)
        except Exception as e:
            log.error("prices_refresh_kr 배치 오류 (%s...): %s", batch[:2], e)
    log.info("prices_refresh_kr: 갱신 완료")


def ema_scan_kr_job():
    """국장 EMA 골든크로스 스캔 — 매일 16:00 KST."""
    try:
        result = run_ema_scan("KR")
        log.info("ema_scan_kr 완료: %s", result)
    except Exception as e:
        log.error("ema_scan_kr_job 오류: %s", e)


def prices_refresh_us_job():
    """US EMA 유니버스 OHLCV 강제 갱신 — EMA 스캔 전 06:45 실행."""
    tickers = _load_ema_tickers("US")
    end = date.today()
    start = end - timedelta(days=130)
    _BATCH = 50
    log.info("prices_refresh_us: %d개 종목 강제 갱신 시작", len(tickers))
    for i in range(0, len(tickers), _BATCH):
        batch = tickers[i:i + _BATCH]
        try:
            fetch_ohlcv(batch, start, end, force=True)
        except Exception as e:
            log.error("prices_refresh_us 배치 오류 (%s...): %s", batch[:2], e)
    log.info("prices_refresh_us: 갱신 완료")


def ema_scan_us_job():
    """미장 EMA 골든크로스 스캔 — 매일 07:00 KST."""
    try:
        result = run_ema_scan("US")
        log.info("ema_scan_us 완료: %s", result)
    except Exception as e:
        log.error("ema_scan_us_job 오류: %s", e)


def growth_batch_kr_job():
    """국장 성장주 배치 — 매일 16:10 KST."""
    if not os.getenv("DART_API_KEY"):
        log.error("growth_batch_kr 건너뜀: DART_API_KEY가 필요합니다.")
        return
    _run_growth_universes(("kospi200", "kosdaq150"))


def growth_batch_us_job():
    """미장 성장주 배치 — 매일 07:10 KST."""
    _run_growth_universes(("sp500", "nasdaq100"))


def _run_growth_universes(universes: tuple[str, ...]):
    import core.batch_state as bs
    from core.batch_refresh import get_status
    from core.scoring.universe_scorer import run_batch

    for universe in universes:
        status = get_status(universe)
        if status["status"] == "running":
            log.warning("growth batch 건너뜀: %s 배치가 이미 실행 중입니다.", universe)
            continue
        if status["is_fresh"]:
            log.info("growth batch 건너뜀: %s 데이터가 이미 최신입니다.", universe)
            continue
        try:
            run_batch(universe)
        except Exception as e:
            log.error("growth batch 오류 (%s): %s", universe, e)
            bs.fail(universe, str(e))


def _check_condition(alert: dict, current_price: float, ohlcv_df: pd.DataFrame | None) -> bool:
    """알림 조건 충족 여부 반환."""
    ct = alert["condition_type"]
    cv = alert.get("condition_value")

    if ct == "price_above":
        return cv is not None and current_price > cv
    if ct == "price_below":
        return cv is not None and current_price < cv

    if ohlcv_df is None or len(ohlcv_df) < 21:
        return False

    indicators = compute_indicators(ohlcv_df)

    if ct in ("rsi_above", "rsi_below") and cv is not None:
        rsi_pts = indicators["rsi"]
        if not rsi_pts:
            return False
        last_rsi = rsi_pts[-1]["value"]
        return last_rsi > cv if ct == "rsi_above" else last_rsi < cv

    if ct in ("ma_golden_cross", "ma_dead_cross"):
        ma5 = indicators["ma"]["5"]
        ma20 = indicators["ma"]["20"]
        if len(ma5) < 2 or len(ma20) < 2:
            return False
        prev_above = ma5[-2]["value"] > ma20[-2]["value"]
        curr_above = ma5[-1]["value"] > ma20[-1]["value"]
        if ct == "ma_golden_cross":
            return (not prev_above) and curr_above     # prev: MA5 < MA20, curr: MA5 > MA20
        else:  # dead_cross
            return prev_above and (not curr_above)     # prev: MA5 > MA20, curr: MA5 < MA20

    return False


def alert_check_job():
    """활성 알림 조건 체크 — 조건 충족 시 user_alert_events 삽입 (1분 주기)."""
    try:
        alerts = repo.get_all_enabled_alerts()
        if not alerts:
            return

        # 티커별로 현재가 일괄 조회
        tickers = list({a["ticker"] for a in alerts})
        try:
            prices = _price_provider.get_current_prices(tickers)
        except Exception as e:
            log.warning("alert_check_job 시세 조회 실패: %s", e)
            return

        # RSI/MA 조건이 있는 티커만 OHLCV 조회
        indicator_tickers = {
            a["ticker"] for a in alerts
            if a["condition_type"] in ("rsi_above", "rsi_below", "ma_golden_cross", "ma_dead_cross")
        }
        ohlcv_cache: dict[str, pd.DataFrame] = {}
        if indicator_tickers:
            end = date.today()
            start = end - timedelta(days=60)
            for ticker in indicator_tickers:
                try:
                    prices_df, _ = fetch_ohlcv([ticker], start, end)
                    if not prices_df.empty and ticker in prices_df.columns.get_level_values(0):
                        ohlcv_cache[ticker] = prices_df[ticker][
                            ["Open", "High", "Low", "Close", "Volume"]
                        ].dropna()
                except Exception:
                    pass

        for alert in alerts:
            try:
                ticker = alert["ticker"]
                if ticker not in prices:
                    continue

                current_price = prices[ticker].current
                ohlcv_df = ohlcv_cache.get(ticker)

                if repo.has_recent_alert_event(alert["id"], minutes=60):
                    continue

                if _check_condition(alert, current_price, ohlcv_df):
                    repo.insert_alert_event(
                        user_id=alert["user_id"],
                        alert_id=alert["id"],
                        ticker=ticker,
                        condition_type=alert["condition_type"],
                        condition_value=alert.get("condition_value"),
                        triggered_price=current_price,
                    )
                    log.info("alert fired: user=%d ticker=%s type=%s price=%.2f",
                             alert["user_id"], ticker, alert["condition_type"], current_price)
            except Exception as e:
                log.error("alert check 오류 (alert_id=%d): %s", alert.get("id", -1), e)

    except Exception as e:
        log.error("alert_check_job 오류: %s", e)


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(snapshot_job, "interval", minutes=5, id="snapshot",
                      next_run_time=datetime.now())
    scheduler.add_job(alert_check_job, "interval", minutes=1, id="alert_check")
    scheduler.add_job(prices_refresh_kr_job, "cron", hour=15, minute=45,
                      id="prices_refresh_kr", timezone="Asia/Seoul")
    scheduler.add_job(ema_scan_kr_job, "cron", hour=16, minute=0,
                      id="ema_scan_kr", timezone="Asia/Seoul")
    scheduler.add_job(prices_refresh_us_job, "cron", hour=6, minute=45,
                      id="prices_refresh_us", timezone="Asia/Seoul")
    scheduler.add_job(ema_scan_us_job, "cron", hour=7, minute=0,
                      id="ema_scan_us", timezone="Asia/Seoul")
    scheduler.add_job(growth_batch_kr_job, "cron", hour=16, minute=10,
                      id="growth_batch_kr", timezone="Asia/Seoul")
    scheduler.add_job(growth_batch_us_job, "cron", hour=7, minute=10,
                      id="growth_batch_us", timezone="Asia/Seoul")
    return scheduler
