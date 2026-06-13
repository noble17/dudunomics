"""관심/보유종목 목표주가 consensus snapshot 명시 적재."""
from __future__ import annotations

import core.repository as repo
from core.data.price_target_consensus import fetch_price_target_consensus


def hydrate_price_target_consensus_snapshots(tickers: list[str] | None = None) -> dict:
    candidates = _normalize_candidates(tickers or repo.list_price_target_consensus_hydration_tickers())
    result = {"requested": len(candidates), "updated": 0, "skipped": 0, "errors": []}

    for ticker in candidates:
        try:
            consensus = fetch_price_target_consensus(ticker)
            repo.upsert_price_target_consensus_snapshot(ticker, consensus)
            if consensus.get("consensus_status") == "ok":
                result["updated"] += 1
            else:
                result["skipped"] += 1
                result["errors"].append(f"{ticker}: {consensus.get('consensus_status')}")
        except Exception as exc:
            result["skipped"] += 1
            result["errors"].append(f"{ticker}: {type(exc).__name__}")

    return result


def _normalize_candidates(tickers: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for ticker in tickers:
        normalized = ticker.strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
