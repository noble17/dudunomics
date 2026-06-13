"""DuckDB + SQLAlchemy 기반 데이터 접근 계층."""
import json
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from core.data.normalization import normalize_finite_numbers

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

    CREATE TABLE IF NOT EXISTS ticker_profiles (
        ticker     TEXT PRIMARY KEY,
        name       TEXT,
        market     TEXT,
        country    TEXT,
        currency   TEXT,
        sector     TEXT,
        industry   TEXT,
        exchange   TEXT,
        source     TEXT,
        updated_at TIMESTAMP DEFAULT current_timestamp
    );

    CREATE TABLE IF NOT EXISTS fundamental_snapshots (
        ticker           TEXT NOT NULL,
        as_of            DATE NOT NULL,
        source           TEXT NOT NULL,
        per              DOUBLE,
        pbr              DOUBLE,
        psr              DOUBLE,
        peg              DOUBLE,
        forward_pe       DOUBLE,
        trailing_pe      DOUBLE,
        forward_eps      DOUBLE,
        eps_ttm          DOUBLE,
        roe              DOUBLE,
        roic             DOUBLE,
        debt_ratio       DOUBLE,
        current_ratio    DOUBLE,
        gross_margin     DOUBLE,
        operating_margin DOUBLE,
        revenue_growth   DOUBLE,
        eps_growth       DOUBLE,
        market_cap       DOUBLE,
        raw_json         JSON,
        fetched_at       TIMESTAMP DEFAULT current_timestamp,
        PRIMARY KEY (ticker, as_of, source)
    );

    CREATE TABLE IF NOT EXISTS price_target_consensus_snapshots (
        ticker           TEXT NOT NULL,
        as_of            DATE NOT NULL,
        source           TEXT NOT NULL,
        consensus_status TEXT,
        consensus_message TEXT,
        current_price    DOUBLE,
        target_mean      DOUBLE,
        target_median    DOUBLE,
        target_low       DOUBLE,
        target_high      DOUBLE,
        upside_pct       DOUBLE,
        analyst_count    INTEGER,
        consensus_as_of  TEXT,
        fallback_used    BOOLEAN DEFAULT FALSE,
        attempts_json    JSON,
        fetched_at       TIMESTAMP DEFAULT current_timestamp,
        PRIMARY KEY (ticker, as_of, source)
    );

    CREATE TABLE IF NOT EXISTS ticker_data_status (
        ticker          TEXT NOT NULL,
        data_type       TEXT NOT NULL,
        source          TEXT NOT NULL,
        min_date        DATE,
        max_date        DATE,
        last_fetched_at TIMESTAMP,
        last_success_at TIMESTAMP,
        last_error      TEXT,
        coverage_json   JSON,
        PRIMARY KEY (ticker, data_type, source)
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

    CREATE TABLE IF NOT EXISTS quant_rank_history (
        universe         TEXT,
        as_of            DATE,
        ticker           TEXT,
        growth_composite DOUBLE,
        rank             INTEGER,
        PRIMARY KEY (universe, as_of, ticker)
    );

    CREATE TABLE IF NOT EXISTS user_workspaces (
        user_id     INTEGER NOT NULL,
        name        TEXT NOT NULL DEFAULT 'default',
        layout_json TEXT NOT NULL DEFAULT '{}',
        updated_at  TIMESTAMP DEFAULT current_timestamp,
        PRIMARY KEY (user_id, name)
    );

    CREATE TABLE IF NOT EXISTS growth_watchlist (
        user_id    INTEGER NOT NULL,
        universe   TEXT NOT NULL,
        ticker     TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT current_timestamp,
        PRIMARY KEY (user_id, universe, ticker)
    );

    CREATE SEQUENCE IF NOT EXISTS watchlists_id_seq START 1;
    CREATE TABLE IF NOT EXISTS watchlists (
        id          INTEGER DEFAULT nextval('watchlists_id_seq') PRIMARY KEY,
        user_id     INTEGER NOT NULL,
        name        TEXT NOT NULL,
        description TEXT,
        created_at  TIMESTAMP DEFAULT current_timestamp,
        updated_at  TIMESTAMP DEFAULT current_timestamp
    );

    CREATE TABLE IF NOT EXISTS watchlist_items (
        watchlist_id INTEGER NOT NULL,
        ticker       TEXT NOT NULL,
        universe     TEXT NOT NULL DEFAULT 'sp500',
        name         TEXT,
        memo         TEXT,
        timing_alert_enabled BOOLEAN DEFAULT FALSE,
        created_at   TIMESTAMP DEFAULT current_timestamp,
        PRIMARY KEY (watchlist_id, ticker, universe)
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
        source      TEXT DEFAULT 'manual',
        external_id TEXT,
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

    CREATE TABLE IF NOT EXISTS quarterly_financials (
        ticker      TEXT    NOT NULL,
        period      TEXT    NOT NULL,
        eps         DOUBLE,
        roe         DOUBLE,
        debt_ratio  DOUBLE,
        revenue     DOUBLE,
        op_income   DOUBLE,
        source      TEXT,
        PRIMARY KEY (ticker, period)
    );

    CREATE SEQUENCE IF NOT EXISTS golden_cross_events_id_seq START 1;
    CREATE TABLE IF NOT EXISTS golden_cross_events (
        id                 INTEGER DEFAULT nextval('golden_cross_events_id_seq') PRIMARY KEY,
        ticker             VARCHAR NOT NULL,
        market             VARCHAR NOT NULL,
        group_name         VARCHAR,
        name               VARCHAR,
        first_detected_at  DATE NOT NULL,
        last_sent_at       TIMESTAMP,
        day_count          INTEGER DEFAULT 1,
        UNIQUE(ticker)
    );

    CREATE SEQUENCE IF NOT EXISTS golden_cross_history_id_seq START 1;
    CREATE TABLE IF NOT EXISTS golden_cross_history (
        id                 INTEGER DEFAULT nextval('golden_cross_history_id_seq') PRIMARY KEY,
        ticker             VARCHAR NOT NULL,
        market             VARCHAR NOT NULL,
        group_name         VARCHAR,
        name               VARCHAR,
        status             VARCHAR NOT NULL,
        day_count          INTEGER,
        cross_start_date   DATE,
        checked_at         TIMESTAMP DEFAULT current_timestamp,
        close              DOUBLE,
        ema5               DOUBLE,
        ema20              DOUBLE,
        ema60              DOUBLE,
        reason             VARCHAR
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
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_ev_ebitda      DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_peg            DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_fcf_yield      DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_eps_momentum   DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS negative_book_value BOOLEAN DEFAULT FALSE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS sector             TEXT",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS industry           TEXT",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS pct_growth                  DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS pct_profitability           DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS pct_cashflow                DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS pct_stability               DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS growth_composite            DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_roic                    DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_gross_margin            DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_oper_margin             DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_current_ratio           DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_sales_growth            DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_rev_yoy                 DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_market_cap_usd_m        DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_market_cap_krw          DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_fwd_rev_growth          DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_fwd_eps_growth          DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_operating_cashflow      DOUBLE",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS data_coverage               JSON",
            "ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS sector_percentile_fallback  BOOLEAN DEFAULT FALSE",
            "CREATE TABLE IF NOT EXISTS quant_rank_history (universe TEXT, as_of DATE, ticker TEXT, growth_composite DOUBLE, rank INTEGER, PRIMARY KEY (universe, as_of, ticker))",
            "CREATE INDEX IF NOT EXISTS idx_rank_hist ON quant_rank_history (universe, as_of)",
            "CREATE TABLE IF NOT EXISTS quarterly_financials (ticker TEXT NOT NULL, period TEXT NOT NULL, eps DOUBLE, roe DOUBLE, debt_ratio DOUBLE, revenue DOUBLE, op_income DOUBLE, source TEXT, PRIMARY KEY (ticker, period))",
            "CREATE TABLE IF NOT EXISTS growth_watchlist (user_id INTEGER NOT NULL, universe TEXT NOT NULL, ticker TEXT NOT NULL, created_at TIMESTAMP DEFAULT current_timestamp, PRIMARY KEY (user_id, universe, ticker))",
            "CREATE SEQUENCE IF NOT EXISTS watchlists_id_seq START 1",
            "CREATE TABLE IF NOT EXISTS watchlists (id INTEGER DEFAULT nextval('watchlists_id_seq') PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT NOT NULL, description TEXT, created_at TIMESTAMP DEFAULT current_timestamp, updated_at TIMESTAMP DEFAULT current_timestamp)",
            "CREATE TABLE IF NOT EXISTS watchlist_items (watchlist_id INTEGER NOT NULL, ticker TEXT NOT NULL, universe TEXT NOT NULL DEFAULT 'sp500', name TEXT, memo TEXT, timing_alert_enabled BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT current_timestamp, PRIMARY KEY (watchlist_id, ticker, universe))",
            "ALTER TABLE watchlist_items ADD COLUMN IF NOT EXISTS timing_alert_enabled BOOLEAN DEFAULT FALSE",
            "CREATE TABLE IF NOT EXISTS ticker_profiles (ticker TEXT PRIMARY KEY, name TEXT, market TEXT, country TEXT, currency TEXT, sector TEXT, industry TEXT, exchange TEXT, source TEXT, updated_at TIMESTAMP DEFAULT current_timestamp)",
            "CREATE TABLE IF NOT EXISTS fundamental_snapshots (ticker TEXT NOT NULL, as_of DATE NOT NULL, source TEXT NOT NULL, per DOUBLE, pbr DOUBLE, psr DOUBLE, peg DOUBLE, forward_pe DOUBLE, trailing_pe DOUBLE, forward_eps DOUBLE, eps_ttm DOUBLE, roe DOUBLE, roic DOUBLE, debt_ratio DOUBLE, current_ratio DOUBLE, gross_margin DOUBLE, operating_margin DOUBLE, revenue_growth DOUBLE, eps_growth DOUBLE, market_cap DOUBLE, raw_json JSON, fetched_at TIMESTAMP DEFAULT current_timestamp, PRIMARY KEY (ticker, as_of, source))",
            "CREATE TABLE IF NOT EXISTS price_target_consensus_snapshots (ticker TEXT NOT NULL, as_of DATE NOT NULL, source TEXT NOT NULL, consensus_status TEXT, consensus_message TEXT, current_price DOUBLE, target_mean DOUBLE, target_median DOUBLE, target_low DOUBLE, target_high DOUBLE, upside_pct DOUBLE, analyst_count INTEGER, consensus_as_of TEXT, fallback_used BOOLEAN DEFAULT FALSE, attempts_json JSON, fetched_at TIMESTAMP DEFAULT current_timestamp, PRIMARY KEY (ticker, as_of, source))",
            "ALTER TABLE price_target_consensus_snapshots ADD COLUMN IF NOT EXISTS current_price DOUBLE",
            "ALTER TABLE price_target_consensus_snapshots ADD COLUMN IF NOT EXISTS upside_pct DOUBLE",
            "CREATE TABLE IF NOT EXISTS ticker_data_status (ticker TEXT NOT NULL, data_type TEXT NOT NULL, source TEXT NOT NULL, min_date DATE, max_date DATE, last_fetched_at TIMESTAMP, last_success_at TIMESTAMP, last_error TEXT, coverage_json JSON, PRIMARY KEY (ticker, data_type, source))",
            "CREATE TABLE IF NOT EXISTS holding_sources (user_id INTEGER NOT NULL, source TEXT NOT NULL, account_id TEXT NOT NULL DEFAULT '', ticker TEXT NOT NULL, name TEXT NOT NULL, currency TEXT NOT NULL, quantity DOUBLE NOT NULL, avg_price DOUBLE NOT NULL, sector TEXT, market TEXT, excluded_from_portfolio BOOLEAN DEFAULT FALSE, updated_at TIMESTAMP DEFAULT current_timestamp, PRIMARY KEY (user_id, source, account_id, ticker))",
            "CREATE TABLE IF NOT EXISTS portfolio_snapshot_rollups (user_id INTEGER NOT NULL, bucket TEXT NOT NULL, ts TIMESTAMP NOT NULL, total_equity_krw DOUBLE, total_with_cash_krw DOUBLE, cash_krw DOUBLE, total_equity_usd DOUBLE, total_with_cash_usd DOUBLE, cash_usd DOUBLE, usdkrw DOUBLE, PRIMARY KEY (user_id, bucket, ts))",
            "CREATE SEQUENCE IF NOT EXISTS job_runs_id_seq START 1",
            "CREATE TABLE IF NOT EXISTS job_runs (id INTEGER DEFAULT nextval('job_runs_id_seq') PRIMARY KEY, job_id TEXT NOT NULL, status TEXT NOT NULL, trigger_type TEXT NOT NULL, started_at TIMESTAMP NOT NULL, finished_at TIMESTAMP, duration_ms INTEGER, message TEXT, error TEXT, meta_json JSON)",
            "CREATE INDEX IF NOT EXISTS idx_job_runs_job_started ON job_runs (job_id, started_at)",
            "ALTER TABLE golden_cross_events ADD COLUMN IF NOT EXISTS group_name VARCHAR",
            "CREATE SEQUENCE IF NOT EXISTS golden_cross_history_id_seq START 1",
            "CREATE TABLE IF NOT EXISTS golden_cross_history (id INTEGER DEFAULT nextval('golden_cross_history_id_seq') PRIMARY KEY, ticker VARCHAR NOT NULL, market VARCHAR NOT NULL, group_name VARCHAR, name VARCHAR, status VARCHAR NOT NULL, day_count INTEGER, cross_start_date DATE, checked_at TIMESTAMP DEFAULT current_timestamp, close DOUBLE, ema5 DOUBLE, ema20 DOUBLE, ema60 DOUBLE, reason VARCHAR)",
            "CREATE INDEX IF NOT EXISTS idx_golden_cross_history_checked ON golden_cross_history (checked_at)",
            "CREATE INDEX IF NOT EXISTS idx_golden_cross_history_ticker ON golden_cross_history (ticker, checked_at)",
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

    if not _has_column(conn, "trades", "source"):
        conn.execute(text("ALTER TABLE trades ADD COLUMN source TEXT DEFAULT 'manual'"))
        conn.execute(text("UPDATE trades SET source = 'manual' WHERE source IS NULL"))
    if not _has_column(conn, "trades", "external_id"):
        conn.execute(text("ALTER TABLE trades ADD COLUMN external_id TEXT"))
    try:
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_source_external "
            "ON trades (user_id, source, external_id)"
        ))
    except Exception:
        pass

    conn.execute(text("CREATE SEQUENCE IF NOT EXISTS job_runs_id_seq START 1"))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS job_runs (
            id           INTEGER DEFAULT nextval('job_runs_id_seq') PRIMARY KEY,
            job_id       TEXT NOT NULL,
            status       TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            started_at   TIMESTAMP NOT NULL,
            finished_at  TIMESTAMP,
            duration_ms  INTEGER,
            message      TEXT,
            error        TEXT,
            meta_json    JSON
        )
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_job_runs_job_started ON job_runs (job_id, started_at)"
    ))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS portfolio_snapshot_rollups (
            user_id              INTEGER NOT NULL,
            bucket               TEXT NOT NULL,
            ts                   TIMESTAMP NOT NULL,
            total_equity_krw     DOUBLE,
            total_with_cash_krw  DOUBLE,
            cash_krw             DOUBLE,
            total_equity_usd     DOUBLE,
            total_with_cash_usd  DOUBLE,
            cash_usd             DOUBLE,
            usdkrw               DOUBLE,
            PRIMARY KEY (user_id, bucket, ts)
        )
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS holding_sources (
            user_id    INTEGER NOT NULL,
            source     TEXT NOT NULL,
            account_id TEXT NOT NULL DEFAULT '',
            ticker     TEXT NOT NULL,
            name       TEXT NOT NULL,
            currency   TEXT NOT NULL,
            quantity   DOUBLE NOT NULL,
            avg_price  DOUBLE NOT NULL,
            sector     TEXT,
            market     TEXT,
            excluded_from_portfolio BOOLEAN DEFAULT FALSE,
            updated_at TIMESTAMP DEFAULT current_timestamp,
            PRIMARY KEY (user_id, source, account_id, ticker)
        )
    """))
    if not _has_column(conn, "holding_sources", "excluded_from_portfolio"):
        conn.execute(text(
            "ALTER TABLE holding_sources ADD COLUMN excluded_from_portfolio BOOLEAN DEFAULT FALSE"
        ))
    existing_sources = conn.execute(text("SELECT COUNT(*) FROM holding_sources")).fetchone()[0]
    if existing_sources == 0:
        conn.execute(text("""
            INSERT INTO holding_sources
              (user_id, source, account_id, ticker, name, currency, quantity, avg_price, sector, market, excluded_from_portfolio, updated_at)
            SELECT user_id, 'manual', '', ticker, name, currency, quantity, avg_price, sector, market, false, updated_at
            FROM holdings
            WHERE quantity > 0
        """))

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


def get_active_user_ids() -> list[int]:
    with session() as s:
        rows = s.execute(text(
            "SELECT id FROM users WHERE is_active = true ORDER BY id"
        )).fetchall()
        return [r[0] for r in rows]


# ── Holdings ──────────────────────────────────────────────────────────────────

def get_holdings(user_id: int, include_excluded: bool = False) -> list[dict]:
    with session() as s:
        if include_excluded:
            rows = s.execute(text("""
                SELECT
                  user_id, ticker,
                  any_value(name) AS name,
                  any_value(currency) AS currency,
                  sum(quantity) AS quantity,
                  sum(quantity * avg_price) / nullif(sum(quantity), 0) AS avg_price,
                  any_value(sector) AS sector,
                  any_value(market) AS market,
                  max(updated_at) AS updated_at
                FROM holding_sources
                WHERE user_id = :uid AND quantity > 0
                GROUP BY user_id, ticker
                ORDER BY ticker
            """), {"uid": user_id}).mappings().all()
        else:
            rows = s.execute(
                text("SELECT * FROM holdings WHERE user_id = :uid ORDER BY ticker"),
                {"uid": user_id},
            ).mappings().all()
        result = [dict(r) for r in rows]
        if not result:
            return result
        sources = s.execute(text("""
            SELECT source, account_id, ticker, name, currency, quantity, avg_price, sector, market, excluded_from_portfolio, updated_at
            FROM holding_sources
            WHERE user_id = :uid
            ORDER BY ticker, source, account_id
        """), {"uid": user_id}).mappings().all()
        by_ticker: dict[str, list[dict]] = {}
        for row in sources:
            by_ticker.setdefault(row["ticker"], []).append(dict(row))
        for row in result:
            row["sources"] = by_ticker.get(row["ticker"], [])
        return result


def upsert_holding(
    user_id: int,
    ticker: str,
    name: str,
    currency: str,
    quantity: float,
    avg_price: float,
    sector: str | None = None,
    market: str | None = None,
    source: str = "manual",
    account_id: str = "",
    preserve_display_fields: bool = False,
):
    now = datetime.now()
    with session() as s:
        s.execute(text("""
            INSERT INTO holding_sources
              (user_id, source, account_id, ticker, name, currency, quantity, avg_price, sector, market, updated_at)
            VALUES (:uid, :source, :account_id, :ticker, :name, :currency, :quantity, :avg_price, :sector, :market, :now)
            ON CONFLICT (user_id, source, account_id, ticker) DO UPDATE SET
                name       = CASE WHEN :preserve_display_fields THEN holding_sources.name ELSE excluded.name END,
                currency   = excluded.currency,
                quantity   = excluded.quantity,
                avg_price  = excluded.avg_price,
                sector     = CASE WHEN :preserve_display_fields THEN holding_sources.sector ELSE excluded.sector END,
                market     = excluded.market,
                updated_at = :now
        """), {"uid": user_id, "source": source, "account_id": account_id, "ticker": ticker, "name": name, "currency": currency,
               "quantity": quantity, "avg_price": avg_price,
               "sector": sector, "market": market, "preserve_display_fields": preserve_display_fields, "now": now})
        _rebuild_holding_aggregate(s, user_id, ticker)
        s.commit()


def delete_holding(user_id: int, ticker: str, source: str = "manual", account_id: str = ""):
    with session() as s:
        s.execute(
            text("DELETE FROM holding_sources WHERE user_id = :uid AND ticker = :ticker AND source = :source AND account_id = :account_id"),
            {"uid": user_id, "ticker": ticker, "source": source, "account_id": account_id},
        )
        _rebuild_holding_aggregate(s, user_id, ticker)
        s.commit()


def update_holding_source_meta(
    user_id: int,
    ticker: str,
    source: str,
    account_id: str = "",
    name: str | None = None,
    sector: str | None = None,
    excluded_from_portfolio: bool | None = None,
) -> bool:
    set_name = name is not None
    set_sector = sector is not None
    set_excluded = excluded_from_portfolio is not None
    with session() as s:
        s.execute(text("""
            UPDATE holding_sources
            SET name = CASE WHEN :set_name THEN :name ELSE name END,
                sector = CASE WHEN :set_sector THEN :sector ELSE sector END,
                excluded_from_portfolio = CASE WHEN :set_excluded THEN :excluded ELSE excluded_from_portfolio END,
                updated_at = :now
            WHERE user_id = :uid
              AND ticker = :ticker
              AND source = :source
              AND account_id = :account_id
        """), {
            "uid": user_id,
            "ticker": ticker,
            "source": source,
            "account_id": account_id,
            "name": name,
            "set_name": set_name,
            "sector": sector,
            "set_sector": set_sector,
            "set_excluded": set_excluded,
            "excluded": bool(excluded_from_portfolio) if excluded_from_portfolio is not None else False,
            "now": datetime.now(),
        })
        exists = s.execute(text("""
            SELECT 1 FROM holding_sources
            WHERE user_id = :uid
              AND ticker = :ticker
              AND source = :source
              AND account_id = :account_id
        """), {
            "uid": user_id,
            "ticker": ticker,
            "source": source,
            "account_id": account_id,
        }).fetchone() is not None
        if exists:
            _rebuild_holding_aggregate(s, user_id, ticker)
        s.commit()
        return exists


def _rebuild_holding_aggregate(s, user_id: int, ticker: str) -> None:
    rows = s.execute(text("""
        SELECT * FROM holding_sources
        WHERE user_id = :uid AND ticker = :ticker AND quantity > 0 AND coalesce(excluded_from_portfolio, false) = false
    """), {"uid": user_id, "ticker": ticker}).mappings().all()
    if not rows:
        s.execute(text("DELETE FROM holdings WHERE user_id = :uid AND ticker = :ticker"), {"uid": user_id, "ticker": ticker})
        return

    quantity = sum(float(r["quantity"] or 0) for r in rows)
    total_cost = sum(float(r["quantity"] or 0) * float(r["avg_price"] or 0) for r in rows)
    avg_price = total_cost / quantity if quantity else 0.0
    first = dict(rows[0])
    now = datetime.now()
    target = s.execute(text("""
        SELECT target_weight FROM holdings WHERE user_id = :uid AND ticker = :ticker
    """), {"uid": user_id, "ticker": ticker}).fetchone()
    target_weight = target[0] if target else None
    s.execute(text("""
        INSERT INTO holdings (user_id, ticker, name, currency, quantity, avg_price, sector, market, target_weight, updated_at)
        VALUES (:uid, :ticker, :name, :currency, :quantity, :avg_price, :sector, :market, :target_weight, :now)
        ON CONFLICT (user_id, ticker) DO UPDATE SET
            name = excluded.name,
            currency = excluded.currency,
            quantity = excluded.quantity,
            avg_price = excluded.avg_price,
            sector = excluded.sector,
            market = excluded.market,
            target_weight = excluded.target_weight,
            updated_at = :now
    """), {"uid": user_id, "ticker": ticker, "name": first["name"], "currency": first["currency"],
           "quantity": quantity, "avg_price": avg_price, "sector": first.get("sector"),
           "market": first.get("market"), "target_weight": target_weight, "now": now})


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


def get_cash_sources(user_id: int) -> list[dict]:
    sources = []
    for source in ("manual", "toss", "kis"):
        krw = get_meta(user_id, f"cash_krw_{source}")
        usd = get_meta(user_id, f"cash_usd_{source}")
        if krw is None and usd is None:
            continue
        sources.append({
            "source": source,
            "cash_krw": float(krw or 0),
            "cash_usd": float(usd or 0),
        })
    return sources


def get_cash_source(user_id: int, source: str) -> dict:
    krw = get_meta(user_id, f"cash_krw_{source}")
    usd = get_meta(user_id, f"cash_usd_{source}")
    if source == "manual" and krw is None and usd is None:
        has_source_cash = any(
            get_meta(user_id, f"cash_krw_{s}") is not None or get_meta(user_id, f"cash_usd_{s}") is not None
            for s in ("toss", "kis")
        )
        if not has_source_cash:
            krw = get_meta(user_id, "cash_krw")
            usd = get_meta(user_id, "cash_usd")
    return {"cash_krw": float(krw or 0), "cash_usd": float(usd or 0)}


def get_cash_total(user_id: int) -> dict:
    sources = get_cash_sources(user_id)
    if not sources:
        return {
            "cash_krw": float(get_meta(user_id, "cash_krw") or 0),
            "cash_usd": float(get_meta(user_id, "cash_usd") or 0),
        }
    return {
        "cash_krw": sum(s["cash_krw"] for s in sources),
        "cash_usd": sum(s["cash_usd"] for s in sources),
    }


def set_cash_source(user_id: int, source: str, cash_krw: float, cash_usd: float):
    set_meta(user_id, f"cash_krw_{source}", str(cash_krw))
    set_meta(user_id, f"cash_usd_{source}", str(cash_usd))
    total = get_cash_total(user_id)
    set_meta(user_id, "cash_krw", str(total["cash_krw"]))
    set_meta(user_id, "cash_usd", str(total["cash_usd"]))


# ── Job Runs ─────────────────────────────────────────────────────────────────

def start_job_run(job_id: str, trigger_type: str) -> tuple[int, bool]:
    now = datetime.now()
    with session() as s:
        running = s.execute(text("""
            SELECT id FROM job_runs
            WHERE job_id = :job_id AND status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
        """), {"job_id": job_id}).fetchone()
        if running:
            row = s.execute(text("""
                INSERT INTO job_runs
                  (job_id, status, trigger_type, started_at, finished_at, duration_ms, message)
                VALUES (:job_id, 'skipped', :trigger_type, :now, :now, 0, :message)
                RETURNING id
            """), {
                "job_id": job_id,
                "trigger_type": trigger_type,
                "now": now,
                "message": "이미 실행 중인 작업이 있어 건너뜀",
            }).fetchone()
            s.commit()
            return int(row[0]), False

        row = s.execute(text("""
            INSERT INTO job_runs (job_id, status, trigger_type, started_at)
            VALUES (:job_id, 'running', :trigger_type, :now)
            RETURNING id
        """), {"job_id": job_id, "trigger_type": trigger_type, "now": now}).fetchone()
        s.commit()
        return int(row[0]), True


def finish_job_run(
    run_id: int,
    status: str,
    *,
    message: str | None = None,
    error: str | None = None,
    meta: dict | None = None,
) -> None:
    finished_at = datetime.now()
    with session() as s:
        started = s.execute(
            text("SELECT started_at FROM job_runs WHERE id = :id"),
            {"id": run_id},
        ).fetchone()
        started_at = started[0] if started else finished_at
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        s.execute(text("""
            UPDATE job_runs
            SET status = :status,
                finished_at = :finished_at,
                duration_ms = :duration_ms,
                message = :message,
                error = :error,
                meta_json = :meta_json
            WHERE id = :id
        """), {
            "id": run_id,
            "status": status,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "message": message,
            "error": error,
            "meta_json": json.dumps(meta or {}, ensure_ascii=False),
        })
        s.commit()


def get_latest_job_runs() -> dict[str, dict]:
    with session() as s:
        rows = s.execute(text("""
            SELECT *
            FROM (
                SELECT *, row_number() OVER (PARTITION BY job_id ORDER BY started_at DESC) AS rn
                FROM job_runs
            )
            WHERE rn = 1
        """)).mappings().all()
        return {row["job_id"]: _job_run_row(row) for row in rows}


def list_job_runs(job_id: str | None = None, limit: int = 50) -> list[dict]:
    sql = """
        SELECT * FROM job_runs
        {where}
        ORDER BY started_at DESC
        LIMIT :limit
    """
    params: dict[str, object] = {"limit": limit}
    where = ""
    if job_id:
        where = "WHERE job_id = :job_id"
        params["job_id"] = job_id
    with session() as s:
        rows = s.execute(text(sql.format(where=where)), params).mappings().all()
        return [_job_run_row(row) for row in rows]


def _job_run_row(row) -> dict:
    out = dict(row)
    out.pop("rn", None)
    raw = out.get("meta_json")
    if isinstance(raw, str) and raw:
        try:
            out["meta_json"] = json.loads(raw)
        except Exception:
            out["meta_json"] = {}
    elif raw is None:
        out["meta_json"] = {}
    return out


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


SNAPSHOT_BUCKETS = ("10m", "1h", "1d", "1w", "1mo")


def _snapshot_bucket_ts(ts: datetime, bucket: str) -> datetime:
    if bucket == "10m":
        return ts.replace(minute=(ts.minute // 10) * 10, second=0, microsecond=0)
    if bucket == "1h":
        return ts.replace(minute=0, second=0, microsecond=0)
    if bucket == "1d":
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    if bucket == "1w":
        start = ts - timedelta(days=ts.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    if bucket == "1mo":
        return ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"unsupported snapshot bucket: {bucket}")


def refresh_snapshot_rollups(user_id: int | None = None, buckets: tuple[str, ...] = SNAPSHOT_BUCKETS) -> dict:
    for bucket in buckets:
        if bucket not in SNAPSHOT_BUCKETS:
            raise ValueError(f"unsupported snapshot bucket: {bucket}")

    with session() as s:
        if user_id is None:
            rows = s.execute(text("""
                SELECT user_id, ts, total_equity_krw, total_with_cash_krw, cash_krw,
                       total_equity_usd, total_with_cash_usd, cash_usd, usdkrw
                FROM portfolio_snapshots
                ORDER BY user_id, ts
            """)).mappings().all()
        else:
            rows = s.execute(text("""
                SELECT user_id, ts, total_equity_krw, total_with_cash_krw, cash_krw,
                       total_equity_usd, total_with_cash_usd, cash_usd, usdkrw
                FROM portfolio_snapshots
                WHERE user_id = :uid
                ORDER BY user_id, ts
            """), {"uid": user_id}).mappings().all()

        latest: dict[tuple[int, str, datetime], dict] = {}
        for row in rows:
            for bucket in buckets:
                key = (int(row["user_id"]), bucket, _snapshot_bucket_ts(row["ts"], bucket))
                latest[key] = dict(row)

        for (uid, bucket, bucket_ts), row in latest.items():
            s.execute(text("""
                INSERT INTO portfolio_snapshot_rollups
                  (user_id, bucket, ts, total_equity_krw, total_with_cash_krw, cash_krw,
                   total_equity_usd, total_with_cash_usd, cash_usd, usdkrw)
                VALUES
                  (:uid, :bucket, :ts, :total_equity_krw, :total_with_cash_krw, :cash_krw,
                   :total_equity_usd, :total_with_cash_usd, :cash_usd, :usdkrw)
                ON CONFLICT (user_id, bucket, ts) DO UPDATE SET
                  total_equity_krw = excluded.total_equity_krw,
                  total_with_cash_krw = excluded.total_with_cash_krw,
                  cash_krw = excluded.cash_krw,
                  total_equity_usd = excluded.total_equity_usd,
                  total_with_cash_usd = excluded.total_with_cash_usd,
                  cash_usd = excluded.cash_usd,
                  usdkrw = excluded.usdkrw
            """), {
                "uid": uid,
                "bucket": bucket,
                "ts": bucket_ts,
                "total_equity_krw": row["total_equity_krw"],
                "total_with_cash_krw": row["total_with_cash_krw"],
                "cash_krw": row.get("cash_krw") or 0,
                "total_equity_usd": row["total_equity_usd"],
                "total_with_cash_usd": row["total_with_cash_usd"],
                "cash_usd": row.get("cash_usd") or 0,
                "usdkrw": row.get("usdkrw") or 0,
            })
        s.commit()
        return {"buckets": list(buckets), "rows": len(latest)}


def get_snapshot_rollups(user_id: int, bucket: str = "10m", limit: int = 400) -> list[dict]:
    if bucket not in SNAPSHOT_BUCKETS:
        raise ValueError(f"unsupported snapshot bucket: {bucket}")
    with session() as s:
        rows = s.execute(text("""
            SELECT ts, total_equity_krw, total_with_cash_krw, cash_krw,
                   total_equity_usd, total_with_cash_usd, cash_usd, usdkrw
            FROM portfolio_snapshot_rollups
            WHERE user_id = :uid AND bucket = :bucket
            ORDER BY ts DESC LIMIT :limit
        """), {"uid": user_id, "bucket": bucket, "limit": limit}).mappings().all()
    if not rows:
        refresh_snapshot_rollups(user_id=user_id, buckets=(bucket,))
        with session() as s:
            rows = s.execute(text("""
                SELECT ts, total_equity_krw, total_with_cash_krw, cash_krw,
                       total_equity_usd, total_with_cash_usd, cash_usd, usdkrw
                FROM portfolio_snapshot_rollups
                WHERE user_id = :uid AND bucket = :bucket
                ORDER BY ts DESC LIMIT :limit
            """), {"uid": user_id, "bucket": bucket, "limit": limit}).mappings().all()
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


# ── Common Ticker Data (공유) ─────────────────────────────────────────────────

def upsert_ticker_profile(row: dict) -> None:
    row = normalize_finite_numbers({
        "ticker": row["ticker"].upper(),
        "name": row.get("name"),
        "market": row.get("market"),
        "country": row.get("country"),
        "currency": row.get("currency"),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "exchange": row.get("exchange"),
        "source": row.get("source"),
        "updated_at": datetime.now(),
    })
    with session() as s:
        s.execute(text("""
            INSERT INTO ticker_profiles
                (ticker, name, market, country, currency, sector, industry, exchange, source, updated_at)
            VALUES
                (:ticker, :name, :market, :country, :currency, :sector, :industry, :exchange, :source, :updated_at)
            ON CONFLICT (ticker) DO UPDATE SET
                name = excluded.name,
                market = excluded.market,
                country = excluded.country,
                currency = excluded.currency,
                sector = excluded.sector,
                industry = excluded.industry,
                exchange = excluded.exchange,
                source = excluded.source,
                updated_at = excluded.updated_at
        """), row)
        s.commit()


def get_ticker_profile(ticker: str) -> dict | None:
    with session() as s:
        row = s.execute(text("""
            SELECT ticker, name, market, country, currency, sector, industry, exchange, source, updated_at
            FROM ticker_profiles
            WHERE ticker = :ticker
        """), {"ticker": ticker.upper()}).mappings().fetchone()
    return dict(row) if row else None


_FUNDAMENTAL_SNAPSHOT_DEFAULTS = {
    "per": None,
    "pbr": None,
    "psr": None,
    "peg": None,
    "forward_pe": None,
    "trailing_pe": None,
    "forward_eps": None,
    "eps_ttm": None,
    "roe": None,
    "roic": None,
    "debt_ratio": None,
    "current_ratio": None,
    "gross_margin": None,
    "operating_margin": None,
    "revenue_growth": None,
    "eps_growth": None,
    "market_cap": None,
    "raw_json": {},
}


def upsert_fundamental_snapshot(row: dict) -> None:
    row = normalize_finite_numbers({
        **_FUNDAMENTAL_SNAPSHOT_DEFAULTS,
        **row,
        "ticker": row["ticker"].upper(),
        "raw_json": json.dumps(row.get("raw_json") or {}),
        "fetched_at": datetime.now(),
    })
    with session() as s:
        s.execute(text("""
            INSERT INTO fundamental_snapshots
                (ticker, as_of, source, per, pbr, psr, peg, forward_pe, trailing_pe,
                 forward_eps, eps_ttm, roe, roic, debt_ratio, current_ratio, gross_margin,
                 operating_margin, revenue_growth, eps_growth, market_cap, raw_json, fetched_at)
            VALUES
                (:ticker, :as_of, :source, :per, :pbr, :psr, :peg, :forward_pe, :trailing_pe,
                 :forward_eps, :eps_ttm, :roe, :roic, :debt_ratio, :current_ratio, :gross_margin,
                 :operating_margin, :revenue_growth, :eps_growth, :market_cap, :raw_json, :fetched_at)
            ON CONFLICT (ticker, as_of, source) DO UPDATE SET
                per = excluded.per,
                pbr = excluded.pbr,
                psr = excluded.psr,
                peg = excluded.peg,
                forward_pe = excluded.forward_pe,
                trailing_pe = excluded.trailing_pe,
                forward_eps = excluded.forward_eps,
                eps_ttm = excluded.eps_ttm,
                roe = excluded.roe,
                roic = excluded.roic,
                debt_ratio = excluded.debt_ratio,
                current_ratio = excluded.current_ratio,
                gross_margin = excluded.gross_margin,
                operating_margin = excluded.operating_margin,
                revenue_growth = excluded.revenue_growth,
                eps_growth = excluded.eps_growth,
                market_cap = excluded.market_cap,
                raw_json = excluded.raw_json,
                fetched_at = excluded.fetched_at
        """), row)
        s.commit()


def get_latest_fundamental_snapshot(ticker: str) -> dict | None:
    with session() as s:
        row = s.execute(text("""
            SELECT *
            FROM fundamental_snapshots
            WHERE ticker = :ticker
            ORDER BY as_of DESC, fetched_at DESC
            LIMIT 1
        """), {"ticker": ticker.upper()}).mappings().fetchone()
    if not row:
        return None
    result = dict(row)
    raw = result.get("raw_json")
    if isinstance(raw, str):
        result["raw_json"] = json.loads(raw)
    return result


def upsert_price_target_consensus_snapshot(ticker: str, result: dict, as_of: date | None = None) -> None:
    row = normalize_finite_numbers({
        "ticker": ticker.upper(),
        "as_of": as_of or date.today(),
        "source": result.get("consensus_source") or "UNKNOWN",
        "consensus_status": result.get("consensus_status"),
        "consensus_message": result.get("consensus_message"),
        "current_price": result.get("current_price"),
        "target_mean": result.get("target_mean"),
        "target_median": result.get("target_median"),
        "target_low": result.get("target_low"),
        "target_high": result.get("target_high"),
        "upside_pct": result.get("upside_pct"),
        "analyst_count": result.get("analyst_count"),
        "consensus_as_of": result.get("consensus_as_of"),
        "fallback_used": bool(result.get("fallback_used")),
        "attempts_json": json.dumps(result.get("consensus_attempts") or []),
        "fetched_at": datetime.now(),
    })
    with session() as s:
        s.execute(text("""
            INSERT INTO price_target_consensus_snapshots
                (ticker, as_of, source, consensus_status, consensus_message,
                 current_price, target_mean, target_median, target_low, target_high,
                 upside_pct, analyst_count, consensus_as_of, fallback_used, attempts_json, fetched_at)
            VALUES
                (:ticker, :as_of, :source, :consensus_status, :consensus_message,
                 :current_price, :target_mean, :target_median, :target_low, :target_high,
                 :upside_pct, :analyst_count, :consensus_as_of, :fallback_used, :attempts_json, :fetched_at)
            ON CONFLICT (ticker, as_of, source) DO UPDATE SET
                consensus_status = excluded.consensus_status,
                consensus_message = excluded.consensus_message,
                current_price = excluded.current_price,
                target_mean = excluded.target_mean,
                target_median = excluded.target_median,
                target_low = excluded.target_low,
                target_high = excluded.target_high,
                upside_pct = excluded.upside_pct,
                analyst_count = excluded.analyst_count,
                consensus_as_of = excluded.consensus_as_of,
                fallback_used = excluded.fallback_used,
                attempts_json = excluded.attempts_json,
                fetched_at = excluded.fetched_at
        """), row)
        s.commit()


def get_latest_price_target_consensus_snapshot(ticker: str) -> dict | None:
    with session() as s:
        row = s.execute(text("""
            SELECT *
            FROM price_target_consensus_snapshots
            WHERE ticker = :ticker
            ORDER BY as_of DESC, fetched_at DESC
            LIMIT 1
        """), {"ticker": ticker.upper()}).mappings().fetchone()
    if not row:
        return None
    result = dict(row)
    attempts = result.pop("attempts_json", "[]")
    if isinstance(attempts, str):
        result["consensus_attempts"] = json.loads(attempts)
    else:
        result["consensus_attempts"] = attempts or []
    result["consensus_source"] = result.pop("source")
    return result


def list_fundamental_hydration_tickers() -> list[str]:
    """관심종목/보유종목에서 미국/해외 펀더멘털 수집 후보 티커를 반환."""
    with session() as s:
        rows = s.execute(text("""
            SELECT DISTINCT upper(ticker) AS ticker
            FROM (
                SELECT ticker
                FROM watchlist_items
                UNION ALL
                SELECT ticker
                FROM growth_watchlist
                UNION ALL
                SELECT ticker
                FROM holdings
                WHERE quantity > 0
            )
            WHERE ticker IS NOT NULL AND ticker != ''
            ORDER BY ticker
        """)).fetchall()
        return [row[0] for row in rows]


def list_price_target_consensus_hydration_tickers() -> list[str]:
    """관심종목/보유종목에서 목표주가 consensus 수집 후보 티커를 반환."""
    return list_fundamental_hydration_tickers()


def upsert_ticker_data_status(row: dict) -> None:
    row = normalize_finite_numbers({
        "ticker": row["ticker"].upper(),
        "data_type": row["data_type"],
        "source": row["source"],
        "min_date": row.get("min_date"),
        "max_date": row.get("max_date"),
        "last_fetched_at": row.get("last_fetched_at"),
        "last_success_at": row.get("last_success_at"),
        "last_error": row.get("last_error"),
        "coverage_json": json.dumps(row.get("coverage_json") or {}),
    })
    with session() as s:
        s.execute(text("""
            INSERT INTO ticker_data_status
                (ticker, data_type, source, min_date, max_date, last_fetched_at,
                 last_success_at, last_error, coverage_json)
            VALUES
                (:ticker, :data_type, :source, :min_date, :max_date, :last_fetched_at,
                 :last_success_at, :last_error, :coverage_json)
            ON CONFLICT (ticker, data_type, source) DO UPDATE SET
                min_date = excluded.min_date,
                max_date = excluded.max_date,
                last_fetched_at = excluded.last_fetched_at,
                last_success_at = excluded.last_success_at,
                last_error = excluded.last_error,
                coverage_json = excluded.coverage_json
        """), row)
        s.commit()


def get_ticker_data_status(ticker: str) -> list[dict]:
    with session() as s:
        rows = s.execute(text("""
            SELECT *
            FROM ticker_data_status
            WHERE ticker = :ticker
            ORDER BY data_type, source
        """), {"ticker": ticker.upper()}).mappings().fetchall()
    result = []
    for row in rows:
        item = dict(row)
        raw = item.get("coverage_json")
        if isinstance(raw, str):
            item["coverage_json"] = json.loads(raw)
        result.append(item)
    return result


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

_QUANT_GROWTH_DEFAULTS = {
    "pct_growth": None,
    "pct_profitability": None,
    "pct_cashflow": None,
    "pct_stability": None,
    "growth_composite": None,
    "raw_roic": None,
    "raw_gross_margin": None,
    "raw_oper_margin": None,
    "raw_current_ratio": None,
    "raw_sales_growth": None,
    "raw_rev_yoy": None,
    "raw_market_cap_usd_m": None,
    "raw_market_cap_krw": None,
    "raw_fwd_rev_growth": None,
    "raw_fwd_eps_growth": None,
    "raw_operating_cashflow": None,
    "data_coverage": None,
    "sector_percentile_fallback": False,
}


def upsert_quant_scores(rows: list[dict]) -> None:
    if not rows:
        return
    with session() as s:
        for r in rows:
            r = normalize_finite_numbers({**_QUANT_GROWTH_DEFAULTS, **r})
            if isinstance(r["data_coverage"], (dict, list)):
                r["data_coverage"] = json.dumps(r["data_coverage"])
            s.execute(text("""
                INSERT INTO quant_scores
                    (ticker, universe, as_of,
                     pct_momentum, pct_valuation, pct_eps_momentum, pct_quality, pct_technical,
                     raw_momentum, raw_fwd_pe, raw_pbr, raw_psr, raw_trailing_pe,
                     raw_eps_ttm, raw_fwd_eps, raw_roe, raw_debt_ratio, raw_rsi,
                     above_ma200, cfo_positive, company_name,
                     raw_ev_ebitda, raw_peg, raw_fcf_yield, raw_eps_momentum,
                     negative_book_value, sector, industry,
                     pct_growth, pct_profitability, pct_cashflow, pct_stability,
                     growth_composite, raw_roic, raw_gross_margin, raw_oper_margin,
                     raw_current_ratio, raw_sales_growth, raw_rev_yoy,
                     raw_market_cap_usd_m, raw_market_cap_krw, raw_fwd_rev_growth,
                     raw_fwd_eps_growth, raw_operating_cashflow, data_coverage,
                     sector_percentile_fallback)
                VALUES
                    (:ticker, :universe, :as_of,
                     :pct_momentum, :pct_valuation, :pct_eps_momentum, :pct_quality, :pct_technical,
                     :raw_momentum, :raw_fwd_pe, :raw_pbr, :raw_psr, :raw_trailing_pe,
                     :raw_eps_ttm, :raw_fwd_eps, :raw_roe, :raw_debt_ratio, :raw_rsi,
                     :above_ma200, :cfo_positive, :company_name,
                     :raw_ev_ebitda, :raw_peg, :raw_fcf_yield, :raw_eps_momentum,
                     :negative_book_value, :sector, :industry,
                     :pct_growth, :pct_profitability, :pct_cashflow, :pct_stability,
                     :growth_composite, :raw_roic, :raw_gross_margin, :raw_oper_margin,
                     :raw_current_ratio, :raw_sales_growth, :raw_rev_yoy,
                     :raw_market_cap_usd_m, :raw_market_cap_krw, :raw_fwd_rev_growth,
                     :raw_fwd_eps_growth, :raw_operating_cashflow, :data_coverage,
                     :sector_percentile_fallback)
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
                    company_name = excluded.company_name,
                    raw_ev_ebitda = excluded.raw_ev_ebitda,
                    raw_peg = excluded.raw_peg,
                    raw_fcf_yield = excluded.raw_fcf_yield,
                    raw_eps_momentum = excluded.raw_eps_momentum,
                    negative_book_value = excluded.negative_book_value,
                    sector = excluded.sector,
                    industry = excluded.industry,
                    pct_growth = excluded.pct_growth,
                    pct_profitability = excluded.pct_profitability,
                    pct_cashflow = excluded.pct_cashflow,
                    pct_stability = excluded.pct_stability,
                    growth_composite = excluded.growth_composite,
                    raw_roic = excluded.raw_roic,
                    raw_gross_margin = excluded.raw_gross_margin,
                    raw_oper_margin = excluded.raw_oper_margin,
                    raw_current_ratio = excluded.raw_current_ratio,
                    raw_sales_growth = excluded.raw_sales_growth,
                    raw_rev_yoy = excluded.raw_rev_yoy,
                    raw_market_cap_usd_m = excluded.raw_market_cap_usd_m,
                    raw_market_cap_krw = excluded.raw_market_cap_krw,
                    raw_fwd_rev_growth = excluded.raw_fwd_rev_growth,
                    raw_fwd_eps_growth = excluded.raw_fwd_eps_growth,
                    raw_operating_cashflow = excluded.raw_operating_cashflow,
                    data_coverage = excluded.data_coverage,
                    sector_percentile_fallback = excluded.sector_percentile_fallback
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


