"""공통 퀀트 배치 갱신 정책."""
from __future__ import annotations

import os
from datetime import date

import core.batch_state as bs
import core.repository as repo

_KR_UNIVERSES = {"kospi200", "kosdaq150"}


class BatchAlreadyRunningError(RuntimeError):
    pass


class DartApiKeyRequiredError(RuntimeError):
    pass


def get_status(universe: str) -> dict:
    status = dict(bs.get(universe))
    latest = repo.get_latest_quant_as_of(universe)
    status["latest_as_of"] = latest.isoformat() if latest else ""
    status["is_fresh"] = latest == date.today()
    return status


def refresh(universe: str, background_tasks=None, force: bool = False) -> dict:
    if universe in _KR_UNIVERSES and not os.getenv("DART_API_KEY"):
        raise DartApiKeyRequiredError("국내 성장주 배치에는 DART_API_KEY가 필요합니다.")

    status = get_status(universe)
    if status["status"] == "running":
        raise BatchAlreadyRunningError(f"{universe} 배치가 이미 실행 중입니다.")
    if status["is_fresh"] and not force:
        return {**status, "status": "fresh", "universe": universe}

    def _run():
        try:
            from core.scoring.universe_scorer import run_batch
            run_batch(universe)
        except Exception as exc:
            bs.fail(universe, str(exc))

    if background_tasks:
        background_tasks.add_task(_run)
        return {"status": "started", "universe": universe}

    from core.scoring.universe_scorer import run_batch
    return run_batch(universe)
