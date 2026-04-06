from __future__ import annotations

from datetime import date, datetime

from life_world_model.analysis.pattern_discovery import (
    detect_circadian_rhythm,
    detect_context_switching_cost,
    detect_productivity_correlations,
    detect_routines,
    detect_time_sinks,
    discover_patterns,
)
from life_world_model.types import LifeState


def _make_state(
    day: date,
    hour: int,
    minute: int = 0,
    activity: str = "browsing",
    domain: str | None = None,
    dwell_seconds: float | None = None,
    context_switches: int | None = None,
    session_depth: int | None = None,
) -> LifeState:
    """Helper to build a LifeState for testing."""
    return LifeState(
        timestamp=datetime(day.year, day.month, day.day, hour, minute),
        primary_activity=activity,
        secondary_activity=None,
        domain=domain,
        event_count=5,
        confidence=0.8,
        sources=["chrome"],
        dwell_seconds=dwell_seconds,
        context_switches=context_switches,
        session_depth=session_depth,
    )


def _build_multi_day(
    days: list[date],
    hours_activities: list[tuple[int, str]],
    **kwargs,
) -> dict[date, list[LifeState]]:
    """Build a multi-day dict where every day has the same hour/activity pairs."""
    result: dict[date, list[LifeState]] = {}
    for day in days:
        result[day] = [
            _make_state(day, hour, activity=act, **kwargs)
            for hour, act in hours_activities
        ]
    return result


# ---- Detector 1: Routines ----


def test_detect_routines_finds_consistent_activity() -> None:
    """Same activity at 9am on 4/5 days should be detected as a routine."""
    days = [date(2026, 4, d) for d in range(1, 6)]  # 5 days
    multi_day: dict[date, list[LifeState]] = {}
    for day in days[:4]:
        multi_day[day] = [_make_state(day, 9, activity="research")]
    # Day 5: different activity at 9am
    multi_day[days[4]] = [_make_state(days[4], 9, activity="browsing")]

    patterns = detect_routines(multi_day)

    routine_names = [p.name for p in patterns]
    assert "research_at_9" in routine_names
    research_pattern = next(p for p in patterns if p.name == "research_at_9")
    assert research_pattern.category == "routine"
    assert research_pattern.evidence["frequency"] >= 0.6
    assert research_pattern.evidence["days_observed"] == 4


def test_detect_routines_ignores_infrequent() -> None:
    """Activity at 9am on only 1/5 days should NOT be reported."""
    days = [date(2026, 4, d) for d in range(1, 6)]
    multi_day: dict[date, list[LifeState]] = {}
    # Only day 1 has research at 9am
    multi_day[days[0]] = [_make_state(days[0], 9, activity="research")]
    for day in days[1:]:
        multi_day[day] = [_make_state(day, 9, activity="browsing")]

    patterns = detect_routines(multi_day)

    # research_at_9 should NOT appear (only 20%)
    routine_names = [p.name for p in patterns]
    assert "research_at_9" not in routine_names


# ---- Detector 2: Productivity Correlations ----


def test_detect_productivity_correlations() -> None:
    """Coding after research should be detected as a correlation."""
    days = [date(2026, 4, d) for d in range(1, 8)]  # 7 days
    multi_day: dict[date, list[LifeState]] = {}
    for day in days:
        multi_day[day] = [
            _make_state(day, 9, activity="research"),
            _make_state(day, 10, activity="coding"),
            _make_state(day, 11, activity="coding"),
        ]

    patterns = detect_productivity_correlations(multi_day)

    # research -> coding should appear with sample_size >= 5
    corr_names = [p.name for p in patterns]
    assert "research_precedes_coding" in corr_names
    rp = next(p for p in patterns if p.name == "research_precedes_coding")
    assert rp.category == "correlation"
    assert rp.evidence["sample_size"] >= 5
    assert rp.evidence["probability"] > 0


# ---- Detector 3: Circadian Rhythm ----


def test_detect_circadian_rhythm_finds_peaks() -> None:
    """Low switches at 10am + high dwell should show as peak; high switches at 14 as scattered."""
    days = [date(2026, 4, d) for d in range(1, 6)]
    multi_day: dict[date, list[LifeState]] = {}
    for day in days:
        multi_day[day] = [
            # 10am: focused (low switches, high dwell)
            _make_state(day, 10, activity="coding", context_switches=1, dwell_seconds=800),
            # 14: scattered (high switches, low dwell)
            _make_state(day, 14, activity="browsing", context_switches=10, dwell_seconds=60),
            # 16: moderate
            _make_state(day, 16, activity="browsing", context_switches=5, dwell_seconds=300),
        ]

    patterns = detect_circadian_rhythm(multi_day)

    assert len(patterns) == 1
    rhythm = patterns[0]
    assert rhythm.category == "rhythm"
    assert 10 in rhythm.evidence["peak_hours"]
    assert 14 in rhythm.evidence["scattered_hours"]


