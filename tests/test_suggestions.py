from __future__ import annotations

from datetime import date

import pytest

from life_world_model.analysis.suggestions import generate_suggestions
from life_world_model.types import Pattern, Suggestion


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _time_sink_pattern(activity: str = "browsing", total_hours: float = 3.0) -> Pattern:
    return Pattern(
        name=f"time_sink_{activity}",
        category="time_sink",
        description=f"{activity}: {total_hours}h total, high switching",
        evidence={
            "activity": activity,
            "total_hours": total_hours,
            "avg_dwell": 30.0,
            "avg_switches": 5.0,
            "score": 2.5,
        },
        confidence=0.6,
        days_observed=7,
        first_seen=date(2025, 6, 1),
        last_seen=date(2025, 6, 7),
    )


def _trigger_pattern(recovery_minutes: float = 45.0) -> Pattern:
    return Pattern(
        name="context_switching_recovery",
        category="trigger",
        description=f"Recovery takes {recovery_minutes} minutes",
        evidence={
            "avg_recovery_buckets": recovery_minutes / 15,
            "avg_recovery_minutes": recovery_minutes,
            "sample_size": 10,
        },
        confidence=0.5,
        days_observed=7,
        first_seen=date(2025, 6, 1),
        last_seen=date(2025, 6, 7),
    )


def _correlation_pattern(
    precursor: str = "idle", outcome: str = "deep_focus", prob: float = 0.6
) -> Pattern:
    return Pattern(
        name=f"{precursor}_precedes_{outcome}",
        category="correlation",
        description=f"{precursor} precedes {outcome} {prob:.0%} of the time",
        evidence={
            "precursor": precursor,
            "outcome": outcome,
            "probability": prob,
            "sample_size": 20,
        },
        confidence=prob,
        days_observed=7,
        first_seen=date(2025, 6, 1),
        last_seen=date(2025, 6, 7),
    )


def _rhythm_pattern(peak_hours: list[int] | None = None) -> Pattern:
    if peak_hours is None:
        peak_hours = [9, 10, 11]
    return Pattern(
        name="circadian_rhythm",
        category="rhythm",
        description=f"Peak focus hours: {peak_hours}",
        evidence={
            "peak_hours": peak_hours,
            "scattered_hours": [15, 16, 17],
        },
        confidence=0.7,
        days_observed=7,
        first_seen=date(2025, 6, 1),
        last_seen=date(2025, 6, 7),
    )


def _routine_pattern(
    activity: str = "coding", hour: int = 9, frequency: float = 0.8
) -> Pattern:
    return Pattern(
        name=f"{activity}_at_{hour}",
        category="routine",
        description=f"{activity} at {hour}:00 on {frequency:.0%} of days",
        evidence={
            "activity": activity,
            "hour": hour,
            "frequency": frequency,
            "days_observed": 5,
        },
        confidence=frequency,
        days_observed=5,
        first_seen=date(2025, 6, 1),
        last_seen=date(2025, 6, 5),
    )


# ---------------------------------------------------------------------------
# Tests per category
# ---------------------------------------------------------------------------


class TestTimeSinkSuggestion:
    def test_generates_limit(self):
        suggestions = generate_suggestions([_time_sink_pattern()])
        assert len(suggestions) == 1
        s = suggestions[0]
        assert s.intervention_type == "limit"
        assert "browsing" in s.title.lower()
        assert s.source_patterns == ["time_sink_browsing"]

    def test_high_impact_above_2h(self):
        suggestions = generate_suggestions([_time_sink_pattern(total_hours=3.0)])
        assert suggestions[0].predicted_impact == "high"

    def test_medium_impact_below_2h(self):
        suggestions = generate_suggestions([_time_sink_pattern(total_hours=1.5)])
        assert suggestions[0].predicted_impact == "medium"


class TestTriggerSuggestion:
    def test_generates_time_block(self):
        suggestions = generate_suggestions([_trigger_pattern()])
        assert len(suggestions) == 1
        s = suggestions[0]
        assert s.intervention_type == "time_block"
        assert s.source_patterns == ["context_switching_recovery"]

    def test_high_impact_over_30min(self):
        suggestions = generate_suggestions([_trigger_pattern(recovery_minutes=45)])
        assert suggestions[0].predicted_impact == "high"


