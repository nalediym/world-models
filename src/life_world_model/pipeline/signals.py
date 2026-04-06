"""TikTok-style behavioral signal extraction.

Post-processing pass over LifeState buckets to enrich them with:
- dwell_seconds: total time spent in each bucket (from knowledgeC duration)
- context_switches: number of distinct consecutive app transitions
- session_depth: length of consecutive-same-activity runs
"""

from __future__ import annotations

from datetime import datetime

from life_world_model.types import LifeState, RawEvent


def _compute_dwell_seconds(
    events: list[RawEvent], bucket_minutes: int
) -> float:
    """Sum duration_seconds from knowledgeC events. Estimate if none available."""
    knowledgec_events = [e for e in events if e.source == "knowledgec"]

    if knowledgec_events:
        durations = [
            e.duration_seconds
            for e in knowledgec_events
            if e.duration_seconds is not None and e.duration_seconds > 0
        ]
        if durations:
            return sum(durations)

    # Estimate: spread bucket time evenly across events
    if events:
        return float(bucket_minutes * 60)

    return 0.0


def _compute_context_switches(events: list[RawEvent]) -> int:
    """Count distinct consecutive app transitions within a bucket.

    Looks at knowledgeC /app/inFocus events sorted by timestamp.
    Each time the app (bundle ID in domain field) changes, that is a switch.
    """
    in_focus_events = sorted(
        [
            e
            for e in events
            if e.source == "knowledgec"
            and e.metadata
            and e.metadata.get("stream") == "/app/inFocus"
        ],
        key=lambda e: e.timestamp,
    )

    if len(in_focus_events) <= 1:
        return 0

    switches = 0
    prev_app = in_focus_events[0].domain
    for event in in_focus_events[1:]:
        if event.domain != prev_app:
            switches += 1
            prev_app = event.domain

    return switches


def _compute_session_depth(states: list[LifeState]) -> None:
    """Scan forward from each bucket and count consecutive same-activity runs.

    Mutates states in-place: sets session_depth on each bucket to the length
    of its contiguous run.
    """
    if not states:
        return

    n = len(states)
    i = 0
    while i < n:
        # Find the end of this run
        j = i + 1
        while j < n and states[j].primary_activity == states[i].primary_activity:
            j += 1
        run_length = j - i
        for k in range(i, j):
            states[k].session_depth = run_length
        i = j


def compute_signals(
    states: list[LifeState],
    events_by_bucket: dict[datetime, list[RawEvent]],
    bucket_minutes: int = 15,
) -> list[LifeState]:
    """Enrich LifeState objects with behavioral signals.

    Computes dwell_seconds, context_switches per bucket, then session_depth
    across the full list.
    """
    for state in states:
        bucket_events = events_by_bucket.get(state.timestamp, [])

        state.dwell_seconds = _compute_dwell_seconds(bucket_events, bucket_minutes)
        state.context_switches = _compute_context_switches(bucket_events)

    _compute_session_depth(states)

    return states
