"""tests/test_fundamentals_enrichment.py — Task 1: 펀더멘털 데이터 보강 단위 테스트."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock


# ── 1. FundamentalsSnapshot 신규 필드 존재 확인 ──────────────────────────────

def test_fundamentals_snapshot_new_fields():
    from core.data.fundamentals_scraper import FundamentalsSnapshot
    snap = FundamentalsSnapshot(ticker="TEST")
    assert hasattr(snap, "roic")
    assert hasattr(snap, "gross_margin")
    assert hasattr(snap, "operating_margin")
    assert hasattr(snap, "current_ratio")
    assert hasattr(snap, "sales_qq")
    # 기본값은 모두 None
    assert snap.roic is None
    assert snap.gross_margin is None
    assert snap.operating_margin is None
    assert snap.current_ratio is None
    assert snap.sales_qq is None


def test_fundamentals_snapshot_new_fields_assignable():
    from core.data.fundamentals_scraper import FundamentalsSnapshot
    snap = FundamentalsSnapshot(
        ticker="TEST",
        roic=12.5,
        gross_margin=45.0,
        operating_margin=20.3,
        current_ratio=1.8,
        sales_qq=8.7,
    )
    assert snap.roic == pytest.approx(12.5)
    assert snap.gross_margin == pytest.approx(45.0)
    assert snap.operating_margin == pytest.approx(20.3)
    assert snap.current_ratio == pytest.approx(1.8)
    assert snap.sales_qq == pytest.approx(8.7)


def test_fundamentals_snapshot_json_serializable():
    """dataclasses.asdict → JSON 직렬화 깨지지 않아야 한다."""
    import dataclasses, json
    from core.data.fundamentals_scraper import FundamentalsSnapshot
    snap = FundamentalsSnapshot(ticker="TEST", roic=10.0, gross_margin=None)
    d = dataclasses.asdict(snap)
    payload = json.dumps(d)
    assert '"roic": 10.0' in payload
    assert '"gross_margin": null' in payload


def test_fetch_finviz_parses_new_fields(monkeypatch):
    """_fetch_finviz가 ROI/Gross Margin/Oper. Margin/Curr R./Sales Q/Q를 파싱한다."""
    from core.data.fundamentals_scraper import _fetch_finviz

    html = """
    <table class="snapshot-table2">
      <tr>
        <td>P/E</td><td>20.0</td>
        <td>ROI</td><td>15.3%</td>
        <td>Gross Margin</td><td>62.1%</td>
        <td>Oper. Margin</td><td>28.5%</td>
        <td>Curr R.</td><td>2.1</td>
        <td>Sales Q/Q</td><td>12.4%</td>
        <td>Market Cap</td><td>2.5T</td>
      </tr>
    </table>
    """

    class FakeResponse:
        text = html
        def raise_for_status(self): pass

    monkeypatch.setattr(
        "core.data.fundamentals_scraper._CLIENT",
        type("C", (), {"get": lambda self, u: FakeResponse()})()
    )

    snap = _fetch_finviz("AAPL")
    assert snap.roic == pytest.approx(15.3)
    assert snap.gross_margin == pytest.approx(62.1)
    assert snap.operating_margin == pytest.approx(28.5)
    assert snap.current_ratio == pytest.approx(2.1)
    assert snap.sales_qq == pytest.approx(12.4)


# ── 2. compute_consensus_growth CAGR 계산 ────────────────────────────────────

def _make_sa_data(rev_base: float, rev_target: float, eps_base: float, eps_target: float,
                  base_year: str = "2024", target_year: str = "2027") -> dict:
    """테스트용 fetch_annual_financials 반환값 생성."""
    years_gap = int(target_year) - int(base_year)
    return {
        "revenue": [
            {"year": "2022", "period_end": "2022", "value": rev_base * 0.8, "is_estimate": False},
            {"year": base_year, "period_end": base_year, "value": rev_base, "is_estimate": False},
            {"year": target_year, "period_end": target_year, "value": rev_target, "is_estimate": True},
        ],
        "eps": [
            {"year": base_year, "period_end": base_year, "value": eps_base, "is_estimate": False},
            {"year": target_year, "period_end": target_year, "value": eps_target, "is_estimate": True},
        ],
        "roe": [],
        "latest_report_date": None,
    }


def test_compute_consensus_growth_basic():
    """정상 케이스: 3년 CAGR 계산."""
    from core.data import stockanalysis_financials as sa

    data = _make_sa_data(rev_base=400_000.0, rev_target=520_000.0,
                         eps_base=6.0, eps_target=9.0,
                         base_year="2024", target_year="2027")

    with patch.object(sa, "fetch_annual_financials", return_value=data):
        result = sa.compute_consensus_growth("AAPL")

    expected_rev = (520_000 / 400_000) ** (1 / 3) - 1
    expected_eps = (9.0 / 6.0) ** (1 / 3) - 1
    assert result["rev_fwd_cagr"] == pytest.approx(expected_rev, rel=1e-4)
    assert result["eps_fwd_cagr"] == pytest.approx(expected_eps, rel=1e-4)
    assert result["fwd_years"] == 3


def test_compute_consensus_growth_no_estimates():
    """예상치가 없으면 None 반환."""
    from core.data import stockanalysis_financials as sa

    data = {
        "revenue": [
            {"year": "2024", "period_end": "2024", "value": 400_000.0, "is_estimate": False},
        ],
        "eps": [],
        "roe": [],
        "latest_report_date": None,
    }

    with patch.object(sa, "fetch_annual_financials", return_value=data):
        result = sa.compute_consensus_growth("AAPL")

    assert result["rev_fwd_cagr"] is None
    assert result["eps_fwd_cagr"] is None


def test_compute_consensus_growth_negative_base():
    """base 값이 0 이하이면 CAGR = None."""
    from core.data import stockanalysis_financials as sa

    data = {
        "revenue": [
            {"year": "2024", "period_end": "2024", "value": -100.0, "is_estimate": False},
            {"year": "2026", "period_end": "2026", "value": 200.0, "is_estimate": True},
        ],
        "eps": [],
        "roe": [],
        "latest_report_date": None,
    }

    with patch.object(sa, "fetch_annual_financials", return_value=data):
        result = sa.compute_consensus_growth("XYZ")

    assert result["rev_fwd_cagr"] is None


def test_compute_consensus_growth_none_data():
    """fetch_annual_financials가 None 반환 시 모두 None."""
    from core.data import stockanalysis_financials as sa

    with patch.object(sa, "fetch_annual_financials", return_value=None):
        result = sa.compute_consensus_growth("NONE")

    assert result["rev_fwd_cagr"] is None
    assert result["eps_fwd_cagr"] is None


def test_compute_consensus_growth_zero_years():
    """base_year == target_year이면 CAGR = None (fwd_years=0)."""
    from core.data import stockanalysis_financials as sa

    data = {
        "revenue": [
            {"year": "2024", "period_end": "2024", "value": 400_000.0, "is_estimate": False},
            {"year": "2024", "period_end": "2024", "value": 500_000.0, "is_estimate": True},
        ],
        "eps": [],
        "roe": [],
        "latest_report_date": None,
    }

    with patch.object(sa, "fetch_annual_financials", return_value=data):
        result = sa.compute_consensus_growth("TEST")

    assert result["rev_fwd_cagr"] is None


# ── 3. ExtendedSnapshot 신규 필드 존재 확인 ──────────────────────────────────

def test_extended_snapshot_new_fields():
    from core.data.fundamentals_extended import ExtendedSnapshot
    from datetime import date
    snap = ExtendedSnapshot(ticker="TEST", as_of=date.today())
    assert hasattr(snap, "roic")
    assert hasattr(snap, "gross_margin")
    assert hasattr(snap, "operating_margin")
    assert hasattr(snap, "current_ratio")
    assert hasattr(snap, "sales_growth")
    assert hasattr(snap, "fwd_revenue_growth")
    assert hasattr(snap, "fwd_eps_growth")
    assert hasattr(snap, "market_cap_krw_b")
    # 기본값 None
    assert snap.roic is None
    assert snap.fwd_revenue_growth is None
    assert snap.market_cap_krw_b is None


def test_extended_snapshot_foreign_branch_maps_growth(monkeypatch):
    """해외 종목 _fetch_one이 신규 필드를 올바르게 매핑한다."""
    from core.data import fundamentals_extended as fe
    from core.data.fundamentals_scraper import FundamentalsSnapshot
    from datetime import date

    mock_scraped = FundamentalsSnapshot(
        ticker="AAPL",
        forward_pe=25.0,
        trailing_pe=28.0,
        short_name="Apple Inc.",
        roic=35.0,
        gross_margin=44.0,
        operating_margin=30.0,
        current_ratio=1.1,
        sales_qq=5.0,
    )

    mock_growth = {"rev_fwd_cagr": 0.08, "eps_fwd_cagr": 0.12, "fwd_years": 3}

    monkeypatch.setattr(fe, "_scrape", lambda ticker: mock_scraped)
    monkeypatch.setattr(
        "core.data.fundamentals_extended.compute_consensus_growth",
        lambda ticker: mock_growth,
        raising=False,
    )

    # compute_consensus_growth는 lazy import이므로 모듈 내부에서 직접 패치
    import core.data.stockanalysis_financials as sa
    monkeypatch.setattr(sa, "fetch_annual_financials", lambda t: None)

    snap = fe._fetch_one("AAPL", date.today())
    assert snap.roic == pytest.approx(35.0)
    assert snap.gross_margin == pytest.approx(44.0)
    assert snap.operating_margin == pytest.approx(30.0)
    assert snap.current_ratio == pytest.approx(1.1)
    assert snap.sales_growth == pytest.approx(5.0)


def test_extended_snapshot_domestic_maps_market_cap(monkeypatch):
    """국내 종목 _fetch_one이 market_cap_krw_b를 올바르게 매핑한다."""
    from core.data import fundamentals_extended as fe
    from datetime import date

    mock_nav = {
        "per": 12.5,
        "pbr": 1.2,
        "eps": 5000.0,
        "fwd_per": 11.0,
        "fwd_eps": 5500.0,
        "name": "삼성전자",
        "sector": "전기전자",
        "market_cap_krw_b": 3_800_000.0,
    }

    monkeypatch.setattr(
        "core.data.fundamentals_extended.fetch_naver_summary",
        lambda ticker: mock_nav,
        raising=False,
    )
    # 국내 branch는 naver_fundamentals를 lazy import하므로 직접 패치
    import core.data.naver_fundamentals as nf
    monkeypatch.setattr(nf, "fetch_naver_summary", lambda ticker: mock_nav)

    snap = fe._fetch_one("005930.KS", date.today())
    assert snap.market_cap_krw_b == pytest.approx(3_800_000.0)
    assert snap.company_name == "삼성전자"