class TestCorrelationSuggestion:
    def test_positive_correlation_reorder(self):
        suggestions = generate_suggestions(
            [_correlation_pattern(precursor="idle", outcome="deep_focus")]
        )
        assert len(suggestions) == 1
        assert suggestions[0].intervention_type == "reorder"
        assert "idle" in suggestions[0].title.lower()

    def test_negative_correlation_reorder(self):
        suggestions = generate_suggestions(
            [_correlation_pattern(precursor="communication", outcome="scattered")]
        )
        assert len(suggestions) == 1
        assert suggestions[0].intervention_type == "reorder"

    def test_irrelevant_correlation_ignored(self):
        suggestions = generate_suggestions(
            [_correlation_pattern(precursor="coding", outcome="browsing")]
        )
        assert len(suggestions) == 0


class TestRhythmSuggestion:
    def test_protect_focus_window(self):
        suggestions = generate_suggestions([_rhythm_pattern()])
        assert len(suggestions) == 1
        s = suggestions[0]
        assert s.intervention_type == "time_block"
        assert "focus" in s.title.lower()
        assert s.predicted_impact == "high"


class TestRoutineSuggestion:
    def test_keep_routine(self):
        suggestions = generate_suggestions([_routine_pattern()])
        assert len(suggestions) == 1
        s = suggestions[0]
        assert s.intervention_type == "time_block"
        assert s.predicted_impact == "low"
        assert "coding" in s.title.lower()


# ---------------------------------------------------------------------------
# Ranking and dedup
# ---------------------------------------------------------------------------


class TestRankingAndDedup:
    def test_ranked_by_impact_then_delta(self):
        patterns = [
            _routine_pattern(),  # low impact
            _rhythm_pattern(),  # high impact
            _time_sink_pattern(total_hours=3.0),  # high impact
        ]
        suggestions = generate_suggestions(patterns)
        impacts = [s.predicted_impact for s in suggestions]
        # High impacts first, then low
        assert impacts.index("low") > impacts.index("high")

    def test_dedup_same_activity_and_type(self):
        """Two time_block suggestions for the same activity -> keep higher delta."""
        patterns = [
            _routine_pattern(activity="coding", hour=9, frequency=0.8),
            _routine_pattern(activity="coding", hour=10, frequency=0.9),
        ]
        suggestions = generate_suggestions(patterns)
        # Both are time_block for "coding" (from "Keep coding routine at X")
        # Should dedup to one
        coding_suggestions = [
            s for s in suggestions if "coding" in s.title.lower()
        ]
        assert len(coding_suggestions) == 1

    def test_empty_input(self):
        assert generate_suggestions([]) == []


# ---------------------------------------------------------------------------
# Feedback integration
# ---------------------------------------------------------------------------


class TestFeedbackIntegration:
    def test_rejected_suggestions_removed(self):
        from datetime import datetime
        from life_world_model.types import FeedbackAction, SuggestionFeedback

        patterns = [_time_sink_pattern(), _rhythm_pattern()]
        # First generate to get IDs
        suggestions = generate_suggestions(patterns)
        assert len(suggestions) >= 2
        reject_id = suggestions[0].id

        # Now reject the first one
        feedback = [SuggestionFeedback(
            suggestion_id=reject_id,
            suggestion_title=suggestions[0].title,
            action=FeedbackAction.REJECT,
            timestamp=datetime.now(),
        )]
        filtered = generate_suggestions(patterns, feedback=feedback)
        ids = [s.id for s in filtered]
        assert reject_id not in ids

    def test_accepted_suggestions_boosted(self):
        from datetime import datetime
        from life_world_model.types import FeedbackAction, SuggestionFeedback

        patterns = [_routine_pattern()]  # produces "low" impact
        suggestions = generate_suggestions(patterns)
        assert suggestions[0].predicted_impact == "low"
        accept_id = suggestions[0].id

        feedback = [SuggestionFeedback(
            suggestion_id=accept_id,
            suggestion_title=suggestions[0].title,
            action=FeedbackAction.ACCEPT,
            timestamp=datetime.now(),
        )]
        boosted = generate_suggestions(patterns, feedback=feedback)
        assert boosted[0].predicted_impact == "medium"  # low → medium

    def test_no_feedback_is_noop(self):
        patterns = [_time_sink_pattern()]
        without = generate_suggestions(patterns)
        with_empty = generate_suggestions(patterns, feedback=None)
        assert len(without) == len(with_empty)
