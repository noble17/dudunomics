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


def _has_column(conn, table: str, column: str) -> bool:
    row = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": table, "c": column}).fetchone()
    return row[0] > 0


def _init_schema(engine):
    ddl = """
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY,
        email       TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at  TIMESTAMP DEFAULT current_timestamp,
        is_active   BOOLEAN DEFAULT true
    );

    CREATE SEQUENCE IF NOT EXISTS users_id_seq START 1;

    CREATE TABLE IF NOT EXISTS user_sessions (
        jti         TEXT PRIMARY KEY,
        user_id     INTEGER NOT NULL,
        expires_at  TIMESTAMP NOT NULL,
        revoked     BOOLEAN DEFAULT false
    );

    CREATE TABLE IF NOT EXISTS holdings (
        ticker      TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        currency    TEXT NOT NULL,
        quantity    DOUBLE NOT NULL,
        avg_price   DOUBLE NOT NULL,
        sector      TEXT,
        market      TEXT,
        updated_at  TIMESTAMP DEFAULT current_timestamp
    );

    CREATE TABLE IF NOT EXISTS meta (
        key   TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE IF NOT EXISTS prices_cache (
        ticker TEXT,
        date   DATE,
        open   DOUBLE,
        high   DOUBLE,
        low    DOUBLE,
        close  DOUBLE,
        volume BIGINT,
        PRIMARY KEY (ticker, date)
    );

    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        ts                  TIMESTAMP PRIMARY KEY,
        total_equity_krw    DOUBLE,
        total_with_cash_krw DOUBLE,
        cash_krw            DOUBLE,
        total_equity_usd    DOUBLE,
        total_with_cash_usd DOUBLE,
        cash_usd            DOUBLE,
        usdkrw              DOUBLE,
        holdings_json       JSON
    );

    CREATE TABLE IF NOT EXISTS fx_rates (
        ts   TIMESTAMP,
        pair TEXT,
        rate DOUBLE,
        PRIMARY KEY (ts, pair)
    );

    CREATE TABLE IF NOT EXISTS backtest_runs (
        id           INTEGER PRIMARY KEY,
        created_at   TIMESTAMP DEFAULT current_timestamp,
        strategy     TEXT,
        params_json  JSON,
        ticker       TEXT,
        period_start DATE,
        period_end   DATE,
        total_return DOUBLE,
        mdd          DOUBLE,
        sharpe       DOUBLE,
        equity_curve JSON
    );

    CREATE SEQUENCE IF NOT EXISTS backtest_runs_id_seq START 1;

    CREATE TABLE IF NOT EXISTS portfolio_events (
        id     INTEGER PRIMARY KEY,
        ts     TIMESTAMP NOT NULL,
        label  TEXT NOT NULL,
        amount INTEGER DEFAULT 0,
        type   TEXT DEFAULT '기타'
    );

    CREATE SEQUENCE IF NOT EXISTS portfolio_events_id_seq START 1;

    CREATE TABLE IF NOT EXISTS fundamentals_cache (
        ticker      TEXT,
        as_of       DATE,
        forward_eps DOUBLE,
        forward_pe  DOUBLE,
        trailing_pe DOUBLE,
        raw_json    JSON,
        fetched_at  TIMESTAMP,
        PRIMARY KEY (ticker, as_of)
    );

    CREATE TABLE IF NOT EXISTS quant_scores (
        ticker           TEXT,
        universe         TEXT,
        as_of            DATE,
        pct_momentum     DOUBLE,
        pct_valuation    DOUBLE,
        pct_eps_momentum DOUBLE,
        pct_quality      DOUBLE,
        pct_technical    DOUBLE,
        raw_momentum     DOUBLE,
        raw_fwd_pe       DOUBLE,
        raw_pbr          DOUBLE,
        raw_psr          DOUBLE,
        raw_trailing_pe  DOUBLE,
        raw_eps_ttm      DOUBLE,
        raw_fwd_eps      DOUBLE,
        raw_roe          DOUBLE,
        raw_debt_ratio   DOUBLE,
        raw_rsi          DOUBLE,
        above_ma200      BOOLEAN,
        cfo_positive     BOOLEAN,
        company_name     TEXT,
        PRIMARY KEY (ticker, universe, as_of)
    );

    CREATE TABLE IF NOT EXISTS ticker_notes (
        ticker       TEXT PRIMARY KEY,
        opinion      TEXT,
        target_price DOUBLE,
        memo         TEXT,
        tags         TEXT,
        updated_at   TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_workspaces (
        user_id     INTEGER NOT NULL,
        name        TEXT NOT NULL DEFAULT 'default',
        layout_json TEXT NOT NULL DEFAULT '{}',
        updated_at  TIMESTAMP DEFAULT current_timestamp,
        PRIMARY KEY (user_id, name)
    );

    CREATE SEQUENCE IF NOT EXISTS user_alerts_id_seq START 1;
    CREATE TABLE IF NOT EXISTS user_alerts (
        id              INTEGER DEFAULT nextval('user_alerts_id_seq') PRIMARY KEY,
        user_id         INTEGER NOT NULL,
        ticker          VARCHAR NOT NULL,
        condition_type  VARCHAR NOT NULL,
        condition_value DOUBLE,
        enabled         BOOLEAN DEFAULT TRUE,
        created_at      TIMESTAMP DEFAULT current_timestamp
    );

    CREATE SEQUENCE IF NOT EXISTS user_alert_events_id_seq START 1;
    CREATE TABLE IF NOT EXISTS user_alert_events (
        id              INTEGER DEFAULT nextval('user_alert_events_id_seq') PRIMARY KEY,
        user_id         INTEGER NOT NULL,
        alert_id        INTEGER,
        ticker          VARCHAR NOT NULL,
        condition_type  VARCHAR NOT NULL,
        condition_value DOUBLE,
        triggered_price DOUBLE NOT NULL,
        triggered_at    TIMESTAMP DEFAULT current_timestamp,
        read            BOOLEAN DEFAULT FALSE
    );

    CREATE SEQUENCE IF NOT EXISTS trades_id_seq START 1;
    CREATE TABLE IF NOT EXISTS trades (
        id          INTEGER DEFAULT nextval('trades_id_seq') PRIMARY KEY,
        user_id     INTEGER NOT NULL,
        ticker      VARCHAR NOT NULL,
        market      VARCHAR,
        trade_type  VARCHAR NOT NULL,
        quantity    DOUBLE NOT NULL,
        price       DOUBLE NOT NULL,
        currency    VARCHAR NOT NULL,
        traded_at   VARCHAR NOT NULL,
        fee         DOUBLE DEFAULT 0,
        note        TEXT,
        created_at  TIMESTAMP DEFAULT current_timestamp
    );
    """
    with engine.connect() as conn:
        for stmt in ddl.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        # 기존 ALTER 마이그레이션 (하위 호환)
        for migration in [
            "ALTER TABLE holdings ADD COLUMN sector TEXT",
            "ALTER TABLE holdings ADD COLUMN market TEXT",
            "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS tickers_json JSON",
            "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS weights_history JSON",
            "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS contribution_json JSON",
            "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS warnings_json JSON",
            "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS cagr DOUBLE",
            "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS risk_options_json JSON",
            "CREATE INDEX IF NOT EXISTS idx_quant_scores_uni_date ON quant_scores (universe, as_of)",
        ]:
            try:
                conn.execute(text(migration))
            except Exception:
                pass
        conn.commit()
        _run_migrations(conn)


