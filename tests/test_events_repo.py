import pytest
from datetime import datetime
import core.repository as repo


def test_get_events_empty():
    assert repo.get_events() == []


def test_insert_and_get_events():
    id1 = repo.insert_event(datetime(2026, 5, 23, 21, 9), "5월 월급", 7_900_000, "입금")
    id2 = repo.insert_event(datetime(2026, 5, 14, 20, 5), "카드값", -2_000_000, "출금")

    events = repo.get_events()
    assert len(events) == 2
    # ORDER BY ts DESC → 5월 23일이 먼저
    assert events[0]["label"] == "5월 월급"
    assert events[0]["amount"] == 7_900_000
    assert events[0]["type"] == "입금"
    assert events[1]["label"] == "카드값"
    assert isinstance(id1, int)
    assert isinstance(id2, int)


def test_delete_event():
    id1 = repo.insert_event(datetime(2026, 5, 1, 10, 0), "테스트", 0, "기타")
    assert len(repo.get_events()) == 1

    repo.delete_event(id1)
    assert repo.get_events() == []


def test_delete_nonexistent_event_does_not_raise():
    repo.delete_event(9999)  # 존재하지 않아도 에러 없음
