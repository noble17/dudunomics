"""tests/test_screener_api.py"""
from datetime import date
from unittest.mock import patch
import pytest


def test_quant_score_out_new_fields():
    from api.models import QuantScoreOut
    row = QuantScoreOut(
        ticker="DELL", universe="sp500", as_of=date.today(),
        raw_ev_ebitda=8.5, raw_peg=0.8, raw_fcf_yield=0.084,
        negative_book_value=True, raw_eps_momentum=0.15,
        sector="Technology", industry="Computer Hardware",
    )
    assert row.pbr_flag == "자본잠식형 우량주 가능성 (M&A·자사주매입 기업)"
    assert row.peg_undervalued is True
    assert row.eps_revision_up is True


def test_pbr_flag_none_for_normal():
    from api.models import QuantScoreOut
    row = QuantScoreOut(ticker="AAPL", universe="sp500", as_of=date.today(),
                        raw_pbr=35.0, negative_book_value=False)
    assert row.pbr_flag is None


def test_peg_undervalued_false_when_above_one():
    from api.models import QuantScoreOut
    row = QuantScoreOut(ticker="MSFT", universe="sp500", as_of=date.today(), raw_peg=2.5)
    assert row.peg_undervalued is False


def test_screener_refresh_rejects_duplicate_batch(client, monkeypatch):
    import core.batch_state as bs

    monkeypatch.setitem(bs._state, "sp500", {
        "status": "running",
        "step": "펀더멘탈 페치 중",
        "done": 10,
        "total": 503,
        "started_at": "2026-06-02T07:10:00",
        "finished_at": "",
        "error": "",
    })

    with patch("core.scoring.universe_scorer.run_batch") as run_batch:
        response = client.post("/api/screener/refresh?universe=sp500")

    assert response.status_code == 409
    run_batch.assert_not_called()