def get_latest_quant_as_of(universe: str) -> date | None:
    with session() as s:
        return s.execute(text("""
            SELECT MAX(as_of) FROM quant_scores WHERE universe = :universe
        """), {"universe": universe}).scalar()


def get_quant_ticker(ticker: str, universe: str) -> dict | None:
    with session() as s:
        row = s.execute(text("""
            SELECT * FROM quant_scores
            WHERE ticker = :ticker AND universe = :universe
              AND as_of = (SELECT MAX(as_of) FROM quant_scores WHERE universe = :universe)
        """), {"ticker": ticker, "universe": universe}).mappings().fetchone()
        return dict(row) if row else None


# ── Growth Watchlist (사용자별) ────────────────────────────────────────────────

def add_growth_watchlist_item(user_id: int, universe: str, ticker: str) -> None:
    with session() as s:
        s.execute(text("""
            INSERT OR IGNORE INTO growth_watchlist (user_id, universe, ticker, created_at)
            VALUES (:uid, :universe, :ticker, current_timestamp)
        """), {"uid": user_id, "universe": universe, "ticker": ticker})
        s.commit()


def remove_growth_watchlist_item(user_id: int, universe: str, ticker: str) -> None:
    with session() as s:
        s.execute(text("""
            DELETE FROM growth_watchlist
            WHERE user_id = :uid AND universe = :universe AND ticker = :ticker
        """), {"uid": user_id, "universe": universe, "ticker": ticker})
        s.commit()


