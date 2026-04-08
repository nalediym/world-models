"""Tests for Monte Carlo simulation engine."""

from __future__ import annotations

import random
from datetime import date, datetime, timezone

import pytest

from life_world_model.simulation.monte_carlo import (
    MonteCarloResult,
    _add_behavioral_noise,
    _ascii_histogram,
    _manual_stdev,
    _percentile,
    _weighted_sample_day,
    format_monte_carlo_report,
    monte_carlo_simulate_from_data,
)
from life_world_model.analysis.causal import CausalGraph, build_causal_graph
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


def _multi_day_dataset() -> dict[date, list[LifeState]]:
    """Build a realistic multi-day dataset for Monte Carlo testing.

    5 days of data with consistent patterns:
    - Morning: coding (8-11)
    - Midday: browsing (11-13)
    - Afternoon: coding or idle (13-16)
    """
    data: dict[date, list[LifeState]] = {}
    for d in range(15, 20):  # 5 days
        states = []
        for h in range(8, 12):
            states.append(_make_state(
                h, "coding", day=d,
                context_switches=1, session_depth=3, dwell_seconds=850.0,
            ))
        for h in range(12, 14):
            states.append(_make_state(
                h, "browsing", day=d,
                context_switches=4, session_depth=1, dwell_seconds=600.0,
            ))
        for h in range(14, 16):
            activity = "idle" if d % 2 == 0 else "coding"
            states.append(_make_state(
                h, activity, day=d,
                context_switches=2, session_depth=2, dwell_seconds=700.0,
            ))
        data[date(2025, 6, d)] = states
    return data


# ---------------------------------------------------------------------------
# MonteCarloResult structure tests
# ---------------------------------------------------------------------------


class TestMonteCarloResult:
    def test_result_fields(self):
        """MonteCarloResult has all required fields."""
        result = MonteCarloResult(
            intervention="code from 8-10am",
            num_simulations=50,
            mean_score=0.65,
            median_score=0.64,
            std_dev=0.05,
            p5_score=0.55,
            p95_score=0.75,
            confidence=0.8,
            baseline_score=0.6,
            score_distribution=[0.55, 0.6, 0.65, 0.7, 0.75],
        )
        assert result.intervention == "code from 8-10am"
        assert result.num_simulations == 50
        assert result.mean_score == 0.65
        assert result.median_score == 0.64
        assert result.std_dev == 0.05
        assert result.p5_score == 0.55
        assert result.p95_score == 0.75
        assert result.confidence == 0.8
        assert result.baseline_score == 0.6
        assert len(result.score_distribution) == 5

    def test_result_default_distribution(self):
        """Default score_distribution is empty list."""
        result = MonteCarloResult(
            intervention="test",
            num_simulations=0,
            mean_score=0.0,
            median_score=0.0,
            std_dev=0.0,
            p5_score=0.0,
            p95_score=0.0,
            confidence=0.0,
            baseline_score=0.0,
        )
        assert result.score_distribution == []


# ---------------------------------------------------------------------------
# Monte Carlo simulation with mock data
# ---------------------------------------------------------------------------


class TestMonteCarloSimulation:
    def test_basic_simulation(self):
        """Monte Carlo simulation runs and returns valid result."""
        data = _multi_day_dataset()
        result = monte_carlo_simulate_from_data(
            data,
            "code from 8-10am",
            num_simulations=20,
            seed=42,
        )

        assert result.num_simulations == 20
        assert len(result.score_distribution) == 20
        assert result.mean_score >= 0.0
        assert result.median_score >= 0.0
        assert result.std_dev >= 0.0
        assert 0.0 <= result.confidence <= 1.0
        assert result.baseline_score >= 0.0

    def test_deterministic_with_seed(self):
        """Same seed produces identical results."""
        data = _multi_day_dataset()
        result1 = monte_carlo_simulate_from_data(
            data, "code from 8-10am", num_simulations=30, seed=123,
        )
        result2 = monte_carlo_simulate_from_data(
            data, "code from 8-10am", num_simulations=30, seed=123,
        )

        assert result1.mean_score == result2.mean_score
        assert result1.median_score == result2.median_score
        assert result1.std_dev == result2.std_dev
        assert result1.score_distribution == result2.score_distribution

    def test_different_seeds_differ(self):
        """Different seeds produce different results."""
        data = _multi_day_dataset()
        result1 = monte_carlo_simulate_from_data(
            data, "code from 8-10am", num_simulations=30, seed=1,
        )
        result2 = monte_carlo_simulate_from_data(
            data, "code from 8-10am", num_simulations=30, seed=999,
        )

        # With different seeds, distributions should differ
        # (extremely unlikely to be identical)
        assert result1.score_distribution != result2.score_distribution

    def test_num_simulations_parameter(self):
        """num_simulations controls how many runs happen."""
        data = _multi_day_dataset()

        result_10 = monte_carlo_simulate_from_data(
            data, "stop browsing", num_simulations=10, seed=42,
        )
        result_50 = monte_carlo_simulate_from_data(
            data, "stop browsing", num_simulations=50, seed=42,
        )

        assert result_10.num_simulations == 10
        assert len(result_10.score_distribution) == 10
        assert result_50.num_simulations == 50
        assert len(result_50.score_distribution) == 50

    def test_empty_data(self):
        """Empty data produces zero result."""
        result = monte_carlo_simulate_from_data(
            {},
            "code from 8-10am",
            num_simulations=10,
            seed=42,
        )
        assert result.mean_score == 0.0
        assert result.score_distribution == []
        assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# Confidence calculation
