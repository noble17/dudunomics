"""배치 진행 상태 공유 저장소 (in-memory)."""
from __future__ import annotations
from datetime import datetime
from typing import TypedDict


class BatchStatus(TypedDict):
    status: str        # "idle" | "running" | "done" | "error"
    step: str          # 현재 단계 설명
    done: int          # 완료된 티커 수
    total: int         # 전체 티커 수
    started_at: str    # ISO 시각
    finished_at: str   # ISO 시각 (완료 시)
    error: str         # 에러 메시지 (실패 시)


_state: dict[str, BatchStatus] = {}


def get(universe: str) -> BatchStatus:
    return _state.get(universe, {
        "status": "idle", "step": "", "done": 0, "total": 0,
        "started_at": "", "finished_at": "", "error": "",
    })


def start(universe: str, total: int) -> None:
    _state[universe] = {
        "status": "running", "step": "초기화 중", "done": 0, "total": total,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "finished_at": "", "error": "",
    }


def update(universe: str, step: str, done: int) -> None:
    if universe in _state:
        _state[universe]["step"] = step
        _state[universe]["done"] = done


def finish(universe: str, done: int) -> None:
    if universe in _state:
        _state[universe].update({
            "status": "done", "step": "완료", "done": done,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        })


def fail(universe: str, error: str) -> None:
    if universe in _state:
        _state[universe].update({
            "status": "error", "step": "실패", "error": error,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        })