def is_growth_watchlist_item(user_id: int, universe: str, ticker: str) -> bool:
    with session() as s:
        row = s.execute(text("""
            SELECT 1 FROM growth_watchlist
            WHERE user_id = :uid AND universe = :universe AND ticker = :ticker
        """), {"uid": user_id, "universe": universe, "ticker": ticker}).fetchone()
        return row is not None


def get_growth_watchlist_tickers(user_id: int, universe: str) -> list[str]:
    with session() as s:
        rows = s.execute(text("""
            SELECT ticker FROM growth_watchlist
            WHERE user_id = :uid AND universe = :universe
            ORDER BY created_at DESC, ticker
        """), {"uid": user_id, "universe": universe}).fetchall()
        return [row[0] for row in rows]


# ── Watchlists (사용자별) ─────────────────────────────────────────────────────

def ensure_default_watchlist(user_id: int) -> int:
    with session() as s:
        row = s.execute(text("""
            SELECT id FROM watchlists
            WHERE user_id = :uid
            ORDER BY id
            LIMIT 1
        """), {"uid": user_id}).fetchone()
        if row:
            return row[0]
        new_id = s.execute(text("SELECT nextval('watchlists_id_seq')")).fetchone()[0]
        s.execute(text("""
            INSERT INTO watchlists (id, user_id, name, description, created_at, updated_at)
            VALUES (:id, :uid, '기본 Watchlist', NULL, current_timestamp, current_timestamp)
        """), {"id": new_id, "uid": user_id})
        s.commit()
        return new_id