def _run_migrations(conn):
    """멀티유저 user_id 마이그레이션. 이미 적용됐으면 건너뜀."""

    # holdings: (user_id, ticker) 복합 PK로 재생성
    if not _has_column(conn, "holdings", "user_id"):
        conn.execute(text("""
            CREATE TABLE holdings_new (
                user_id    INTEGER NOT NULL DEFAULT 1,
                ticker     TEXT NOT NULL,
                name       TEXT NOT NULL,
                currency   TEXT NOT NULL,
                quantity   DOUBLE NOT NULL,
                avg_price  DOUBLE NOT NULL,
                sector     TEXT,
                market     TEXT,
                updated_at TIMESTAMP DEFAULT current_timestamp,
                PRIMARY KEY (user_id, ticker)
            )
        """))
        conn.execute(text(
            "INSERT INTO holdings_new SELECT 1, ticker, name, currency, quantity, "
            "avg_price, sector, market, updated_at FROM holdings"
        ))
        conn.execute(text("DROP TABLE holdings"))
        conn.execute(text("ALTER TABLE holdings_new RENAME TO holdings"))

    # meta: (user_id, key) 복합 PK로 재생성
    if not _has_column(conn, "meta", "user_id"):
        conn.execute(text("""
            CREATE TABLE meta_new (
                user_id INTEGER NOT NULL DEFAULT 1,
                key     TEXT NOT NULL,
                value   TEXT,
                PRIMARY KEY (user_id, key)
            )
        """))
        conn.execute(text(
            "INSERT INTO meta_new SELECT 1, key, value FROM meta"
        ))
        conn.execute(text("DROP TABLE meta"))
        conn.execute(text("ALTER TABLE meta_new RENAME TO meta"))

    # ticker_notes: (user_id, ticker) 복합 PK로 재생성
    if not _has_column(conn, "ticker_notes", "user_id"):
        conn.execute(text("""
            CREATE TABLE ticker_notes_new (
                user_id      INTEGER NOT NULL DEFAULT 1,
                ticker       TEXT NOT NULL,
                opinion      TEXT,
                target_price DOUBLE,
                memo         TEXT,
                tags         TEXT,
                updated_at   TIMESTAMP,
                PRIMARY KEY (user_id, ticker)
            )
        """))
        conn.execute(text(
            "INSERT INTO ticker_notes_new SELECT 1, ticker, opinion, target_price, "
            "memo, tags, updated_at FROM ticker_notes"
        ))
        conn.execute(text("DROP TABLE ticker_notes"))
        conn.execute(text("ALTER TABLE ticker_notes_new RENAME TO ticker_notes"))

    # portfolio_snapshots: user_id 컬럼 추가
    if not _has_column(conn, "portfolio_snapshots", "user_id"):
        conn.execute(text(
            "ALTER TABLE portfolio_snapshots ADD COLUMN IF NOT EXISTS user_id INTEGER DEFAULT 1"
        ))
        conn.execute(text(
            "UPDATE portfolio_snapshots SET user_id = 1 WHERE user_id IS NULL"
        ))
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_user ON portfolio_snapshots(user_id)"
            ))
        except Exception:
            pass

    # backtest_runs: user_id 컬럼 추가
    if not _has_column(conn, "backtest_runs", "user_id"):
        conn.execute(text(
            "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS user_id INTEGER DEFAULT 1"
        ))
        conn.execute(text(
            "UPDATE backtest_runs SET user_id = 1 WHERE user_id IS NULL"
        ))

    # portfolio_events: user_id 컬럼 추가
    if not _has_column(conn, "portfolio_events", "user_id"):
        conn.execute(text(
            "ALTER TABLE portfolio_events ADD COLUMN IF NOT EXISTS user_id INTEGER DEFAULT 1"
        ))
        conn.execute(text(
            "UPDATE portfolio_events SET user_id = 1 WHERE user_id IS NULL"
        ))

    # holdings: target_weight 컬럼 추가
    if not _has_column(conn, "holdings", "target_weight"):
        conn.execute(text(
            "ALTER TABLE holdings ADD COLUMN target_weight DOUBLE DEFAULT NULL"
        ))

    # trades: 기존 holdings를 Day 0 BUY로 시딩 (최초 1회)
    seeded = conn.execute(text("SELECT COUNT(*) FROM trades")).fetchone()[0]
    if seeded == 0:
        holdings = conn.execute(text(
            "SELECT user_id, ticker, market, quantity, avg_price, currency FROM holdings"
        )).fetchall()
        for h in holdings:
            if h[3] > 0 and h[4] > 0:
                conn.execute(text("""
                    INSERT INTO trades
                      (user_id, ticker, market, trade_type, quantity, price, currency, traded_at, fee)
                    VALUES (:uid, :ticker, :market, 'BUY', :qty, :price, :cur, '2024-01-01', 0)
                """), {"uid": h[0], "ticker": h[1], "market": h[2],
                       "qty": h[3], "price": h[4], "cur": h[5]})

    # LEGACY 사용자 자동 생성
    legacy_email = os.getenv("LEGACY_USER_EMAIL", "")
    legacy_pw = os.getenv("LEGACY_USER_PASSWORD", "")
    if legacy_email and legacy_pw:
        existing = conn.execute(
            text("SELECT id FROM users WHERE id = 1")
        ).fetchone()
        if not existing:
            from core.auth.passwords import hash_password
            conn.execute(text("""
                INSERT INTO users (id, email, password_hash, created_at, is_active)
                VALUES (1, :email, :pw_hash, current_timestamp, true)
            """), {"email": legacy_email, "pw_hash": hash_password(legacy_pw)})
            # id=1을 직접 삽입했으므로 시퀀스를 2로 진행
            conn.execute(text("SELECT nextval('users_id_seq')"))

    conn.commit()


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(email: str, password_hash: str) -> int:
    with session() as s:
        row = s.execute(text("SELECT nextval('users_id_seq')")).fetchone()
        user_id = row[0]
        s.execute(text("""
            INSERT INTO users (id, email, password_hash, created_at, is_active)
            VALUES (:id, :email, :pw_hash, current_timestamp, true)
        """), {"id": user_id, "email": email, "pw_hash": password_hash})
        s.commit()
        return user_id