# ---------------------------------------------------------------------------


class TestConfidence:
    def test_confidence_bounds(self):
        """Confidence is between 0 and 1."""
        data = _multi_day_dataset()
        result = monte_carlo_simulate_from_data(
            data, "code from 8-10am", num_simulations=20, seed=42,
        )
        assert 0.0 <= result.confidence <= 1.0

    def test_high_confidence_for_good_intervention(self):
        """An intervention replacing browsing with coding should have nonzero confidence."""
        data = _multi_day_dataset()
        result = monte_carlo_simulate_from_data(
            data, "code from 12-14",  # replace browsing with coding
            num_simulations=50,
            seed=42,
        )
        # We expect some simulations to improve since we're replacing
        # browsing (non-productive) with coding (productive)
        assert result.confidence > 0.0


# ---------------------------------------------------------------------------
# Percentile calculations
# ---------------------------------------------------------------------------


class TestPercentiles:
    def test_p5_less_than_p95(self):
        """5th percentile is always <= 95th percentile."""
        data = _multi_day_dataset()
        result = monte_carlo_simulate_from_data(
            data, "code from 8-10am", num_simulations=50, seed=42,
        )
        assert result.p5_score <= result.p95_score

    def test_median_between_extremes(self):
        """Median is between p5 and p95."""
        data = _multi_day_dataset()
        result = monte_carlo_simulate_from_data(
            data, "code from 8-10am", num_simulations=50, seed=42,
        )
        assert result.p5_score <= result.median_score <= result.p95_score

    def test_percentile_function_basic(self):
        """_percentile computes correctly for known data."""
        data = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert _percentile(data, 0) == 10.0
        assert _percentile(data, 50) == 30.0
        assert _percentile(data, 100) == 50.0

    def test_percentile_empty(self):
        """_percentile returns 0 for empty data."""
        assert _percentile([], 50) == 0.0

    def test_percentile_single_value(self):
        """_percentile returns the value for single-element data."""
        assert _percentile([42.0], 0) == 42.0
        assert _percentile([42.0], 50) == 42.0
        assert _percentile([42.0], 100) == 42.0

    def test_percentile_interpolation(self):
        """_percentile interpolates between values."""
        data = [0.0, 100.0]
        assert _percentile(data, 50) == 50.0
        assert _percentile(data, 25) == 25.0
        assert _percentile(data, 75) == 75.0


# ---------------------------------------------------------------------------
# Manual stdev
# ---------------------------------------------------------------------------


class TestManualStdev:
    def test_known_stdev(self):
        """Manual stdev matches known value."""
        # stdev of [2, 4, 4, 4, 5, 5, 7, 9] is approximately 2.138
        data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        result = _manual_stdev(data)
        assert abs(result - 2.138) < 0.01

    def test_zero_stdev(self):
        """Identical values have zero stdev."""
        data = [5.0, 5.0, 5.0]
        assert _manual_stdev(data) == 0.0

    def test_single_value(self):
        """Single value returns 0."""
        assert _manual_stdev([5.0]) == 0.0

    def test_empty(self):
        """Empty list returns 0."""
        assert _manual_stdev([]) == 0.0


# ---------------------------------------------------------------------------
# Weighted day sampling
# ---------------------------------------------------------------------------


class TestWeightedSampling:
    def test_recent_days_preferred(self):
        """More recent days should be sampled more frequently."""
        data = _multi_day_dataset()
        ref_date = date(2025, 6, 20)

        rng = random.Random(42)
        counts: dict[date, int] = {}
        for _ in range(500):
            d, _ = _weighted_sample_day(data, ref_date, rng)
            counts[d] = counts.get(d, 0) + 1

        # Most recent day (June 19) should be sampled more than oldest (June 15)
        assert counts.get(date(2025, 6, 19), 0) > counts.get(date(2025, 6, 15), 0)

    def test_empty_data_raises(self):
        """Empty data raises ValueError."""
        rng = random.Random(42)
        with pytest.raises(ValueError):
            _weighted_sample_day({}, date(2025, 6, 20), rng)