def create_watchlist(user_id: int, name: str, description: str | None = None) -> dict:
    with session() as s:
        new_id = s.execute(text("SELECT nextval('watchlists_id_seq')")).fetchone()[0]
        s.execute(text("""
            INSERT INTO watchlists (id, user_id, name, description, created_at, updated_at)
            VALUES (:id, :uid, :name, :description, current_timestamp, current_timestamp)
        """), {"id": new_id, "uid": user_id, "name": name, "description": description})
        s.commit()
    return get_watchlist(user_id, new_id)


def list_watchlists(user_id: int) -> list[dict]:
    ensure_default_watchlist(user_id)
    with session() as s:
        rows = s.execute(text("""
            SELECT w.*, COUNT(i.ticker) AS item_count
            FROM watchlists w
            LEFT JOIN watchlist_items i ON i.watchlist_id = w.id
            WHERE w.user_id = :uid
            GROUP BY w.id, w.user_id, w.name, w.description, w.created_at, w.updated_at
            ORDER BY w.id
        """), {"uid": user_id}).mappings().all()
        return [dict(row) for row in rows]


def get_watchlist(user_id: int, watchlist_id: int) -> dict | None:
    with session() as s:
        row = s.execute(text("""
            SELECT w.*, COUNT(i.ticker) AS item_count
            FROM watchlists w
            LEFT JOIN watchlist_items i ON i.watchlist_id = w.id
            WHERE w.user_id = :uid AND w.id = :id
            GROUP BY w.id, w.user_id, w.name, w.description, w.created_at, w.updated_at
        """), {"uid": user_id, "id": watchlist_id}).mappings().fetchone()
        return dict(row) if row else None


