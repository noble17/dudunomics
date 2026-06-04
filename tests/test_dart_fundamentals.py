"""tests/test_dart_fundamentals.py — OpenDART 기반 국내 성장주 필수 지표."""
from __future__ import annotations

import pytest


def test_parse_corp_codes_maps_stock_code_to_corp_code():
    from core.data.dart_fundamentals import parse_corp_codes

    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <result>
      <list><corp_code>00126380</corp_code><corp_name>삼성전자</corp_name><stock_code>005930</stock_code></list>
      <list><corp_code>00164742</corp_code><corp_name>카카오</corp_name><stock_code>035720</stock_code></list>
      <list><corp_code>00000001</corp_code><corp_name>비상장</corp_name><stock_code> </stock_code></list>
    </result>
    """

    assert parse_corp_codes(xml) == {"005930": "00126380", "035720": "00164742"}


def test_build_snapshot_from_dart_rows_computes_required_metrics():
    from core.data.dart_fundamentals import build_snapshot_from_rows

    rows = [
        {"sj_div": "IS", "account_nm": "매출액", "thstrm_amount": "1,000,000"},
        {"sj_div": "IS", "account_nm": "영업이익", "thstrm_amount": "180,000"},
        {"sj_div": "IS", "account_nm": "법인세비용차감전순이익", "thstrm_amount": "160,000"},
        {"sj_div": "IS", "account_nm": "법인세비용", "thstrm_amount": "40,000"},
        {"sj_div": "BS", "account_nm": "유동자산", "thstrm_amount": "900,000"},
        {"sj_div": "BS", "account_nm": "유동부채", "thstrm_amount": "450,000"},
        {"sj_div": "BS", "account_nm": "자본총계", "thstrm_amount": "1,200,000"},
        {"sj_div": "BS", "account_nm": "단기차입금", "thstrm_amount": "100,000"},
        {"sj_div": "BS", "account_nm": "장기차입금", "thstrm_amount": "300,000"},
        {"sj_div": "BS", "account_nm": "현금및현금성자산", "thstrm_amount": "200,000"},
        {"sj_div": "CF", "account_nm": "영업활동 현금흐름", "thstrm_amount": "220,000"},
        {"sj_div": "CF", "account_nm": "유형자산의 취득", "thstrm_amount": "-70,000"},
    ]

    snap = build_snapshot_from_rows("005930.KS", rows, market_cap_krw=5_000_000)

    assert snap.operating_margin == pytest.approx(0.18)
    assert snap.current_ratio == pytest.approx(2.0)
    # NOPAT = 180000 * (1 - 40000/160000) = 135000
    # invested capital = 1200000 + 100000 + 300000 - 200000 = 1400000
    assert snap.roic == pytest.approx(135_000 / 1_400_000)
    assert snap.operating_cashflow == pytest.approx(220_000)
    assert snap.capex == pytest.approx(70_000)
    assert snap.fcf_yield == pytest.approx((220_000 - 70_000) / 5_000_000)
    assert snap.data_coverage["dart_required_complete"] is True


def test_build_snapshot_marks_missing_required_metrics():
    from core.data.dart_fundamentals import build_snapshot_from_rows

    snap = build_snapshot_from_rows(
        "005930.KS",
        [{"sj_div": "IS", "account_nm": "매출액", "thstrm_amount": "1,000"}],
        market_cap_krw=5_000_000,
    )

    assert snap.data_coverage["dart_required_complete"] is False
    assert "operating_cashflow" in snap.data_coverage["missing"]
    assert "current_ratio" in snap.data_coverage["missing"]


def test_fetch_dart_snapshot_falls_back_to_previous_business_year(monkeypatch):
    from core.data import dart_fundamentals as dart

    monkeypatch.setenv("DART_API_KEY", "test-key")
    monkeypatch.setattr(dart, "fetch_corp_code_map", lambda api_key: {"005930": "00126380"})
    calls = []

    def fake_fetch(api_key, corp_code, year, report_code, fs_div):
        calls.append((year, report_code, fs_div))
        if year == 2025 and report_code == "11011" and fs_div == "CFS":
            return [{"account_nm": "매출액", "thstrm_amount": "1,000"}]
        return []

    monkeypatch.setattr(dart, "_fetch_statement_rows", fake_fetch)

    dart.fetch_dart_snapshot("005930.KS", market_cap_krw=5_000_000, bsns_year=2026)

    assert any(year == 2025 for year, _, _ in calls)


def test_build_snapshot_uses_balance_sheet_equity_and_debt_only():
    from core.data.dart_fundamentals import build_snapshot_from_rows

    rows = [
        {"sj_div": "IS", "account_nm": "매출액", "thstrm_amount": "1,000"},
        {"sj_div": "IS", "account_nm": "영업이익", "thstrm_amount": "100"},
        {"sj_div": "BS", "account_nm": "자본총계", "thstrm_amount": "1,000"},
        {"sj_div": "SCE", "account_nm": "자본총계", "thstrm_amount": "10"},
        {"sj_div": "BS", "account_nm": "현금및현금성자산", "thstrm_amount": "100"},
        {"sj_div": "BS", "account_nm": "단기차입금", "thstrm_amount": "200"},
        {"sj_div": "CF", "account_nm": "장기차입금의 차입", "thstrm_amount": "9,999"},
        {"sj_div": "CF", "account_nm": "영업활동 현금흐름", "thstrm_amount": "150"},
        {"sj_div": "CF", "account_nm": "유형자산의 취득", "thstrm_amount": "-50"},
    ]

    snap = build_snapshot_from_rows("005930.KS", rows, market_cap_krw=5_000)

    # NOPAT = 100 * (1 - default tax rate 25%), invested capital = BS equity 1000 + BS debt 200 - BS cash 100
    assert snap.roic == pytest.approx(75 / 1_100)
