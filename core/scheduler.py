"""APScheduler 잡 정의 — snapshot(5분), fundamentals(1일, Phase β), universe(1일, γ)."""
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

import core.repository as repo
from core.fx import get_fx_provider
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


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(snapshot_job, "interval", minutes=5, id="snapshot",
                      next_run_time=datetime.now())
    return scheduler