def update_watchlist(user_id: int, watchlist_id: int, name: str, description: str | None = None) -> dict | None:
    with session() as s:
        s.execute(text("""
            UPDATE watchlists
            SET name = :name, description = :description, updated_at = current_timestamp
            WHERE user_id = :uid AND id = :id
        """), {"uid": user_id, "id": watchlist_id, "name": name, "description": description})
        s.commit()
    return get_watchlist(user_id, watchlist_id)


def delete_watchlist(user_id: int, watchlist_id: int) -> None:
    with session() as s:
        s.execute(text("""
            DELETE FROM watchlist_items
            WHERE watchlist_id IN (SELECT id FROM watchlists WHERE user_id = :uid AND id = :id)
        """), {"uid": user_id, "id": watchlist_id})
        s.execute(text("DELETE FROM watchlists WHERE user_id = :uid AND id = :id"), {"uid": user_id, "id": watchlist_id})
        s.commit()


def upsert_watchlist_item(
    user_id: int,
    watchlist_id: int,
    ticker: str,
    universe: str,
    name: str | None = None,
    memo: str | None = None,
    timing_alert_enabled: bool | None = None,
) -> None:
    with session() as s:
        exists = s.execute(text("""
            SELECT 1 FROM watchlists WHERE user_id = :uid AND id = :id
        """), {"uid": user_id, "id": watchlist_id}).fetchone()
        if not exists:
            raise ValueError("watchlist not found")
        s.execute(text("""
            INSERT INTO watchlist_items (
                watchlist_id, ticker, universe, name, memo, timing_alert_enabled, created_at
            )
            VALUES (
                :watchlist_id,
                :ticker,
                :universe,
                :name,
                :memo,
                CASE WHEN :timing_alert_provided THEN :timing_alert_enabled ELSE FALSE END,
                current_timestamp
            )
            ON CONFLICT (watchlist_id, ticker, universe) DO UPDATE SET
                name = excluded.name,
                memo = excluded.memo,
                timing_alert_enabled = CASE
                    WHEN :timing_alert_provided THEN excluded.timing_alert_enabled
                    ELSE watchlist_items.timing_alert_enabled
                END
        """), {
            "watchlist_id": watchlist_id,
            "ticker": ticker,
            "universe": universe,
            "name": name,
            "memo": memo,
            "timing_alert_provided": timing_alert_enabled is not None,
            "timing_alert_enabled": bool(timing_alert_enabled),
        })
        s.commit()