def get_user_by_email(email: str) -> dict | None:
    with session() as s:
        row = s.execute(
            text("SELECT * FROM users WHERE email = :email AND is_active = true"),
            {"email": email},
        ).mappings().fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with session() as s:
        row = s.execute(
            text("SELECT * FROM users WHERE id = :id AND is_active = true"),
            {"id": user_id},
        ).mappings().fetchone()
        return dict(row) if row else None


def create_session(jti: str, user_id: int, expires_at: datetime) -> None:
    with session() as s:
        s.execute(text("""
            INSERT INTO user_sessions (jti, user_id, expires_at, revoked)
            VALUES (:jti, :uid, :exp, false)
        """), {"jti": jti, "uid": user_id, "exp": expires_at})
        s.commit()


def revoke_session(jti: str) -> None:
    with session() as s:
        s.execute(
            text("UPDATE user_sessions SET revoked = true WHERE jti = :jti"),
            {"jti": jti},
        )
        s.commit()


def is_session_valid(jti: str) -> bool:
    with session() as s:
        row = s.execute(text("""
            SELECT 1 FROM user_sessions
            WHERE jti = :jti AND revoked = false AND expires_at > current_timestamp
        """), {"jti": jti}).fetchone()
        return row is not None


def get_active_user_ids_with_holdings() -> list[int]:
    with session() as s:
        rows = s.execute(text(
            "SELECT DISTINCT user_id FROM holdings WHERE quantity > 0"
        )).fetchall()
        return [r[0] for r in rows]


