from __future__ import annotations

from datetime import datetime

from life_world_model.pipeline.signals import (
    _compute_context_switches,
    _compute_dwell_seconds,
    _compute_session_depth,
    compute_signals,
)
from life_world_model.types import LifeState, RawEvent


# ---------------------------------------------------------------------------
# dwell_seconds
# ---------------------------------------------------------------------------


def test_dwell_seconds_from_knowledgec_duration() -> None:
    """dwell_seconds should sum duration_seconds from knowledgeC events."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="knowledgec",
            title="VS Code",
            domain="com.microsoft.VSCode",
            duration_seconds=300,
            metadata={"stream": "/app/inFocus"},
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:08:00"),
            source="knowledgec",
            title="Terminal",
            domain="com.apple.Terminal",
            duration_seconds=200,
            metadata={"stream": "/app/inFocus"},
        ),
    ]

    dwell = _compute_dwell_seconds(events, bucket_minutes=15)

    assert dwell == 500.0


def test_dwell_seconds_estimate_when_no_knowledgec() -> None:
    """When no knowledgeC events, estimate from bucket duration."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="chrome",
            title="GitHub",
            domain="github.com",
        ),
    ]

    dwell = _compute_dwell_seconds(events, bucket_minutes=15)

    assert dwell == 900.0  # 15 min * 60


def test_dwell_seconds_zero_for_empty_bucket() -> None:
    """Empty bucket should have 0 dwell_seconds."""
    dwell = _compute_dwell_seconds([], bucket_minutes=15)

    assert dwell == 0.0


def test_dwell_seconds_ignores_none_durations() -> None:
    """knowledgeC events with None duration should be skipped, not crash."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="knowledgec",
            title="VS Code",
            domain="com.microsoft.VSCode",
            duration_seconds=None,
            metadata={"stream": "/app/inFocus"},
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:05:00"),
            source="knowledgec",
            title="Terminal",
            domain="com.apple.Terminal",
            duration_seconds=400,
            metadata={"stream": "/app/inFocus"},
        ),
    ]

    dwell = _compute_dwell_seconds(events, bucket_minutes=15)

    assert dwell == 400.0


# ---------------------------------------------------------------------------
# context_switches
# ---------------------------------------------------------------------------


def test_context_switches_counts_app_transitions() -> None:
    """context_switches should count distinct app changes."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:01:00"),
            source="knowledgec",
            title="VS Code",
            domain="com.microsoft.VSCode",
            duration_seconds=120,
            metadata={"stream": "/app/inFocus"},
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:03:00"),
            source="knowledgec",
            title="Slack",
            domain="com.tinyspeck.slackmacgap",
            duration_seconds=60,
            metadata={"stream": "/app/inFocus"},
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:05:00"),
            source="knowledgec",
            title="VS Code",
            domain="com.microsoft.VSCode",
            duration_seconds=180,
            metadata={"stream": "/app/inFocus"},
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:08:00"),
            source="knowledgec",
            title="Chrome",
            domain="com.google.Chrome",
            duration_seconds=60,
            metadata={"stream": "/app/inFocus"},
        ),
    ]

    switches = _compute_context_switches(events)

    assert switches == 3  # VSCode -> Slack -> VSCode -> Chrome


def test_zero_context_switches_for_single_app() -> None:
    """A single app in the bucket means zero context switches."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:01:00"),
            source="knowledgec",
            title="VS Code",
            domain="com.microsoft.VSCode",
            duration_seconds=300,
            metadata={"stream": "/app/inFocus"},
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:06:00"),
            source="knowledgec",
            title="VS Code",
            domain="com.microsoft.VSCode",
            duration_seconds=300,
            metadata={"stream": "/app/inFocus"},
        ),
    ]

    switches = _compute_context_switches(events)

    assert switches == 0


def test_context_switches_ignores_non_focus_events() -> None:
    """Only /app/inFocus events should count — Safari history is ignored."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:01:00"),
            source="knowledgec",
            title="Safari History",
            url="https://example.com",
            domain="example.com",
            metadata={"stream": "/safari/history"},
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="knowledgec",
            title="Safari History",
            url="https://other.com",
            domain="other.com",
            metadata={"stream": "/safari/history"},
        ),
    ]

    switches = _compute_context_switches(events)

    assert switches == 0


def test_context_switches_empty_bucket() -> None:
    """Empty bucket means zero switches."""
    assert _compute_context_switches([]) == 0


# ---------------------------------------------------------------------------
# session_depth
# ---------------------------------------------------------------------------


def _make_state(timestamp_str: str, activity: str) -> LifeState:
    """Helper to build a minimal LifeState for session_depth tests."""
    return LifeState(
        timestamp=datetime.fromisoformat(timestamp_str),
        primary_activity=activity,
        secondary_activity=None,
        domain=None,
        event_count=1,
        confidence=0.8,
    )


def test_session_depth_counts_consecutive_same_activity() -> None:
    """Consecutive buckets with the same activity get the run length."""
    states = [
        _make_state("2026-03-21T09:00:00", "coding"),
        _make_state("2026-03-21T09:15:00", "coding"),
        _make_state("2026-03-21T09:30:00", "coding"),
    ]

    _compute_session_depth(states)

    assert states[0].session_depth == 3
    assert states[1].session_depth == 3
    assert states[2].session_depth == 3


def test_session_depth_resets_on_activity_change() -> None:
    """Session depth resets when the activity changes."""
    states = [
        _make_state("2026-03-21T09:00:00", "coding"),
        _make_state("2026-03-21T09:15:00", "coding"),
        _make_state("2026-03-21T09:30:00", "meeting"),
        _make_state("2026-03-21T09:45:00", "coding"),
    ]

    _compute_session_depth(states)

    assert states[0].session_depth == 2  # coding run of 2
    assert states[1].session_depth == 2
    assert states[2].session_depth == 1  # meeting run of 1
    assert states[3].session_depth == 1  # coding run of 1


def test_session_depth_single_bucket() -> None:
    """A single bucket gets session_depth = 1."""
    states = [_make_state("2026-03-21T09:00:00", "browsing")]

    _compute_session_depth(states)

    assert states[0].session_depth == 1


def test_session_depth_empty_list() -> None:
    """Empty list should not crash."""
    states: list[LifeState] = []
    _compute_session_depth(states)
    # No assertion needed — just verify it doesn't raise


# ---------------------------------------------------------------------------
# compute_signals integration
# ---------------------------------------------------------------------------


def test_compute_signals_sets_all_fields() -> None:
    """compute_signals should set dwell, switches, and depth on each state."""
    ts = datetime.fromisoformat("2026-03-21T09:00:00")
    states = [
        LifeState(
            timestamp=ts,
            primary_activity="coding",
            secondary_activity=None,
            domain=None,
            event_count=2,
            confidence=0.85,
        ),
    ]
    events_by_bucket = {
        ts: [
            RawEvent(
                timestamp=ts,
                source="knowledgec",
                title="VS Code",
                domain="com.microsoft.VSCode",
                duration_seconds=500,
                metadata={"stream": "/app/inFocus"},
            ),
        ],
    }

    result = compute_signals(states, events_by_bucket, bucket_minutes=15)

    assert result[0].dwell_seconds == 500.0
    assert result[0].context_switches == 0
    assert result[0].session_depth == 1
