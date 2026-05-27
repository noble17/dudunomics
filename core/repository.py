"""DuckDB + SQLAlchemy 기반 데이터 접근 계층."""
import json
import os
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DB_PATH = Path(os.getenv("DB_PATH", "data/dudunomics.duckdb"))

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"duckdb:///{DB_PATH}", connect_args={"read_only": False})
        _init_schema(_engine)
    return _engine


@contextmanager
def session():
    eng = get_engine()
    with Session(eng) as s:
        yield s


def _init_schema(engine):
    ddl = """
    CREATE TABLE IF NOT EXISTS holdings (
        ticker TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        currency TEXT NOT NULL,
        quantity DOUBLE NOT NULL,
        avg_price DOUBLE NOT NULL,
        sector TEXT,
        market TEXT,
        updated_at TIMESTAMP DEFAULT current_timestamp
    );

    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE IF NOT EXISTS prices_cache (
        ticker TEXT,
        date DATE,
        open DOUBLE,
        high DOUBLE,
        low DOUBLE,
        close DOUBLE,
        volume BIGINT,
        PRIMARY KEY (ticker, date)
    );

    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        ts TIMESTAMP PRIMARY KEY,
        total_equity_krw DOUBLE,
        total_with_cash_krw DOUBLE,
        cash_krw DOUBLE,
        total_equity_usd DOUBLE,
        total_with_cash_usd DOUBLE,
        cash_usd DOUBLE,
        usdkrw DOUBLE,
        holdings_json JSON
    );

    CREATE TABLE IF NOT EXISTS fx_rates (
        ts TIMESTAMP,
        pair TEXT,
        rate DOUBLE,
        PRIMARY KEY (ts, pair)
    );

    CREATE TABLE IF NOT EXISTS backtest_runs (
        id INTEGER PRIMARY KEY,
        created_at TIMESTAMP DEFAULT current_timestamp,
        strategy TEXT,
        params_json JSON,
        ticker TEXT,
        period_start DATE,
        period_end DATE,
        total_return DOUBLE,
        mdd DOUBLE,
        sharpe DOUBLE,
        equity_curve JSON
    );

    CREATE SEQUENCE IF NOT EXISTS backtest_runs_id_seq START 1;

    CREATE TABLE IF NOT EXISTS portfolio_events (
        id INTEGER PRIMARY KEY,
        ts TIMESTAMP NOT NULL,
        label TEXT NOT NULL,
        amount INTEGER DEFAULT 0,
        type TEXT DEFAULT '기타'
    );

    CREATE SEQUENCE IF NOT EXISTS portfolio_events_id_seq START 1;

    CREATE TABLE IF NOT EXISTS fundamentals_cache (
        ticker TEXT,
        as_of DATE,
        forward_eps DOUBLE,
        forward_pe DOUBLE,
        trailing_pe DOUBLE,
        raw_json JSON,
        fetched_at TIMESTAMP,
        PRIMARY KEY (ticker, as_of)
    );
    """
    with engine.connect() as conn:
        for stmt in ddl.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        for migration in [
            "ALTER TABLE holdings ADD COLUMN sector TEXT",
            "ALTER TABLE holdings ADD COLUMN market TEXT",
            "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS tickers_json JSON",
            "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS weights_history JSON",
            "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS contribution_json JSON",
            "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS warnings_json JSON",
            "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS cagr DOUBLE",
            "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS risk_options_json JSON",
        ]:
            try:
                conn.execute(text(migration))
            except Exception:
                pass
        conn.commit()


# ── Holdings ──────────────────────────────────────────────────────────────────

def get_holdings() -> list[dict]:
    with session() as s:
        rows = s.execute(text("SELECT * FROM holdings ORDER BY ticker")).mappings().all()
        return [dict(r) for r in rows]


def upsert_holding(
    ticker: str,
    name: str,
    currency: str,
    quantity: float,
    avg_price: float,
    sector: str | None = None,
    market: str | None = None,
):
    now = datetime.now()
    with session() as s:
        s.execute(text("""
            INSERT INTO holdings (ticker, name, currency, quantity, avg_price, sector, market, updated_at)
            VALUES (:ticker, :name, :currency, :quantity, :avg_price, :sector, :market, :now)
            ON CONFLICT (ticker) DO UPDATE SET
                name = excluded.name,
                currency = excluded.currency,
                quantity = excluded.quantity,
                avg_price = excluded.avg_price,
                sector = excluded.sector,
                market = excluded.market,
                updated_at = :now
        """), {"ticker": ticker, "name": name, "currency": currency,
               "quantity": quantity, "avg_price": avg_price,
               "sector": sector, "market": market, "now": now})
        s.commit()