# ── Holdings ──────────────────────────────────────────────────────────────────

def get_holdings(user_id: int) -> list[dict]:
    with session() as s:
        rows = s.execute(
            text("SELECT * FROM holdings WHERE user_id = :uid ORDER BY ticker"),
            {"uid": user_id},
        ).mappings().all()
        return [dict(r) for r in rows]


def upsert_holding(
    user_id: int,
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
            INSERT INTO holdings (user_id, ticker, name, currency, quantity, avg_price, sector, market, updated_at)
            VALUES (:uid, :ticker, :name, :currency, :quantity, :avg_price, :sector, :market, :now)
            ON CONFLICT (user_id, ticker) DO UPDATE SET
                name       = excluded.name,
                currency   = excluded.currency,
                quantity   = excluded.quantity,
                avg_price  = excluded.avg_price,
                sector     = excluded.sector,
                market     = excluded.market,
                updated_at = :now
        """), {"uid": user_id, "ticker": ticker, "name": name, "currency": currency,
               "quantity": quantity, "avg_price": avg_price,
               "sector": sector, "market": market, "now": now})
        s.commit()


def delete_holding(user_id: int, ticker: str):
    with session() as s:
        s.execute(
            text("DELETE FROM holdings WHERE user_id = :uid AND ticker = :ticker"),
            {"uid": user_id, "ticker": ticker},
        )
        s.commit()


# ── Meta (현금 등) ─────────────────────────────────────────────────────────────

def get_meta(user_id: int, key: str, default: str | None = None) -> str | None:
    with session() as s:
        row = s.execute(
            text("SELECT value FROM meta WHERE user_id = :uid AND key = :key"),
            {"uid": user_id, "key": key},
        ).fetchone()
        return row[0] if row else default


def set_meta(user_id: int, key: str, value: str):
    with session() as s:
        s.execute(text("""
            INSERT INTO meta (user_id, key, value) VALUES (:uid, :key, :value)
            ON CONFLICT (user_id, key) DO UPDATE SET value = excluded.value
        """), {"uid": user_id, "key": key, "value": value})
        s.commit()


# ── Portfolio Snapshots ───────────────────────────────────────────────────────

def insert_snapshot(
    user_id: int,
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
            (user_id, ts, total_equity_krw, total_with_cash_krw, cash_krw,
             total_equity_usd, total_with_cash_usd, cash_usd, usdkrw, holdings_json)
            VALUES (:uid, :ts, :total_equity_krw, :total_with_cash_krw, :cash_krw,
                    :total_equity_usd, :total_with_cash_usd, :cash_usd, :usdkrw, :holdings_json)
        """), {
            "uid": user_id, "ts": ts,
            "total_equity_krw": total_equity_krw,
            "total_with_cash_krw": total_with_cash_krw, "cash_krw": cash_krw,
            "total_equity_usd": total_equity_usd,
            "total_with_cash_usd": total_with_cash_usd,
            "cash_usd": cash_usd, "usdkrw": usdkrw,
            "holdings_json": json.dumps(holdings_json),
        })
        s.commit()


def get_snapshots(user_id: int, limit: int = 400) -> list[dict]:
    with session() as s:
        rows = s.execute(text(
            "SELECT * FROM portfolio_snapshots WHERE user_id = :uid "
            "ORDER BY ts DESC LIMIT :limit"
        ), {"uid": user_id, "limit": limit}).mappings().all()
        return [dict(r) for r in rows]


# ── FX Rates (공유, user_id 불필요) ──────────────────────────────────────────

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


# ── Fundamentals Cache (공유) ─────────────────────────────────────────────────

def upsert_fundamentals(snapshots: "list") -> None:
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
                "ticker": snap.ticker, "as_of": snap.as_of,
                "feps": snap.forward_eps, "fpe": snap.forward_pe,
                "tpe": snap.trailing_pe, "raw_json": snap.raw_json,
                "fetched_at": now,
            })
        s.commit()


def get_latest_fundamental(ticker: str, as_of: date) -> dict | None:
    with session() as s:
        row = s.execute(text("""
            SELECT ticker, as_of, forward_eps, forward_pe, trailing_pe
            FROM fundamentals_cache
            WHERE ticker = :ticker AND as_of <= :as_of
            ORDER BY as_of DESC LIMIT 1
        """), {"ticker": ticker, "as_of": as_of}).fetchone()
        return dict(row._mapping) if row else None


# ── Portfolio Events ──────────────────────────────────────────────────────────

