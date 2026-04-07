from __future__ import annotations

import copy
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from life_world_model.simulation.engine import (
    apply_intervention,
    load_baseline,
    parse_intervention,
    simulate,
)
from life_world_model.simulation.types import Intervention
from life_world_model.types import LifeState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(hour: int, activity: str = "browsing") -> LifeState:
    return LifeState(
        timestamp=datetime(2025, 6, 15, hour, 0),
        primary_activity=activity,
        secondary_activity=None,
        domain=None,
        event_count=5,
        confidence=0.8,
        context_switches=2,
        session_depth=1,
    )


def _day_of_states() -> list[LifeState]:
    """A representative day: coding 8-12, browsing 12-14, idle 14-16, coding 16-18."""
    states = []
    for h in range(8, 12):
        states.append(_make_state(h, "coding"))
    for h in range(12, 14):
        states.append(_make_state(h, "browsing"))
    for h in range(14, 16):
        states.append(_make_state(h, "idle"))
    for h in range(16, 18):
        states.append(_make_state(h, "coding"))
    return states


# ---------------------------------------------------------------------------
# Parsing tests (5 types: time_block, eliminate, limit, add, unknown)
# ---------------------------------------------------------------------------


class TestParseIntervention:
    def test_time_block(self):
        iv = parse_intervention("code from 8-10am")
        assert iv.type == "time_block"
        assert iv.activity == "coding"  # alias resolved
        assert iv.params["start_hour"] == 8
        assert iv.params["end_hour"] == 10

    def test_time_block_24h(self):
        iv = parse_intervention("research from 14-16")
        assert iv.type == "time_block"
        assert iv.activity == "research"
        assert iv.params["start_hour"] == 14
        assert iv.params["end_hour"] == 16

    def test_eliminate(self):
        iv = parse_intervention("stop browsing after 9pm")
        assert iv.type == "eliminate"
        assert iv.activity == "browsing"
        assert iv.params["after_hour"] == 21

    def test_eliminate_no_time(self):
        iv = parse_intervention("stop slack")
        assert iv.type == "eliminate"
        assert iv.activity == "communication"  # alias resolved

    def test_limit(self):
        iv = parse_intervention("limit browse to 1hr")
        assert iv.type == "limit"
        assert iv.activity == "browsing"  # alias resolved
        assert iv.params["max_minutes"] == 60

    def test_limit_minutes(self):
        iv = parse_intervention("limit browsing to 30min")
        assert iv.type == "limit"
        assert iv.activity == "browsing"
        assert iv.params["max_minutes"] == 30

    def test_add(self):
        iv = parse_intervention("add 30min walk at lunch")
        assert iv.type == "add"
        assert iv.activity == "walking"  # alias resolved
        assert iv.params["duration_minutes"] == 30

    def test_add_with_hour(self):
        iv = parse_intervention("add 1hr exercise at 7am")
        assert iv.type == "add"
        assert iv.activity == "exercise"
        assert iv.params["duration_minutes"] == 60
        assert iv.params["at_hour"] == 7

    def test_unknown(self):
        iv = parse_intervention("do something magical")
        assert iv.type == "unknown"


# ---------------------------------------------------------------------------
# Apply intervention tests (4 types + no-mutate)
# ---------------------------------------------------------------------------


class TestApplyIntervention:
    def test_time_block_replaces_buckets(self):
        states = _day_of_states()
        iv = Intervention(
            type="time_block",
            activity="research",
            params={"start_hour": 12, "end_hour": 14},
        )
        result = apply_intervention(states, iv)
        # Hours 12-13 should now be research
        for s in result:
            if 12 <= s.timestamp.hour < 14:
                assert s.primary_activity == "research"

    def test_eliminate_removes_activity(self):
        states = _day_of_states()
        iv = Intervention(
            type="eliminate",
            activity="browsing",
            params={"after_hour": 12},
        )
        result = apply_intervention(states, iv)
        for s in result:
            if s.timestamp.hour >= 12:
                assert s.primary_activity != "browsing"

    def test_limit_caps_at_max(self):
        states = _day_of_states()
        # 2 browsing buckets (hours 12, 13). Limit to 15min = 1 bucket.
        iv = Intervention(
            type="limit",
            activity="browsing",
            params={"max_minutes": 15},
        )
        result = apply_intervention(states, iv)
        browsing_count = sum(
            1 for s in result if s.primary_activity == "browsing"
        )
        assert browsing_count == 1  # limited to 1 bucket

    def test_add_inserts_activity(self):
        states = _day_of_states()
        iv = Intervention(
            type="add",
            activity="walking",
            params={"duration_minutes": 30, "at_hour": 14},
        )
        result = apply_intervention(states, iv)
        walking = [s for s in result if s.primary_activity == "walking"]
        assert len(walking) == 2  # 30min / 15min = 2 buckets

    def test_no_mutate_original(self):
        states = _day_of_states()
        original_activities = [s.primary_activity for s in states]
        iv = Intervention(
            type="time_block",
            activity="research",
            params={"start_hour": 8, "end_hour": 18},
        )
        _ = apply_intervention(states, iv)
        # Original should be untouched
        current_activities = [s.primary_activity for s in states]
        assert current_activities == original_activities


# ---------------------------------------------------------------------------
# End-to-end simulate with mock store
# ---------------------------------------------------------------------------


class TestSimulate:
    def test_simulate_returns_result(self):
        """Simulate with a mock store that returns demo events."""
        from life_world_model.config import Settings
        from life_world_model.types import RawEvent

        mock_store = MagicMock()
        # Return events that will build into known LifeStates
        base_date = date(2025, 6, 15)
        events = []
        for h in range(8, 18):
            events.append(
                RawEvent(
                    timestamp=datetime(2025, 6, 15, h, 0),
                    source="chrome",
                    title="test",
                    domain="github.com" if h < 14 else "reddit.com",
                )
            )
        mock_store.load_raw_events_for_date.return_value = events

        settings = Settings()
        result = simulate(
            mock_store, settings, "code from 8-12am", baseline_date=base_date
        )

        assert result.intervention.type == "time_block"
        assert result.intervention.activity == "coding"
        assert isinstance(result.baseline_score, float)
        assert isinstance(result.simulated_score, float)
        assert isinstance(result.score_delta, float)
        assert "Intervention" in result.summary

    def test_simulate_empty_baseline(self):
        """Simulate against empty data returns zero scores."""
        from life_world_model.config import Settings

        mock_store = MagicMock()
        mock_store.load_raw_events_for_date.return_value = []

        settings = Settings()
        result = simulate(
            mock_store, settings, "stop browsing", baseline_date=date(2025, 6, 15)
        )

        assert result.baseline_score == 0.0
        assert result.simulated_score == 0.0
        assert result.score_delta == 0.0
