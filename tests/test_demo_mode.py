from __future__ import annotations

from datetime import date

from life_world_model.demo_data import build_demo_events
from life_world_model.pipeline.bucketizer import build_life_states


def test_build_demo_events_returns_seed_data_for_date() -> None:
    events = build_demo_events(date.fromisoformat("2026-03-21"))

    assert len(events) >= 5
    assert all(event.source == "demo" for event in events)
    assert events[0].timestamp.date().isoformat() == "2026-03-21"


def test_demo_events_can_be_bucketized() -> None:
    states = build_life_states(build_demo_events(date.fromisoformat("2026-03-21")))

    assert states
    assert any(state.primary_activity == "research" for state in states)