def get_events(user_id: int) -> list[dict]:
    with session() as s:
        rows = s.execute(
            text("SELECT * FROM portfolio_events WHERE user_id = :uid ORDER BY ts DESC"),
            {"uid": user_id},
        ).mappings().all()
        return [dict(r) for r in rows]


def insert_event(user_id: int, ts: datetime, label: str, amount: int, type_: str) -> int:
    with session() as s:
        row = s.execute(text("SELECT nextval('portfolio_events_id_seq')")).fetchone()
        event_id = row[0]
        s.execute(text("""
            INSERT INTO portfolio_events (id, user_id, ts, label, amount, type)
            VALUES (:id, :uid, :ts, :label, :amount, :type)
        """), {"id": event_id, "uid": user_id, "ts": ts,
               "label": label, "amount": amount, "type": type_})
        s.commit()
    return event_id


def delete_event(user_id: int, event_id: int) -> None:
    with session() as s:
        s.execute(
            text("DELETE FROM portfolio_events WHERE id = :id AND user_id = :uid"),
            {"id": event_id, "uid": user_id},
        )
        s.commit()


# ── Backtest Runs ─────────────────────────────────────────────────────────────

def insert_backtest_run(
    user_id: int,
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
            (id, user_id, strategy, params_json, ticker, period_start, period_end,
             total_return, mdd, sharpe, equity_curve,
             tickers_json, cagr, weights_history, contribution_json, warnings_json, risk_options_json)
            VALUES (:id, :uid, :strategy, :params_json, :ticker, :period_start, :period_end,
                    :total_return, :mdd, :sharpe, :equity_curve,
                    :tickers_json, :cagr, :weights_history, :contribution_json, :warnings_json, :risk_options_json)
        """), {
            "id": run_id, "uid": user_id, "strategy": strategy,
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


# ── OHLCV Cache (공유) ────────────────────────────────────────────────────────

def get_ohlcv_range(ticker: str) -> "tuple[date, date] | None":
    with session() as s:
        row = s.execute(text(
            "SELECT MIN(date), MAX(date) FROM prices_cache WHERE ticker = :ticker"
        ), {"ticker": ticker}).fetchone()
        if row is None or row[0] is None:
            return None
        return (row[0], row[1])


def upsert_ohlcv_rows(rows: list[dict]) -> None:
    if not rows:
        return
    with session() as s:
        s.execute(text("""
            INSERT OR IGNORE INTO prices_cache (ticker, date, open, high, low, close, volume)
            VALUES (:ticker, :date, :open, :high, :low, :close, :volume)
        """), rows)
        s.commit()


# ── Quant Scores (공유) ───────────────────────────────────────────────────────

def upsert_quant_scores(rows: list[dict]) -> None:
    if not rows:
        return
    with session() as s:
        for r in rows:
            s.execute(text("""
                INSERT INTO quant_scores
                    (ticker, universe, as_of,
                     pct_momentum, pct_valuation, pct_eps_momentum, pct_quality, pct_technical,
                     raw_momentum, raw_fwd_pe, raw_pbr, raw_psr, raw_trailing_pe,
                     raw_eps_ttm, raw_fwd_eps, raw_roe, raw_debt_ratio, raw_rsi,
                     above_ma200, cfo_positive, company_name)
                VALUES
                    (:ticker, :universe, :as_of,
                     :pct_momentum, :pct_valuation, :pct_eps_momentum, :pct_quality, :pct_technical,
                     :raw_momentum, :raw_fwd_pe, :raw_pbr, :raw_psr, :raw_trailing_pe,
                     :raw_eps_ttm, :raw_fwd_eps, :raw_roe, :raw_debt_ratio, :raw_rsi,
                     :above_ma200, :cfo_positive, :company_name)
                ON CONFLICT (ticker, universe, as_of) DO UPDATE SET
                    pct_momentum = excluded.pct_momentum,
                    pct_valuation = excluded.pct_valuation,
                    pct_eps_momentum = excluded.pct_eps_momentum,
                    pct_quality = excluded.pct_quality,
                    pct_technical = excluded.pct_technical,
                    raw_momentum = excluded.raw_momentum,
                    raw_fwd_pe = excluded.raw_fwd_pe,
                    raw_pbr = excluded.raw_pbr,
                    raw_psr = excluded.raw_psr,
                    raw_trailing_pe = excluded.raw_trailing_pe,
                    raw_eps_ttm = excluded.raw_eps_ttm,
                    raw_fwd_eps = excluded.raw_fwd_eps,
                    raw_roe = excluded.raw_roe,
                    raw_debt_ratio = excluded.raw_debt_ratio,
                    raw_rsi = excluded.raw_rsi,
                    above_ma200 = excluded.above_ma200,
                    cfo_positive = excluded.cfo_positive,
                    company_name = excluded.company_name
            """), r)
        s.commit()


def get_latest_quant_scores(universe: str) -> list[dict]:
    with session() as s:
        rows = s.execute(text("""
            SELECT * FROM quant_scores
            WHERE universe = :universe
              AND as_of = (SELECT MAX(as_of) FROM quant_scores WHERE universe = :universe)
            ORDER BY ticker
        """), {"universe": universe}).mappings().all()
        return [dict(r) for r in rows]


def get_quant_ticker(ticker: str, universe: str) -> dict | None:
    with session() as s:
        row = s.execute(text("""
            SELECT * FROM quant_scores
            WHERE ticker = :ticker AND universe = :universe
              AND as_of = (SELECT MAX(as_of) FROM quant_scores WHERE universe = :universe)
        """), {"ticker": ticker, "universe": universe}).mappings().fetchone()
        return dict(row) if row else None


# ── Ticker Notes ──────────────────────────────────────────────────────────────

def upsert_ticker_note(
    user_id: int,
    ticker: str,
    opinion: str | None,
    target_price: float | None,
    memo: str | None,
    tags: str | None,
) -> None:
    with session() as s:
        s.execute(text("""
            INSERT INTO ticker_notes (user_id, ticker, opinion, target_price, memo, tags, updated_at)
            VALUES (:uid, :ticker, :opinion, :target_price, :memo, :tags, :now)
            ON CONFLICT (user_id, ticker) DO UPDATE SET
                opinion      = excluded.opinion,
                target_price = excluded.target_price,
                memo         = excluded.memo,
                tags         = excluded.tags,
                updated_at   = excluded.updated_at
        """), {"uid": user_id, "ticker": ticker, "opinion": opinion,
               "target_price": target_price, "memo": memo, "tags": tags,
               "now": datetime.now()})
        s.commit()


def get_ticker_note(user_id: int, ticker: str) -> dict | None:
    with session() as s:
        row = s.execute(
            text("SELECT * FROM ticker_notes WHERE user_id = :uid AND ticker = :ticker"),
            {"uid": user_id, "ticker": ticker},
        ).mappings().fetchone()
        return dict(row) if row else None


# ── Workspace ─────────────────────────────────────────────────────────────────

def get_workspace(user_id: int, name: str = "default") -> dict:
    with session() as s:
        row = s.execute(
            text("SELECT layout_json FROM user_workspaces WHERE user_id = :uid AND name = :n"),
            {"uid": user_id, "n": name},
        ).fetchone()
        return json.loads(row[0]) if row else {}


def save_workspace(user_id: int, layout: dict, name: str = "default") -> None:
    with session() as s:
        payload = json.dumps(layout, ensure_ascii=False)
        s.execute(text("""
            INSERT INTO user_workspaces (user_id, name, layout_json, updated_at)
            VALUES (:uid, :n, :payload, current_timestamp)
            ON CONFLICT (user_id, name) DO UPDATE SET
                layout_json = excluded.layout_json,
                updated_at  = excluded.updated_at
        """), {"uid": user_id, "n": name, "payload": payload})
        s.commit()


# ── 알림 조건 CRUD ──────────────────────────────────────────

def create_alert(user_id: int, ticker: str, condition_type: str, condition_value: float | None) -> int:
    with session() as s:
        row = s.execute(text("""
            INSERT INTO user_alerts (user_id, ticker, condition_type, condition_value)
            VALUES (:u, :t, :ct, :cv)
            RETURNING id
        """), {"u": user_id, "t": ticker.upper(), "ct": condition_type, "cv": condition_value}).fetchone()
        s.commit()
        return row[0]


def get_user_alerts(user_id: int) -> list[dict]:
    with session() as s:
        rows = s.execute(text("""
            SELECT id, ticker, condition_type, condition_value, enabled, created_at
            FROM user_alerts WHERE user_id = :u AND enabled = TRUE
            ORDER BY created_at DESC
        """), {"u": user_id}).fetchall()
        return [{"id": r[0], "ticker": r[1], "condition_type": r[2],
                 "condition_value": r[3], "enabled": r[4], "created_at": r[5]} for r in rows]


def delete_user_alert(user_id: int, alert_id: int) -> bool:
    with session() as s:
        row = s.execute(text(
            "SELECT id FROM user_alerts WHERE id = :id AND user_id = :u"
        ), {"id": alert_id, "u": user_id}).fetchone()
        if row is None:
            return False
        s.execute(text(
            "DELETE FROM user_alerts WHERE id = :id AND user_id = :u"
        ), {"id": alert_id, "u": user_id})
        s.commit()
        return True


def get_all_enabled_alerts() -> list[dict]:
    """스케줄러용 — 전체 사용자 활성 알림."""
    with session() as s:
        rows = s.execute(text("""
            SELECT id, user_id, ticker, condition_type, condition_value
            FROM user_alerts WHERE enabled = TRUE
        """)).fetchall()
        return [{"id": r[0], "user_id": r[1], "ticker": r[2],
                 "condition_type": r[3], "condition_value": r[4]} for r in rows]


def has_recent_alert_event(alert_id: int, minutes: int = 60) -> bool:
    """같은 alert_id가 최근 N분 내 이미 발화했는지 확인 (중복 방지)."""
    with session() as s:
        row = s.execute(text("""
            SELECT COUNT(*) FROM user_alert_events
            WHERE alert_id = :aid
              AND triggered_at >= current_timestamp - INTERVAL (CAST(:m AS VARCHAR) || ' minutes')
        """), {"aid": alert_id, "m": minutes}).fetchone()
        return row[0] > 0


def insert_alert_event(user_id: int, alert_id: int, ticker: str,
                       condition_type: str, condition_value: float | None,
                       triggered_price: float) -> None:
    with session() as s:
        s.execute(text("""
            INSERT INTO user_alert_events
              (user_id, alert_id, ticker, condition_type, condition_value, triggered_price)
            VALUES (:u, :aid, :t, :ct, :cv, :price)
        """), {"u": user_id, "aid": alert_id, "t": ticker, "ct": condition_type,
               "cv": condition_value, "price": triggered_price})
        s.commit()


def get_alert_events(user_id: int, limit: int = 50) -> list[dict]:
    with session() as s:
        rows = s.execute(text("""
            SELECT id, ticker, condition_type, condition_value, triggered_price, triggered_at, read
            FROM user_alert_events WHERE user_id = :u
            ORDER BY triggered_at DESC LIMIT :lim
        """), {"u": user_id, "lim": limit}).fetchall()
        return [{"id": r[0], "ticker": r[1], "condition_type": r[2], "condition_value": r[3],
                 "triggered_price": r[4], "triggered_at": r[5], "read": r[6]} for r in rows]


def get_unread_alert_events(user_id: int) -> list[dict]:
    with session() as s:
        rows = s.execute(text("""
            SELECT id, ticker, condition_type, condition_value, triggered_price, triggered_at, read
            FROM user_alert_events WHERE user_id = :u AND read = FALSE
            ORDER BY triggered_at DESC
        """), {"u": user_id}).fetchall()
        return [{"id": r[0], "ticker": r[1], "condition_type": r[2], "condition_value": r[3],
                 "triggered_price": r[4], "triggered_at": r[5], "read": r[6]} for r in rows]


def mark_all_alert_events_read(user_id: int) -> None:
    with session() as s:
        s.execute(text(
            "UPDATE user_alert_events SET read = TRUE WHERE user_id = :u AND read = FALSE"
        ), {"u": user_id})
        s.commit()


# ── Trades ────────────────────────────────────────────────────────────────────

def create_trade(
    user_id: int, ticker: str, market: str | None,
    trade_type: str, quantity: float, price: float,
    currency: str, traded_at: str, fee: float = 0, note: str | None = None
) -> int:
    with session() as s:
        row = s.execute(text("SELECT nextval('trades_id_seq')")).fetchone()
        trade_id = row[0]
        s.execute(text("""
            INSERT INTO trades
              (id, user_id, ticker, market, trade_type, quantity, price, currency, traded_at, fee, note)
            VALUES
              (:id, :uid, :ticker, :market, :type, :qty, :price, :cur, :date, :fee, :note)
        """), {"id": trade_id, "uid": user_id, "ticker": ticker, "market": market,
               "type": trade_type, "qty": quantity, "price": price, "cur": currency,
               "date": traded_at, "fee": fee, "note": note})
        s.commit()
        _sync_holding_from_trades(s, user_id, ticker)
        s.commit()
    return trade_id


def get_trades(user_id: int, ticker: str | None = None) -> list[dict]:
    with session() as s:
        if ticker:
            rows = s.execute(text("""
                SELECT id, ticker, market, trade_type, quantity, price, currency,
                       traded_at, fee, note, created_at
                FROM trades WHERE user_id = :uid AND ticker = :ticker
                ORDER BY traded_at DESC, created_at DESC
            """), {"uid": user_id, "ticker": ticker}).fetchall()
        else:
            rows = s.execute(text("""
                SELECT id, ticker, market, trade_type, quantity, price, currency,
                       traded_at, fee, note, created_at
                FROM trades WHERE user_id = :uid
                ORDER BY traded_at DESC, created_at DESC
            """), {"uid": user_id}).fetchall()
    cols = ["id", "ticker", "market", "trade_type", "quantity", "price", "currency",
            "traded_at", "fee", "note", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


def delete_trade(user_id: int, trade_id: int) -> bool:
    with session() as s:
        row = s.execute(text(
            "SELECT ticker FROM trades WHERE id = :id AND user_id = :uid"
        ), {"id": trade_id, "uid": user_id}).fetchone()
        if not row:
            return False
        ticker = row[0]
        s.execute(text(
            "DELETE FROM trades WHERE id = :id AND user_id = :uid"
        ), {"id": trade_id, "uid": user_id})
        s.commit()
        _sync_holding_from_trades(s, user_id, ticker)
        s.commit()
    return True


def _sync_holding_from_trades(s, user_id: int, ticker: str) -> None:
    """거래 내역에서 avg_price/quantity를 재계산해 holdings에 반영."""
    rows = s.execute(text("""
        SELECT trade_type, quantity, price
        FROM trades
        WHERE user_id = :uid AND ticker = :ticker
        ORDER BY traded_at ASC, created_at ASC
    """), {"uid": user_id, "ticker": ticker}).fetchall()

    total_qty = 0.0
    total_cost = 0.0
    for trade_type, qty, price in rows:
        if trade_type == "BUY":
            total_cost += qty * price
            total_qty += qty
        elif trade_type == "SELL":
            total_qty -= qty

    if total_qty <= 0:
        s.execute(text(
            "DELETE FROM holdings WHERE user_id = :uid AND ticker = :ticker"
        ), {"uid": user_id, "ticker": ticker})
        return

    buy_qty = sum(qty for tt, qty, _ in rows if tt == "BUY")
    avg_price = total_cost / buy_qty if buy_qty > 0 else 0.0

    existing = s.execute(text(
        "SELECT ticker FROM holdings WHERE user_id = :uid AND ticker = :ticker"
    ), {"uid": user_id, "ticker": ticker}).fetchone()

    if existing:
        s.execute(text("""
            UPDATE holdings SET quantity = :qty, avg_price = :avg, updated_at = current_timestamp
            WHERE user_id = :uid AND ticker = :ticker
        """), {"qty": total_qty, "avg": avg_price, "uid": user_id, "ticker": ticker})


def get_realized_pnl(user_id: int) -> float:
    """전체 실현 손익 합산. SELL 시점의 avg_price 기준."""
    trades = get_trades(user_id)
    by_ticker: dict[str, list] = {}
    for t in sorted(trades, key=lambda x: (x["traded_at"], str(x["created_at"]))):
        by_ticker.setdefault(t["ticker"], []).append(t)

    total_pnl = 0.0
    for ticker_trades in by_ticker.values():
        buy_qty = 0.0
        buy_cost = 0.0
        for t in ticker_trades:
            if t["trade_type"] == "BUY":
                buy_qty += t["quantity"]
                buy_cost += t["quantity"] * t["price"]
            elif t["trade_type"] == "SELL" and buy_qty > 0:
                avg = buy_cost / buy_qty
                total_pnl += (t["price"] - avg) * t["quantity"]
    return total_pnl


# ── Performance ───────────────────────────────────────────────────────────────

import math


def _period_to_days(period: str) -> int:
    return {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "all": 9999}[period]


def get_portfolio_returns(user_id: int, period: str = "6m") -> list[dict]:
    """portfolio_snapshots에서 일별 수익률 시계열 반환."""
    from datetime import datetime, timedelta
    days = _period_to_days(period)
    cutoff = datetime.now() - timedelta(days=days)
    with session() as s:
        rows = s.execute(text("""
            SELECT ts::DATE as date, total_equity_krw
            FROM portfolio_snapshots
            WHERE user_id = :uid
              AND ts >= :cutoff
            ORDER BY date ASC
        """), {"uid": user_id, "cutoff": cutoff}).fetchall()
    return [{"date": str(r[0]), "equity": float(r[1])} for r in rows]


def calc_performance(equity_series: list[dict]) -> dict:
    """Sharpe, MDD, total_return 계산."""
    if len(equity_series) < 2:
        return {"sharpe": 0.0, "mdd": 0.0, "total_return": 0.0, "annualized_return": 0.0}

    equities = [e["equity"] for e in equity_series]
    returns = [(equities[i] - equities[i-1]) / equities[i-1]
               for i in range(1, len(equities)) if equities[i-1] > 0]

    if not returns:
        return {"sharpe": 0.0, "mdd": 0.0, "total_return": 0.0, "annualized_return": 0.0}

    n = len(returns)
    mean_r = sum(returns) / n
    variance = sum((r - mean_r) ** 2 for r in returns) / n
    std_r = math.sqrt(variance) if variance > 0 else 0.0
    sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0.0

    # MDD
    peak = equities[0]
    mdd = 0.0
    for e in equities:
        if e > peak:
            peak = e
        dd = (peak - e) / peak if peak > 0 else 0
        if dd > mdd:
            mdd = dd

    total_return = (equities[-1] - equities[0]) / equities[0] * 100 if equities[0] > 0 else 0
    days = len(equities)
    annualized = ((1 + total_return / 100) ** (365 / days) - 1) * 100 if days > 0 else 0

    return {
        "sharpe": round(sharpe, 3),
        "mdd": round(-mdd * 100, 2),
        "total_return": round(total_return, 2),
        "annualized_return": round(annualized, 2),
    }


def set_holding_target_weight(user_id: int, ticker: str, target_weight: float | None) -> None:
    with session() as s:
        s.execute(text("""
            UPDATE holdings SET target_weight = :tw
            WHERE user_id = :uid AND ticker = :ticker
        """), {"tw": target_weight, "uid": user_id, "ticker": ticker})
        s.commit()