def remove_watchlist_item(user_id: int, watchlist_id: int, ticker: str, universe: str) -> None:
    with session() as s:
        s.execute(text("""
            DELETE FROM watchlist_items
            WHERE watchlist_id IN (SELECT id FROM watchlists WHERE user_id = :uid AND id = :id)
              AND ticker = :ticker AND universe = :universe
        """), {"uid": user_id, "id": watchlist_id, "ticker": ticker, "universe": universe})
        s.commit()


def list_watchlist_items(user_id: int, watchlist_id: int) -> list[dict]:
    with session() as s:
        rows = s.execute(text("""
            SELECT i.*
            FROM watchlist_items i
            JOIN watchlists w ON w.id = i.watchlist_id
            WHERE w.user_id = :uid AND w.id = :id
            ORDER BY i.created_at DESC, i.ticker
        """), {"uid": user_id, "id": watchlist_id}).mappings().all()
        return [dict(row) for row in rows]


def list_watchlist_memberships(user_id: int, ticker: str) -> list[dict]:
    ensure_default_watchlist(user_id)
    with session() as s:
        rows = s.execute(text("""
            SELECT
                w.id,
                w.name,
                w.description,
                COUNT(all_items.ticker) AS item_count,
                w.created_at,
                w.updated_at,
                i.universe,
                i.memo,
                COALESCE(i.timing_alert_enabled, FALSE) AS timing_alert_enabled
            FROM watchlists w
            JOIN watchlist_items i ON i.watchlist_id = w.id
            LEFT JOIN watchlist_items all_items ON all_items.watchlist_id = w.id
            WHERE w.user_id = :uid AND i.ticker = :ticker
            GROUP BY
                w.id, w.name, w.description, w.created_at, w.updated_at,
                i.universe, i.memo, i.timing_alert_enabled
            ORDER BY w.id
        """), {"uid": user_id, "ticker": ticker.upper()}).mappings().all()
        return [dict(row) for row in rows]


