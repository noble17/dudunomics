"""APScheduler 잡 정의 — snapshot(5분), fundamentals(1일, Phase β), universe(1일, γ)."""
import json
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
    """보유 종목 현재가 + 환율 → portfolio_snapshots (5분 주기)."""
    try:
        holdings = repo.get_holdings()
        if not holdings:
            return

        tickers = [h["ticker"] for h in holdings]
        prices = _price_provider.get_current_prices(tickers)

        usdkrw = _fx_provider.get_rate("USDKRW")
        cash_krw = float(repo.get_meta("cash_krw") or 0)
        cash_usd = float(repo.get_meta("cash_usd") or 0)

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
                mv_krw = mv
                mv_usd = mv / usdkrw
            else:
                mv_krw = mv * usdkrw
                mv_usd = mv
            total_equity_krw += mv_krw
            total_equity_usd += mv_usd
            holdings_snapshot.append({
                "ticker": ticker, "price": p.current, "currency": p.currency,
                "quantity": h["quantity"], "mv_krw": mv_krw,
            })

        cash_total_krw = cash_krw + cash_usd * usdkrw
        cash_total_usd = cash_krw / usdkrw + cash_usd

        ts = datetime.now().replace(second=0, microsecond=0)
        repo.insert_snapshot(
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
        repo.insert_fx_rate(ts=ts, pair="USDKRW", rate=usdkrw)
        log.info("snapshot_job 완료: 총평가액 ₩%,.0f", total_equity_krw)
    except Exception as e:
        log.error("snapshot_job 오류: %s", e)


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(snapshot_job, "interval", minutes=5, id="snapshot",
                      next_run_time=datetime.now())  # 시작 직후 1회 실행
    return scheduler