def delete_holding(ticker: str):
    with session() as s:
        s.execute(text("DELETE FROM holdings WHERE ticker = :ticker"), {"ticker": ticker})
        s.commit()


# ── Meta (현금 등) ─────────────────────────────────────────────────────────────

def get_meta(key: str, default: str | None = None) -> str | None:
    with session() as s:
        row = s.execute(text("SELECT value FROM meta WHERE key = :key"), {"key": key}).fetchone()
        return row[0] if row else default


def set_meta(key: str, value: str):
    with session() as s:
        s.execute(text("""
            INSERT INTO meta (key, value) VALUES (:key, :value)
            ON CONFLICT (key) DO UPDATE SET value = excluded.value
        """), {"key": key, "value": value})
        s.commit()


# ── Portfolio Snapshots ───────────────────────────────────────────────────────

def insert_snapshot(
    ts: datetime,
    total_equity_krw: float,
    total_with_cash_krw: float,
    cash_krw: float,
    total_equity_usd: float,
    total_with_cash_usd: float,
    cash_usd: float,
    usdkrw: float,
    holdings_json: dict,
):
    with session() as s:
        s.execute(text("""
            INSERT OR IGNORE INTO portfolio_snapshots
            (ts, total_equity_krw, total_with_cash_krw, cash_krw,
             total_equity_usd, total_with_cash_usd, cash_usd, usdkrw, holdings_json)
            VALUES (:ts, :total_equity_krw, :total_with_cash_krw, :cash_krw,
                    :total_equity_usd, :total_with_cash_usd, :cash_usd, :usdkrw, :holdings_json)
        """), {
            "ts": ts, "total_equity_krw": total_equity_krw,
            "total_with_cash_krw": total_with_cash_krw, "cash_krw": cash_krw,
            "total_equity_usd": total_equity_usd, "total_with_cash_usd": total_with_cash_usd,
            "cash_usd": cash_usd, "usdkrw": usdkrw,
            "holdings_json": json.dumps(holdings_json),
        })
        s.commit()


def get_snapshots(limit: int = 400) -> list[dict]:
    with session() as s:
        rows = s.execute(text(
            "SELECT * FROM portfolio_snapshots ORDER BY ts DESC LIMIT :limit"
        ), {"limit": limit}).mappings().all()
        return [dict(r) for r in rows]


# ── FX Rates ──────────────────────────────────────────────────────────────────

def insert_fx_rate(ts: datetime, pair: str, rate: float):
    with session() as s:
        s.execute(text("""
            INSERT OR IGNORE INTO fx_rates (ts, pair, rate)
            VALUES (:ts, :pair, :rate)
        """), {"ts": ts, "pair": pair, "rate": rate})
        s.commit()


def get_latest_fx_rate(pair: str) -> float | None:
    with session() as s:
        row = s.execute(text(
            "SELECT rate FROM fx_rates WHERE pair = :pair ORDER BY ts DESC LIMIT 1"
        ), {"pair": pair}).fetchone()
        return row[0] if row else None


# ── Fundamentals Cache ───────────────────────────────────────────────────────

def upsert_fundamentals(snapshots: "list") -> None:
    """FundamentalSnapshot 목록을 fundamentals_cache에 upsert."""
    if not snapshots:
        return
    now = datetime.now()
    with session() as s:
        for snap in snapshots:
            s.execute(text("""
                INSERT INTO fundamentals_cache
                    (ticker, as_of, forward_eps, forward_pe, trailing_pe, raw_json, fetched_at)
                VALUES (:ticker, :as_of, :feps, :fpe, :tpe, :raw_json, :fetched_at)
                ON CONFLICT (ticker, as_of) DO UPDATE SET
                    forward_eps = excluded.forward_eps,
                    forward_pe  = excluded.forward_pe,
                    trailing_pe = excluded.trailing_pe,
                    raw_json    = excluded.raw_json,
                    fetched_at  = excluded.fetched_at
            """), {
                "ticker": snap.ticker,
                "as_of": snap.as_of,
                "feps": snap.forward_eps,
                "fpe": snap.forward_pe,
                "tpe": snap.trailing_pe,
                "raw_json": snap.raw_json,
                "fetched_at": now,
            })
        s.commit()