def list_timing_alert_watchlist_items() -> list[dict]:
    with session() as s:
        rows = s.execute(text("""
            SELECT
                w.user_id,
                w.id AS watchlist_id,
                w.name AS watchlist_name,
                i.ticker,
                i.universe,
                i.name,
                i.memo
            FROM watchlist_items i
            JOIN watchlists w ON w.id = i.watchlist_id
            WHERE COALESCE(i.timing_alert_enabled, FALSE)
            ORDER BY w.user_id, w.id, i.ticker
        """)).mappings().all()
        return [dict(row) for row in rows]


def upsert_rank_history(rows: list[dict]) -> None:
    if not rows:
        return
    with session() as s:
        s.execute(text("""
            INSERT INTO quant_rank_history (universe, as_of, ticker, growth_composite, rank)
            VALUES (:universe, :as_of, :ticker, :growth_composite, :rank)
            ON CONFLICT (universe, as_of, ticker) DO UPDATE SET
                growth_composite = excluded.growth_composite,
                rank = excluded.rank
        """), rows)
        s.commit()


def get_rank_deltas(universe: str, as_of: date) -> dict[str, dict]:
    """최신 랭킹과 5/21일 전 가장 가까운 스냅샷의 순위 차이."""
    current = _rank_rows(universe, as_of)
    one_week = _rank_rows_at_or_before(universe, as_of - timedelta(days=5))
    one_month = _rank_rows_at_or_before(universe, as_of - timedelta(days=21))
    return {
        ticker: {
            "rank": row["rank"],
            "rank_1w_ago": one_week.get(ticker),
            "rank_1m_ago": one_month.get(ticker),
            "delta_1w": one_week[ticker] - row["rank"] if ticker in one_week else None,
            "delta_1m": one_month[ticker] - row["rank"] if ticker in one_month else None,
        }
        for ticker, row in current.items()
    }


def _rank_rows(universe: str, as_of: date) -> dict[str, dict]:
    with session() as s:
        rows = s.execute(text("""
            SELECT ticker, rank
            FROM quant_rank_history
            WHERE universe = :universe AND as_of = :as_of
        """), {"universe": universe, "as_of": as_of}).mappings().all()
        return {r["ticker"]: dict(r) for r in rows}


def _rank_rows_at_or_before(universe: str, as_of: date) -> dict[str, int]:
    with session() as s:
        rows = s.execute(text("""
            SELECT ticker, rank
            FROM quant_rank_history
            WHERE universe = :universe
              AND as_of = (
                SELECT MAX(as_of) FROM quant_rank_history
                WHERE universe = :universe AND as_of <= :as_of
              )
        """), {"universe": universe, "as_of": as_of}).mappings().all()
        return {r["ticker"]: r["rank"] for r in rows}


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
    currency: str, traded_at: str, fee: float = 0, note: str | None = None,
    source: str = "manual", external_id: str | None = None, sync_holdings: bool = True,
) -> int:
    with session() as s:
        if external_id:
            existing = s.execute(text("""
                SELECT id FROM trades
                WHERE user_id = :uid AND source = :source AND external_id = :external_id
            """), {"uid": user_id, "source": source, "external_id": external_id}).fetchone()
            if existing:
                return int(existing[0])
        row = s.execute(text("SELECT nextval('trades_id_seq')")).fetchone()
        trade_id = row[0]
        s.execute(text("""
            INSERT INTO trades
              (id, user_id, source, external_id, ticker, market, trade_type, quantity, price, currency, traded_at, fee, note)
            VALUES
              (:id, :uid, :source, :external_id, :ticker, :market, :type, :qty, :price, :cur, :date, :fee, :note)
        """), {"id": trade_id, "uid": user_id, "source": source, "external_id": external_id, "ticker": ticker, "market": market,
               "type": trade_type, "qty": quantity, "price": price, "cur": currency,
               "date": traded_at, "fee": fee, "note": note})
        s.commit()
        if sync_holdings and source == "manual":
            _sync_holding_from_trades(s, user_id, ticker)
            s.commit()
    return trade_id


