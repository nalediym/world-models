from __future__ import annotations

from datetime import datetime

from life_world_model.pipeline.bucketizer import build_life_states
from life_world_model.types import RawEvent


def test_build_life_states_groups_into_15_minute_windows() -> None:
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="chrome",
            title="World models paper",
            domain="arxiv.org",
            url="https://arxiv.org/abs/1234",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:11:00"),
            source="chrome",
            title="GitHub repo",
            domain="github.com",
            url="https://github.com/example",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:21:00"),
            source="chrome",
            title="Search results",
            domain="google.com",
            url="https://google.com/search?q=world+models",
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert [state.timestamp.strftime("%H:%M") for state in states] == ["09:00", "09:15"]
    assert states[0].event_count == 2
    assert states[1].event_count == 1


def test_build_life_states_marks_empty_bucket_as_idle() -> None:
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="chrome",
            title="GitHub repo",
            domain="github.com",
            url="https://github.com/example",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:33:00"),
            source="chrome",
            title="Later visit",
            domain="github.com",
            url="https://github.com/example/issues",
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert [state.timestamp.strftime("%H:%M") for state in states] == ["09:00", "09:15", "09:30"]
    assert states[1].primary_activity == "idle"
    assert states[1].event_count == 0


def test_build_life_states_labels_github_heavy_bucket() -> None:
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="chrome",
            title="GitHub pull request",
            domain="github.com",
            url="https://github.com/example/pull/1",
        )
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert states[0].primary_activity == "research"