# ---- Detector 4: Context-Switching Cost ----


def test_detect_context_switching_cost() -> None:
    """Recovery time after high-switch buckets should be measurable."""
    days = [date(2026, 4, d) for d in range(1, 6)]
    multi_day: dict[date, list[LifeState]] = {}
    for day in days:
        multi_day[day] = [
            # High context switching at 10am
            _make_state(day, 10, activity="browsing", context_switches=8, session_depth=0),
            # Recovery bucket 1 (still shallow)
            _make_state(day, 10, minute=15, activity="browsing", context_switches=3, session_depth=1),
            # Recovery bucket 2 (deep focus restored)
            _make_state(day, 10, minute=30, activity="coding", context_switches=1, session_depth=3),
        ]

    patterns = detect_context_switching_cost(multi_day)

    assert len(patterns) == 1
    p = patterns[0]
    assert p.category == "trigger"
    assert p.evidence["sample_size"] >= 3
    assert p.evidence["avg_recovery_buckets"] == 2  # 2 buckets to recover
    assert p.evidence["avg_recovery_minutes"] == 30.0


# ---- Detector 5: Time Sinks ----


def test_detect_time_sinks_flags_high_time_low_dwell() -> None:
    """Browsing with fragmented attention should be flagged as a time sink."""
    days = [date(2026, 4, d) for d in range(1, 6)]
    multi_day: dict[date, list[LifeState]] = {}
    for day in days:
        multi_day[day] = [
            # Lots of scattered browsing
            _make_state(day, 9, activity="browsing", domain="twitter.com",
                        dwell_seconds=30, context_switches=12),
            _make_state(day, 10, activity="browsing", domain="twitter.com",
                        dwell_seconds=25, context_switches=15),
            _make_state(day, 11, activity="browsing", domain="twitter.com",
                        dwell_seconds=20, context_switches=10),
            # Focused coding (not a sink)
            _make_state(day, 14, activity="coding",
                        dwell_seconds=900, context_switches=1),
        ]

    patterns = detect_time_sinks(multi_day)

    assert len(patterns) > 0
    # twitter.com browsing should rank as a sink
    sink_activities = [p.evidence["activity"] for p in patterns]
    assert any("twitter.com" in a for a in sink_activities)

    twitter_sink = next(p for p in patterns if "twitter.com" in p.evidence["activity"])
    assert twitter_sink.evidence["avg_switches"] > 5
    assert twitter_sink.evidence["avg_dwell"] < 100


# ---- Integration ----


def test_discover_patterns_runs_all_detectors() -> None:
    """Integration test: discover_patterns should aggregate results from all detectors."""
    days = [date(2026, 4, d) for d in range(1, 8)]
    multi_day: dict[date, list[LifeState]] = {}
    for day in days:
        multi_day[day] = [
            _make_state(day, 9, activity="research", context_switches=2,
                        dwell_seconds=600, session_depth=1),
            _make_state(day, 10, activity="coding", context_switches=1,
                        dwell_seconds=800, session_depth=3),
            _make_state(day, 11, activity="coding", context_switches=1,
                        dwell_seconds=700, session_depth=3),
            _make_state(day, 14, activity="browsing", domain="reddit.com",
                        context_switches=10, dwell_seconds=40, session_depth=0),
            _make_state(day, 15, activity="browsing", domain="reddit.com",
                        context_switches=8, dwell_seconds=50, session_depth=0),
            _make_state(day, 16, activity="coding", context_switches=2,
                        dwell_seconds=500, session_depth=2),
        ]

    patterns = discover_patterns(multi_day)

    categories = {p.category for p in patterns}
    # Should include multiple categories
    assert len(patterns) > 0
    # At minimum we expect routines (same activities every day) and time_sinks
    assert "routine" in categories
    assert "time_sink" in categories


def test_empty_data_returns_no_patterns() -> None:
    """All detectors should handle empty input gracefully."""
    patterns = discover_patterns({})
    assert patterns == []

    assert detect_routines({}) == []
    assert detect_productivity_correlations({}) == []
    assert detect_circadian_rhythm({}) == []
    assert detect_context_switching_cost({}) == []
    assert detect_time_sinks({}) == []
