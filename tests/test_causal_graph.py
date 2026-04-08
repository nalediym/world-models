"""Tests for the causal transition graph."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from life_world_model.analysis.causal import (
    CausalGraph,
    TransitionEdge,
    _RNG,
    _blend_probs,
    _get_transition_probs,
    _pick_activity,
    build_causal_graph,
    propagate_intervention,
)
from life_world_model.types import LifeState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    hour: int,
    activity: str = "browsing",
    day: int = 15,
    context_switches: int | None = 2,
    session_depth: int | None = 1,
    dwell_seconds: float | None = 900.0,
) -> LifeState:
    return LifeState(
        timestamp=datetime(2025, 6, day, hour, 0, tzinfo=timezone.utc),
        primary_activity=activity,
        secondary_activity=None,
        domain=None,
        event_count=5,
        confidence=0.8,
        context_switches=context_switches,
        session_depth=session_depth,
        dwell_seconds=dwell_seconds,
    )


def _make_day(
    day: int, pattern: list[tuple[int, str]]
) -> list[LifeState]:
    """Create a day of LifeStates from (hour, activity) pairs."""
    return [_make_state(hour, activity, day=day) for hour, activity in pattern]


def _simple_multi_day() -> dict[date, list[LifeState]]:
    """Create a small multi-day dataset with known transitions.

    Day 1: coding -> coding -> browsing -> idle
    Day 2: coding -> browsing -> browsing -> idle
    Day 3: coding -> coding -> coding -> idle
    """
    return {
        date(2025, 6, 15): _make_day(15, [
            (8, "coding"), (9, "coding"), (10, "browsing"), (11, "idle"),
        ]),
        date(2025, 6, 16): _make_day(16, [
            (8, "coding"), (9, "browsing"), (10, "browsing"), (11, "idle"),
        ]),
        date(2025, 6, 17): _make_day(17, [
            (8, "coding"), (9, "coding"), (10, "coding"), (11, "idle"),
        ]),
    }


# ---------------------------------------------------------------------------
# Transition counting tests
# ---------------------------------------------------------------------------


class TestBuildCausalGraph:
    def test_transition_counting(self):
        """Transitions are counted correctly from known sequences."""
        data = _simple_multi_day()
        graph = build_causal_graph(data)

        # Build a lookup of (from, to) -> edge
        edge_map = {
            (e.from_activity, e.to_activity): e for e in graph.edges
        }

        # coding -> coding: Day1(8->9), Day3(8->9), Day3(9->10) = 3 times
        assert ("coding", "coding") in edge_map
        assert edge_map[("coding", "coding")].sample_count == 3

        # coding -> browsing: Day1(9->10), Day2(8->9) = 2 times
        assert ("coding", "browsing") in edge_map
        assert edge_map[("coding", "browsing")].sample_count == 2

        # browsing -> idle: Day1(10->11), Day2(10->11) = 2 times
        assert ("browsing", "idle") in edge_map
        assert edge_map[("browsing", "idle")].sample_count == 2

        # browsing -> browsing: Day2(9->10) = 1 time
        assert ("browsing", "browsing") in edge_map
        assert edge_map[("browsing", "browsing")].sample_count == 1

    def test_probability_normalization(self):
        """For each source activity, outgoing probabilities sum to 1."""
        data = _simple_multi_day()
        graph = build_causal_graph(data)

        # Group edges by from_activity
        from_totals: dict[str, float] = {}
        for edge in graph.edges:
            from_totals.setdefault(edge.from_activity, 0.0)
            from_totals[edge.from_activity] += edge.probability

        for activity, total in from_totals.items():
            assert abs(total - 1.0) < 0.01, (
                f"Probabilities from {activity} sum to {total}, expected ~1.0"
            )

    def test_coding_to_coding_probability(self):
        """coding -> coding has correct conditional probability."""
        data = _simple_multi_day()
        graph = build_causal_graph(data)

        # Total outgoing from coding: coding->coding(3) + coding->browsing(2) + coding->idle(1) = 6
        edge_map = {
            (e.from_activity, e.to_activity): e for e in graph.edges
        }
        cc = edge_map[("coding", "coding")]
        cb = edge_map[("coding", "browsing")]

        # coding -> coding: 3/6 = 0.5
        assert abs(cc.probability - 0.5) < 0.01
        # coding -> browsing: 2/6 ≈ 0.3333
        assert abs(cb.probability - 1 / 3) < 0.01

    def test_avg_delay(self):
        """Average delay is bucket size (60 min given hourly states)."""
        data = _simple_multi_day()
        graph = build_causal_graph(data)

        for edge in graph.edges:
            # All our test states are exactly 1 hour apart
            assert edge.avg_delay_minutes == 60.0

    def test_empty_data(self):
        """Empty input produces empty graph."""
        graph = build_causal_graph({})
        assert graph.edges == []
        assert graph.activity_effects == {}
        assert graph.hourly_priors == {}
        assert graph.activity_variance == {}
        assert graph.recovery_cost_buckets == 0.0

    def test_single_day_data(self):
        """Single day with one bucket produces no edges."""
        data = {date(2025, 6, 15): [_make_state(8, "coding")]}
        graph = build_causal_graph(data)
        assert graph.edges == []

    def test_single_day_two_buckets(self):
        """Single day with two buckets produces one edge."""
        data = {date(2025, 6, 15): [
            _make_state(8, "coding"),
            _make_state(9, "browsing"),
        ]}
        graph = build_causal_graph(data)
        assert len(graph.edges) == 1
        assert graph.edges[0].from_activity == "coding"
        assert graph.edges[0].to_activity == "browsing"
        assert graph.edges[0].probability == 1.0
        assert graph.edges[0].sample_count == 1


# ---------------------------------------------------------------------------
# Time-of-day effects
# ---------------------------------------------------------------------------


class TestTimeOfDayEffects:
    def test_hourly_priors_computed(self):
        """Hourly priors reflect activity distribution at each hour."""
        data = _simple_multi_day()
        graph = build_causal_graph(data)

        # At hour 8, all 3 days have "coding"
        assert 8 in graph.hourly_priors
        assert graph.hourly_priors[8].get("coding", 0) == 1.0

        # At hour 9, day1=coding, day2=browsing, day3=coding
        assert 9 in graph.hourly_priors
        priors_9 = graph.hourly_priors[9]
        assert abs(priors_9.get("coding", 0) - 2 / 3) < 0.01
        assert abs(priors_9.get("browsing", 0) - 1 / 3) < 0.01

    def test_hourly_priors_sum_to_one(self):
        """Hourly activity probabilities sum to 1 for each hour."""
        data = _simple_multi_day()
        graph = build_causal_graph(data)

        for hour, probs in graph.hourly_priors.items():
            total = sum(probs.values())
            assert abs(total - 1.0) < 0.01, (
                f"Hourly priors at hour {hour} sum to {total}"
            )


# ---------------------------------------------------------------------------
# Activity effects and variance
# ---------------------------------------------------------------------------


class TestActivityEffects:
    def test_activity_effects_populated(self):
        """Activity effects dict is populated for known activities."""
        data = _simple_multi_day()
        graph = build_causal_graph(data)

        # Coding should have effects computed
        assert "coding" in graph.activity_effects

    def test_activity_variance_populated(self):
        """Activity variance is computed for activities with multiple samples."""
        # Create data with varying metrics
        states_day1 = [
            _make_state(8, "coding", day=15, context_switches=1, session_depth=3),
            _make_state(9, "coding", day=15, context_switches=3, session_depth=1),
            _make_state(10, "browsing", day=15, context_switches=5, session_depth=1),
        ]
        states_day2 = [
            _make_state(8, "coding", day=16, context_switches=2, session_depth=2),
            _make_state(9, "coding", day=16, context_switches=4, session_depth=2),
            _make_state(10, "browsing", day=16, context_switches=3, session_depth=1),
        ]
        data = {
            date(2025, 6, 15): states_day1,
            date(2025, 6, 16): states_day2,
        }
        graph = build_causal_graph(data)

        assert "coding" in graph.activity_variance
        assert "context_switches" in graph.activity_variance["coding"]
        assert graph.activity_variance["coding"]["context_switches"] > 0


# ---------------------------------------------------------------------------
# Propagation tests
# ---------------------------------------------------------------------------


class TestPropagateIntervention:
    def test_propagation_changes_downstream(self):
        """After an intervention, downstream activities are predicted via transitions."""
        data = _simple_multi_day()
        graph = build_causal_graph(data)

        baseline = _make_day(15, [
            (8, "browsing"), (9, "browsing"), (10, "browsing"), (11, "idle"),
        ])
        # Intervention: change hour 8 from browsing to coding
        intervention = _make_day(15, [
            (8, "coding"), (9, "browsing"), (10, "browsing"), (11, "idle"),
        ])

        result = propagate_intervention(graph, baseline, intervention)

        # Hour 8 should remain coding (directly changed)
        assert result[0].primary_activity == "coding"
        # Downstream hours should be propagated (not necessarily browsing anymore)
        # The exact value depends on transition probabilities
        assert len(result) == 4
        # Each state should have a valid activity
        for s in result:
            assert isinstance(s.primary_activity, str)
            assert len(s.primary_activity) > 0

    def test_propagation_no_change(self):
        """If intervention doesn't change anything, propagation returns same states."""
        data = _simple_multi_day()
        graph = build_causal_graph(data)

        baseline = _make_day(15, [
            (8, "coding"), (9, "coding"), (10, "browsing"), (11, "idle"),
        ])
        # Identical to baseline
        intervention = _make_day(15, [
            (8, "coding"), (9, "coding"), (10, "browsing"), (11, "idle"),
        ])

        result = propagate_intervention(graph, baseline, intervention)

        for i, s in enumerate(result):
            assert s.primary_activity == baseline[i].primary_activity

    def test_propagation_with_rng(self):
        """Propagation with RNG produces stochastic results."""
        import random as _random

        data = _simple_multi_day()
        graph = build_causal_graph(data)

        baseline = _make_day(15, [
            (8, "browsing"), (9, "browsing"), (10, "browsing"), (11, "idle"),
        ])
        intervention = _make_day(15, [
            (8, "coding"), (9, "browsing"), (10, "browsing"), (11, "idle"),
        ])

        rng = _random.Random(42)
        rng_wrapper = _RNG(rng.random)

        result = propagate_intervention(graph, baseline, intervention, rng=rng_wrapper)
        assert result[0].primary_activity == "coding"
        assert len(result) == 4

    def test_propagation_empty_inputs(self):
        """Propagation with empty states returns empty."""
        graph = CausalGraph(edges=[], activity_effects={})
        assert propagate_intervention(graph, [], []) == []

    def test_propagation_empty_baseline(self):
        """Propagation with empty baseline returns intervention states."""
        graph = CausalGraph(edges=[], activity_effects={})
        intervention = [_make_state(8, "coding")]
        result = propagate_intervention(graph, [], intervention)
        assert len(result) == 1
        assert result[0].primary_activity == "coding"

    def test_propagation_preserves_intervention_changes(self):
        """The directly changed buckets should not be overwritten by propagation."""
        data = _simple_multi_day()
        graph = build_causal_graph(data)

        baseline = _make_day(15, [
            (8, "browsing"), (9, "browsing"), (10, "browsing"),
            (11, "browsing"), (12, "idle"),
        ])
        # Change hours 8-10 to coding
        intervention = _make_day(15, [
            (8, "coding"), (9, "coding"), (10, "coding"),
            (11, "browsing"), (12, "idle"),
        ])

        result = propagate_intervention(graph, baseline, intervention)

        # Hours 8, 9, 10 should remain coding (the intervention)
        assert result[0].primary_activity == "coding"
        assert result[1].primary_activity == "coding"
        assert result[2].primary_activity == "coding"


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    def test_get_transition_probs(self):
        """_get_transition_probs returns correct outgoing edges."""
        graph = CausalGraph(
            edges=[
                TransitionEdge("coding", "browsing", 0.6, 6, 15.0),
                TransitionEdge("coding", "idle", 0.4, 4, 15.0),
                TransitionEdge("browsing", "coding", 1.0, 3, 15.0),
            ],
            activity_effects={},
        )
        probs = _get_transition_probs(graph, "coding")
        assert probs == {"browsing": 0.6, "idle": 0.4}

    def test_get_transition_probs_unknown(self):
        """Unknown activity returns empty dict."""
        graph = CausalGraph(edges=[], activity_effects={})
        probs = _get_transition_probs(graph, "unknown")
        assert probs == {}

    def test_blend_probs(self):
        """Blending transition and hourly priors produces weighted average."""
        trans = {"coding": 0.8, "browsing": 0.2}
        hourly = {"coding": 0.4, "browsing": 0.4, "idle": 0.2}

        blended = _blend_probs(trans, hourly, transition_weight=0.7)

        # coding: 0.8*0.7 + 0.4*0.3 = 0.56 + 0.12 = 0.68
        # browsing: 0.2*0.7 + 0.4*0.3 = 0.14 + 0.12 = 0.26
        # idle: 0.0*0.7 + 0.2*0.3 = 0.06
        # total = 1.0 (already normalized)
        assert abs(blended["coding"] - 0.68) < 0.01
        assert abs(blended["browsing"] - 0.26) < 0.01
        assert abs(blended["idle"] - 0.06) < 0.01

        # Should sum to 1
        assert abs(sum(blended.values()) - 1.0) < 0.01

    def test_pick_activity(self):
        """_pick_activity selects based on cumulative distribution."""
        probs = {"browsing": 0.3, "coding": 0.5, "idle": 0.2}
        # Sorted keys: browsing(0.3), coding(0.5), idle(0.2)
        # cumulative: browsing=[0,0.3), coding=[0.3,0.8), idle=[0.8,1.0)

        assert _pick_activity(probs, 0.0) == "browsing"
        assert _pick_activity(probs, 0.29) == "browsing"
        assert _pick_activity(probs, 0.3) == "coding"
        assert _pick_activity(probs, 0.79) == "coding"
        assert _pick_activity(probs, 0.8) == "idle"
        assert _pick_activity(probs, 0.99) == "idle"

    def test_pick_activity_empty(self):
        """Empty probs returns idle."""
        assert _pick_activity({}, 0.5) == "idle"


# ---------------------------------------------------------------------------
# Recovery cost
# ---------------------------------------------------------------------------


class TestRecoveryCost:
    def test_recovery_cost_computed(self):
        """Recovery cost is computed from high-switch -> deep focus transitions."""
        states = [
            _make_state(8, "browsing", context_switches=8, session_depth=1),
            _make_state(9, "browsing", context_switches=3, session_depth=1),
            _make_state(10, "coding", context_switches=1, session_depth=3),
            _make_state(11, "coding", context_switches=0, session_depth=4),
        ]
        data = {date(2025, 6, 15): states}
        graph = build_causal_graph(data)

        # High switch at hour 8 (>5), recovery at hour 10 (depth>=2) -> 2 buckets
        assert graph.recovery_cost_buckets == 2.0

    def test_no_recovery_data(self):
        """No high-switch events means recovery cost is 0."""
        states = [
            _make_state(8, "coding", context_switches=1, session_depth=3),
            _make_state(9, "coding", context_switches=0, session_depth=4),
        ]
        data = {date(2025, 6, 15): states}
        graph = build_causal_graph(data)
        assert graph.recovery_cost_buckets == 0.0
