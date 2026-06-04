"""tests/test_growth_repository.py — 성장주 rank history 저장/조회."""
from __future__ import annotations

from datetime import date

import core.repository as repo


def test_rank_deltas_use_old_rank_minus_current_rank(fresh_db):
    repo.upsert_rank_history([
        {"universe": "sp500", "as_of": date(2026, 5, 1), "ticker": "AAPL", "growth_composite": 70.0, "rank": 10},
        {"universe": "sp500", "as_of": date(2026, 5, 27), "ticker": "AAPL", "growth_composite": 80.0, "rank": 7},
        {"universe": "sp500", "as_of": date(2026, 6, 2), "ticker": "AAPL", "growth_composite": 90.0, "rank": 3},
    ])

    delta = repo.get_rank_deltas("sp500", date(2026, 6, 2))["AAPL"]

    assert delta["rank_1w_ago"] == 7
    assert delta["rank_1m_ago"] == 10
    assert delta["delta_1w"] == 4
    assert delta["delta_1m"] == 7


def test_rank_deltas_return_none_without_history(fresh_db):
    repo.upsert_rank_history([
        {"universe": "sp500", "as_of": date(2026, 6, 2), "ticker": "AAPL", "growth_composite": 90.0, "rank": 3},
    ])

    delta = repo.get_rank_deltas("sp500", date(2026, 6, 2))["AAPL"]

    assert delta["rank_1w_ago"] is None
    assert delta["delta_1m"] is None