# ── Portfolio Events ──────────────────────────────────────────────────────────

def get_events() -> list[dict]:
    with session() as s:
        rows = s.execute(
            text("SELECT * FROM portfolio_events ORDER BY ts DESC")
        ).mappings().all()
        return [dict(r) for r in rows]


def insert_event(ts: datetime, label: str, amount: int, type_: str) -> int:
    with session() as s:
        row = s.execute(text("SELECT nextval('portfolio_events_id_seq')")).fetchone()
        event_id = row[0]
        s.execute(text("""
            INSERT INTO portfolio_events (id, ts, label, amount, type)
            VALUES (:id, :ts, :label, :amount, :type)
        """), {"id": event_id, "ts": ts, "label": label, "amount": amount, "type": type_})
        s.commit()
    return event_id


def delete_event(event_id: int) -> None:
    with session() as s:
        s.execute(text("DELETE FROM portfolio_events WHERE id = :id"), {"id": event_id})
        s.commit()


def get_latest_fundamental(ticker: str, as_of: date) -> dict | None:
    """as_of 이전 가장 최근 스냅샷 반환 (없으면 None)."""
    with session() as s:
        row = s.execute(text("""
            SELECT ticker, as_of, forward_eps, forward_pe, trailing_pe
            FROM fundamentals_cache
            WHERE ticker = :ticker AND as_of <= :as_of
            ORDER BY as_of DESC
            LIMIT 1
        """), {"ticker": ticker, "as_of": as_of}).fetchone()
        return dict(row._mapping) if row else None


# ── Backtest Runs ─────────────────────────────────────────────────────────────

def insert_backtest_run(
    strategy: str,
    params: dict,
    ticker: str,
    period_start: date,
    period_end: date,
    total_return: float,
    mdd: float,
    sharpe: float,
    equity_curve: list[dict],
    tickers: list[str] | None = None,
    cagr: float | None = None,
    weights_history: list[dict] | None = None,
    contribution: dict | None = None,
    warnings: list[str] | None = None,
    risk_options: dict | None = None,
) -> int:
    with session() as s:
        row = s.execute(text("SELECT nextval('backtest_runs_id_seq')")).fetchone()
        run_id = row[0]
        s.execute(text("""
            INSERT INTO backtest_runs
            (id, strategy, params_json, ticker, period_start, period_end,
             total_return, mdd, sharpe, equity_curve,
             tickers_json, cagr, weights_history, contribution_json, warnings_json, risk_options_json)
            VALUES (:id, :strategy, :params_json, :ticker, :period_start, :period_end,
                    :total_return, :mdd, :sharpe, :equity_curve,
                    :tickers_json, :cagr, :weights_history, :contribution_json, :warnings_json, :risk_options_json)
        """), {
            "id": run_id, "strategy": strategy,
            "params_json": json.dumps(params), "ticker": ticker,
            "period_start": period_start, "period_end": period_end,
            "total_return": total_return, "mdd": mdd, "sharpe": sharpe,
            "equity_curve": json.dumps(equity_curve),
            "tickers_json": json.dumps(tickers) if tickers else None,
            "cagr": cagr,
            "weights_history": json.dumps(weights_history) if weights_history else None,
            "contribution_json": json.dumps(contribution) if contribution else None,
            "warnings_json": json.dumps(warnings) if warnings else None,
            "risk_options_json": json.dumps(risk_options) if risk_options else None,
        })
        s.commit()
        return run_id


# ── OHLCV Cache ───────────────────────────────────────────────────────────────

def get_ohlcv_range(ticker: str) -> "tuple[date, date] | None":
    """캐시된 (min_date, max_date) 반환. 없으면 None."""
    with session() as s:
        row = s.execute(text("""
            SELECT MIN(date), MAX(date) FROM prices_cache WHERE ticker = :ticker
        """), {"ticker": ticker}).fetchone()
        if row is None or row[0] is None:
            return None
        return (row[0], row[1])


def upsert_ohlcv_rows(rows: list[dict]) -> None:
    """(ticker, date, open, high, low, close, volume) 배치 insert. 중복 무시."""
    if not rows:
        return
    with session() as s:
        s.execute(text("""
            INSERT OR IGNORE INTO prices_cache (ticker, date, open, high, low, close, volume)
            VALUES (:ticker, :date, :open, :high, :low, :close, :volume)
        """), rows)
        s.commit()