# ---------------------------------------------------------------------------
# Behavioral noise
# ---------------------------------------------------------------------------


class TestBehavioralNoise:
    def test_noise_modifies_metrics(self):
        """Adding noise changes at least some metric values."""
        data = _multi_day_dataset()
        graph = build_causal_graph(data)

        states = [
            _make_state(8, "coding", context_switches=2, session_depth=3, dwell_seconds=800.0),
            _make_state(9, "coding", context_switches=2, session_depth=3, dwell_seconds=800.0),
        ]

        rng = random.Random(42)
        noisy = _add_behavioral_noise(states, graph, rng)

        # At least one metric should have changed
        any_changed = False
        for i in range(len(states)):
            if (
                noisy[i].context_switches != states[i].context_switches
                or noisy[i].session_depth != states[i].session_depth
                or noisy[i].dwell_seconds != states[i].dwell_seconds
            ):
                any_changed = True
                break
        assert any_changed, "Noise should change at least one metric"

    def test_noise_nonnegative(self):
        """Noisy metrics should remain non-negative."""
        data = _multi_day_dataset()
        graph = build_causal_graph(data)

        states = [
            _make_state(8, "coding", context_switches=0, session_depth=1, dwell_seconds=10.0),
        ]

        rng = random.Random(42)
        for _ in range(50):  # Run many times to test bounds
            noisy = _add_behavioral_noise(states, graph, rng)
            assert noisy[0].context_switches >= 0
            assert noisy[0].session_depth >= 1
            assert noisy[0].dwell_seconds >= 0.0


# ---------------------------------------------------------------------------
# Format report
# ---------------------------------------------------------------------------


class TestFormatReport:
    def test_report_contains_key_elements(self):
        """Report includes intervention, baseline, distribution, and confidence."""
        result = MonteCarloResult(
            intervention="Code from 8-10am",
            num_simulations=100,
            mean_score=0.691,
            median_score=0.687,
            std_dev=0.054,
            p5_score=0.583,
            p95_score=0.782,
            confidence=0.87,
            baseline_score=0.62,
            score_distribution=[0.5 + i * 0.003 for i in range(100)],
        )
        report = format_monte_carlo_report(result)

        assert "MONTE CARLO SIMULATION" in report
        assert "100 runs" in report
        assert "Code from 8-10am" in report
        assert "Baseline" in report
        assert "62.0%" in report
        assert "Worst case" in report
        assert "Median" in report
        assert "Mean" in report
        assert "Best case" in report
        assert "Std dev" in report
        assert "Confidence" in report
        assert "87%" in report

    def test_report_histogram(self):
        """Report includes a histogram when scores are available."""
        result = MonteCarloResult(
            intervention="test",
            num_simulations=20,
            mean_score=0.5,
            median_score=0.5,
            std_dev=0.1,
            p5_score=0.3,
            p95_score=0.7,
            confidence=0.5,
            baseline_score=0.5,
            score_distribution=[0.3 + i * 0.02 for i in range(20)],
        )
        report = format_monte_carlo_report(result)
        # Histogram uses block characters
        assert "\u2588" in report

    def test_report_empty_distribution(self):
        """Report with empty distribution still renders without error."""
        result = MonteCarloResult(
            intervention="test",
            num_simulations=0,
            mean_score=0.0,
            median_score=0.0,
            std_dev=0.0,
            p5_score=0.0,
            p95_score=0.0,
            confidence=0.0,
            baseline_score=0.0,
            score_distribution=[],
        )
        report = format_monte_carlo_report(result)
        assert "MONTE CARLO SIMULATION" in report


# ---------------------------------------------------------------------------
# ASCII histogram
# ---------------------------------------------------------------------------


class TestAsciiHistogram:
    def test_histogram_renders(self):
        """Histogram produces non-empty output."""
        scores = [0.5 + i * 0.01 for i in range(50)]
        result = _ascii_histogram(scores)
        assert len(result) > 0
        assert "\u2588" in result

    def test_histogram_empty(self):
        """Empty scores produce empty histogram."""
        assert _ascii_histogram([]) == ""

    def test_histogram_single_value(self):
        """Single value produces a full bar."""
        result = _ascii_histogram([0.5])
        assert "\u2588" in result