def get_trades(user_id: int, ticker: str | None = None) -> list[dict]:
    with session() as s:
        if ticker:
            rows = s.execute(text("""
                SELECT id, source, external_id, ticker, market, trade_type, quantity, price, currency,
                       traded_at, fee, note, created_at
                FROM trades WHERE user_id = :uid AND ticker = :ticker
                ORDER BY traded_at DESC, created_at DESC
            """), {"uid": user_id, "ticker": ticker}).fetchall()
        else:
            rows = s.execute(text("""
                SELECT id, source, external_id, ticker, market, trade_type, quantity, price, currency,
                       traded_at, fee, note, created_at
                FROM trades WHERE user_id = :uid
                ORDER BY traded_at DESC, created_at DESC
            """), {"uid": user_id}).fetchall()
    cols = ["id", "source", "external_id", "ticker", "market", "trade_type", "quantity", "price", "currency",
            "traded_at", "fee", "note", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


def delete_trade(user_id: int, trade_id: int) -> bool:
    with session() as s:
        row = s.execute(text(
            "SELECT ticker, source FROM trades WHERE id = :id AND user_id = :uid"
        ), {"id": trade_id, "uid": user_id}).fetchone()
        if not row:
            return False
        ticker = row[0]
        source = row[1] or "manual"
        if source != "manual":
            raise ValueError("동기화된 거래는 삭제할 수 없습니다.")
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
        WHERE user_id = :uid AND ticker = :ticker AND COALESCE(source, 'manual') = 'manual'
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
        s.execute(text("""
            DELETE FROM holding_sources
            WHERE user_id = :uid AND ticker = :ticker AND source = 'manual' AND account_id = ''
        """), {"uid": user_id, "ticker": ticker})
        _rebuild_holding_aggregate(s, user_id, ticker)
        return

    buy_qty = sum(qty for tt, qty, _ in rows if tt == "BUY")
    avg_price = total_cost / buy_qty if buy_qty > 0 else 0.0

    existing = s.execute(text("""
        SELECT name, currency, sector, market, excluded_from_portfolio
        FROM holding_sources
        WHERE user_id = :uid AND ticker = :ticker AND source = 'manual' AND account_id = ''
    """), {"uid": user_id, "ticker": ticker}).fetchone()
    if not existing:
        existing = s.execute(text("""
            SELECT name, currency, sector, market, false AS excluded_from_portfolio
            FROM holdings
            WHERE user_id = :uid AND ticker = :ticker
        """), {"uid": user_id, "ticker": ticker}).fetchone()

    name = existing[0] if existing else ticker
    currency = existing[1] if existing else "USD"
    sector = existing[2] if existing else None
    market = existing[3] if existing else None
    excluded = bool(existing[4]) if existing else False
    now = datetime.now()
    s.execute(text("""
        INSERT INTO holding_sources
          (user_id, source, account_id, ticker, name, currency, quantity, avg_price, sector, market, excluded_from_portfolio, updated_at)
        VALUES (:uid, 'manual', '', :ticker, :name, :currency, :qty, :avg, :sector, :market, :excluded, :now)
        ON CONFLICT (user_id, source, account_id, ticker) DO UPDATE SET
          name = excluded.name,
          currency = excluded.currency,
          quantity = excluded.quantity,
          avg_price = excluded.avg_price,
          sector = excluded.sector,
          market = excluded.market,
          excluded_from_portfolio = excluded.excluded_from_portfolio,
          updated_at = :now
    """), {
        "uid": user_id,
        "ticker": ticker,
        "name": name,
        "currency": currency,
        "qty": total_qty,
        "avg": avg_price,
        "sector": sector,
        "market": market,
        "excluded": excluded,
        "now": now,
    })
    _rebuild_holding_aggregate(s, user_id, ticker)


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


# ── Quarterly Financials ──────────────────────────────────────────────────────

def upsert_quarterly_financials(rows: list[dict]) -> None:
    """분기 재무 데이터 upsert. rows: [{"ticker", "period", "eps", "roe", "debt_ratio", "revenue", "op_income", "source"}]"""
    if not rows:
        return
    with session() as s:
        s.execute(text("""
            INSERT INTO quarterly_financials (ticker, period, eps, roe, debt_ratio, revenue, op_income, source)
            VALUES (:ticker, :period, :eps, :roe, :debt_ratio, :revenue, :op_income, :source)
            ON CONFLICT (ticker, period) DO UPDATE SET
                eps        = excluded.eps,
                roe        = excluded.roe,
                debt_ratio = excluded.debt_ratio,
                revenue    = excluded.revenue,
                op_income  = excluded.op_income,
                source     = excluded.source
        """), rows)
        s.commit()


def get_quarterly_financials(ticker: str, n: int = 8) -> list[dict]:
    """최신 n분기 데이터를 period 내림차순으로 반환."""
    with session() as s:
        rows = s.execute(text("""
            SELECT ticker, period, eps, roe, debt_ratio, revenue, op_income, source
            FROM quarterly_financials
            WHERE ticker = :ticker
            ORDER BY period DESC
            LIMIT :n
        """), {"ticker": ticker, "n": n}).mappings().all()
        return [dict(r) for r in rows]


def get_latest_quarterly_period(tickers: list[str]) -> dict[str, str]:
    """티커별 DB에 저장된 최신 period. 없는 티커는 결과에서 제외."""
    if not tickers:
        return {}
    ticker_set = set(tickers)
    with session() as s:
        rows = s.execute(text("""
            SELECT ticker, MAX(period) AS latest_period
            FROM quarterly_financials
            GROUP BY ticker
        """)).mappings().all()
        return {r["ticker"]: r["latest_period"] for r in rows if r["ticker"] in ticker_set}


def get_quarterly_bulk(tickers: list[str], n: int = 8) -> dict[str, list[dict]]:
    """복수 티커의 분기 데이터를 한 번의 쿼리로 일괄 반환. {ticker: [rows desc]}"""
    if not tickers:
        return {}
    ticker_set = set(tickers)
    result: dict[str, list[dict]] = {}
    with session() as s:
        rows = s.execute(text("""
            SELECT ticker, period, eps, roe, debt_ratio, revenue, op_income, source,
                   ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY period DESC) AS rn
            FROM quarterly_financials
            ORDER BY ticker, period DESC
        """)).mappings().all()
        for row in rows:
            if row["ticker"] not in ticker_set:
                continue
            if row["rn"] > n:
                continue
            d = {k: v for k, v in row.items() if k != "rn"}
            result.setdefault(d["ticker"], []).append(d)
    return result


# ── Golden Cross Events ───────────────────────────────────────────────────────

def _infer_golden_cross_group(market: str, ticker: str, group_name: str | None = None) -> str:
    if group_name:
        return group_name
    if market == "US":
        return "US"
    if ticker.endswith(".KQ"):
        return "KOSDAQ"
    return "KOSPI"


def insert_golden_cross(ticker: str, market: str, name: str | None, first_date: date, group_name: str | None = None) -> None:
    """신규 골든크로스 등록. 이미 있으면 무시 (INSERT OR IGNORE)."""
    with session() as s:
        s.execute(text("""
            INSERT OR IGNORE INTO golden_cross_events
              (ticker, market, group_name, name, first_detected_at, last_sent_at, day_count)
            VALUES (:t, :m, :g, :n, :fd, current_timestamp, 1)
        """), {"t": ticker, "m": market, "g": group_name, "n": name, "fd": str(first_date)})
        s.commit()


def get_active_golden_crosses(market: str) -> list[dict]:
    """시장별 활성 골든크로스 전체 조회."""
    with session() as s:
        rows = s.execute(text("""
            SELECT ticker, market, group_name, name, first_detected_at, last_sent_at, day_count,
                (CAST(last_sent_at AS DATE) = CURRENT_DATE) AS already_sent_today
            FROM golden_cross_events WHERE market = :m
        """), {"m": market}).fetchall()
        return [
            {"ticker": r[0], "market": r[1], "group_name": _infer_golden_cross_group(r[1], r[0], r[2]), "name": r[3],
             "first_detected_at": r[4], "last_sent_at": r[5], "day_count": r[6],
             "already_sent_today": bool(r[7])}
            for r in rows
        ]


def update_golden_cross(ticker: str, day_count: int) -> None:
    """day_count 업데이트 + last_sent_at 갱신."""
    with session() as s:
        s.execute(text("""
            UPDATE golden_cross_events
            SET day_count = :dc, last_sent_at = current_timestamp
            WHERE ticker = :t
        """), {"dc": day_count, "t": ticker})
        s.commit()


def delete_golden_cross(ticker: str) -> None:
    """골든크로스 종료 — 행 삭제."""
    with session() as s:
        s.execute(text("DELETE FROM golden_cross_events WHERE ticker = :t"), {"t": ticker})
        s.commit()


def insert_golden_cross_history(
    ticker: str,
    market: str,
    group_name: str | None,
    name: str | None,
    status: str,
    day_count: int | None = None,
    cross_start_date: date | None = None,
    close: float | None = None,
    ema5: float | None = None,
    ema20: float | None = None,
    ema60: float | None = None,
    reason: str | None = None,
) -> None:
    with session() as s:
        s.execute(text("""
            INSERT INTO golden_cross_history
              (ticker, market, group_name, name, status, day_count, cross_start_date,
               close, ema5, ema20, ema60, reason)
            VALUES
              (:ticker, :market, :group_name, :name, :status, :day_count, :cross_start_date,
               :close, :ema5, :ema20, :ema60, :reason)
        """), {
            "ticker": ticker,
            "market": market,
            "group_name": group_name,
            "name": name,
            "status": status,
            "day_count": day_count,
            "cross_start_date": str(cross_start_date) if cross_start_date else None,
            "close": close,
            "ema5": ema5,
            "ema20": ema20,
            "ema60": ema60,
            "reason": reason,
        })
        s.commit()


def list_golden_cross_history(market: str | None = None, group_name: str | None = None, limit: int = 200) -> list[dict]:
    clauses = []
    params: dict[str, Any] = {"limit": limit}
    if market:
        clauses.append("market = :market")
        params["market"] = market
    if group_name:
        clauses.append("group_name = :group_name")
        params["group_name"] = group_name
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with session() as s:
        rows = s.execute(text(f"""
            SELECT id, ticker, market, group_name, name, status, day_count, cross_start_date,
                   checked_at, close, ema5, ema20, ema60, reason
            FROM golden_cross_history
            {where}
            ORDER BY checked_at DESC, id DESC
            LIMIT :limit
        """), params).mappings().all()
        return [dict(r) for r in rows]


def get_company_names(tickers: list[str]) -> dict[str, str]:
    """티커 리스트 → {ticker: company_name} 매핑. screener_scores 최신 데이터 기준."""
    if not tickers:
        return {}
    placeholders = ",".join(f":t{i}" for i in range(len(tickers)))
    params = {f"t{i}": t for i, t in enumerate(tickers)}
    try:
        with session() as s:
            rows = s.execute(text(f"""
                SELECT ticker, company_name
                FROM quant_scores
                WHERE ticker IN ({placeholders})
                  AND company_name IS NOT NULL
                QUALIFY ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY as_of DESC) = 1
            """), params).fetchall()
            return {r[0]: r[1] for r in rows}
    except Exception:
        return {}
