"""분기 재무 데이터 기반 Quality/EPS 모멘텀 통합 테스트."""
import math
import pytest
import core.repository as repo


@pytest.fixture(autouse=True)
def seed_quarterly(fresh_db):
    repo.upsert_quarterly_financials([
        {"ticker": "005930.KS", "period": "2025Q1", "eps": 6993.0, "roe": 19.16, "debt_ratio": 30.15, "revenue": 1338734.0, "op_income": 572328.0, "source": "naver"},
        {"ticker": "005930.KS", "period": "2024Q4", "eps": 2864.0, "roe": 10.85, "debt_ratio": 29.94, "revenue": 938374.0,  "op_income": 200737.0, "source": "naver"},
        {"ticker": "005930.KS", "period": "2024Q3", "eps": 1783.0, "roe": 8.37,  "debt_ratio": 26.64, "revenue": 860617.0,  "op_income": 121661.0, "source": "naver"},
        {"ticker": "005930.KS", "period": "2024Q2", "eps": 733.0,  "roe": 7.95,  "debt_ratio": 26.36, "revenue": 745663.0,  "op_income": 46761.0,  "source": "naver"},
        {"ticker": "005930.KS", "period": "2024Q1", "eps": 1186.0, "roe": 9.24,  "debt_ratio": 26.99, "revenue": 791405.0,  "op_income": 66853.0,  "source": "naver"},
    ])


def test_get_quarterly_financials_order():
    rows = repo.get_quarterly_financials("005930.KS", n=3)
    assert len(rows) == 3
    assert rows[0]["period"] == "2025Q1"
    assert rows[1]["period"] == "2024Q4"
    assert rows[2]["period"] == "2024Q3"


def test_get_latest_quarterly_period():
    result = repo.get_latest_quarterly_period(["005930.KS", "UNKNOWN"])
    assert result["005930.KS"] == "2025Q1"
    assert "UNKNOWN" not in result


def test_quality_score_uses_quarterly_roe():
    from core.factors.quality import QualityFactor
    rows = repo.get_quarterly_financials("005930.KS", n=1)
    assert rows[0]["roe"] == 19.16
    score = QualityFactor.score(rows[0]["roe"], rows[0]["debt_ratio"])
    assert not math.isnan(score)
    assert score > 0


def test_yoy_eps_momentum():
    rows = repo.get_quarterly_financials("005930.KS", n=8)
    by_period = {r["period"]: r for r in rows}
    recent = by_period.get("2025Q1")
    yoy    = by_period.get("2024Q1")
    assert recent is not None and yoy is not None
    momentum = (recent["eps"] - yoy["eps"]) / abs(yoy["eps"])
    assert abs(momentum - (6993 - 1186) / 1186) < 0.001
