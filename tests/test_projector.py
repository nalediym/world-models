from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from life_world_model.simulation.projector import (
    ProjectionDay,
    TemporalProjection,
    adaptation_factor,
    compound_bonus,
    detect_trend,
    format_projection,
    habit_strength,
    project_intervention,
)


# ---------------------------------------------------------------------------
# Habit strength curve
# ---------------------------------------------------------------------------


class TestHabitStrength:
    def test_zero_days(self):
        assert habit_strength(0) == 0.0

    def test_negative_days(self):
        assert habit_strength(-5) == 0.0

    def test_one_day(self):
        expected = 1.0 - math.exp(-1 / 7)
        assert abs(habit_strength(1) - expected) < 1e-9

    def test_seven_days(self):
        """At time_constant=7, 7 days => 1 - e^(-1) ~ 0.632."""
        expected = 1.0 - math.exp(-1.0)
        assert abs(habit_strength(7) - expected) < 1e-9

    def test_monotonically_increasing(self):
        prev = 0.0
        for d in range(1, 30):
            s = habit_strength(d)
            assert s > prev
            prev = s

    def test_approaches_one(self):
        assert habit_strength(100) > 0.99

    def test_custom_time_constant(self):
        """Faster habit formation with smaller time constant."""
        fast = habit_strength(3, time_constant=3)
        slow = habit_strength(3, time_constant=14)
        assert fast > slow


# ---------------------------------------------------------------------------
# Adaptation effect
# ---------------------------------------------------------------------------


class TestAdaptationFactor:
    def test_first_three_days(self):
        for d in range(1, 4):
            assert adaptation_factor(d, 0.5) == 1.0

    def test_days_four_to_seven(self):
        for d in range(4, 8):
            assert adaptation_factor(d, 0.5) == 0.9

    def test_day_eight_plus_with_low_strength(self):
        factor = adaptation_factor(10, 0.0)
        assert factor == 0.85

    def test_day_eight_plus_with_high_strength(self):
        factor = adaptation_factor(10, 1.0)
        assert factor == pytest.approx(1.0)

    def test_day_eight_plus_mid_strength(self):
        factor = adaptation_factor(10, 0.5)
        expected = 0.85 + 0.5 * 0.15
        assert factor == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Compound bonus
# ---------------------------------------------------------------------------


class TestCompoundBonus:
    def test_no_bonus_below_half(self):
        assert compound_bonus(0.0) == 0.0
        assert compound_bonus(0.3) == 0.0
        assert compound_bonus(0.5) == 0.0

    def test_routine_bonus(self):
        assert compound_bonus(0.51) == 0.02
        assert compound_bonus(0.7) == 0.02
        assert compound_bonus(0.8) == 0.02

    def test_consolidated_bonus(self):
        assert compound_bonus(0.81) == 0.05
        assert compound_bonus(1.0) == 0.05


# ---------------------------------------------------------------------------
# Trend detection
# ---------------------------------------------------------------------------


class TestDetectTrend:
    def _make_days(self, deltas: list[float]) -> list[ProjectionDay]:
        today = date(2026, 4, 7)
        return [
            ProjectionDay(
                day_number=i + 1,
                date=today + timedelta(days=i + 1),
                score=0.6 + d,
                delta_from_baseline=d,
                habit_strength=0.5,
            )
            for i, d in enumerate(deltas)
        ]

    def test_improving(self):
        # First third: low delta, last third: high delta
        deltas = [0.01, 0.01, 0.01, 0.03, 0.05, 0.05, 0.08, 0.10, 0.10]
        assert detect_trend(self._make_days(deltas)) == "improving"

    def test_declining(self):
        deltas = [0.10, 0.10, 0.10, 0.05, 0.05, 0.03, 0.01, 0.01, 0.01]
        assert detect_trend(self._make_days(deltas)) == "declining"

    def test_plateauing(self):
        deltas = [0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05]
        assert detect_trend(self._make_days(deltas)) == "plateauing"

    def test_too_few_days(self):
        deltas = [0.01, 0.10]
        assert detect_trend(self._make_days(deltas)) == "plateauing"


# ---------------------------------------------------------------------------
# Integration: project_intervention with mock simulate
# ---------------------------------------------------------------------------


class TestProjectIntervention:
    def _mock_simulate(self, baseline: float = 0.62, delta: float = 0.09):
        """Return a mock SimulationResult."""
        result = MagicMock()
        result.baseline_score = baseline
        result.score_delta = delta
        return result

    @patch("life_world_model.simulation.projector.simulate")
    def test_fourteen_day_projection(self, mock_sim):
        mock_sim.return_value = self._mock_simulate()
        store = MagicMock()
        settings = MagicMock()

        proj = project_intervention(
            store, settings, "code from 8-10am", duration_days=14
        )

        assert proj.intervention == "code from 8-10am"
        assert proj.duration_days == 14
        assert len(proj.days) == 14
        assert isinstance(proj.average_score, float)
        assert proj.trend in ("improving", "plateauing", "declining")
        assert isinstance(proj.compound_effect, float)
        assert isinstance(proj.summary, str)

    @patch("life_world_model.simulation.projector.simulate")
    @patch("life_world_model.simulation.projector.date")
    def test_weekdays_only_skips_weekends(self, mock_date, mock_sim):
        mock_sim.return_value = self._mock_simulate()
        # Set today to Monday 2026-04-06
        mock_date.today.return_value = date(2026, 4, 6)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        store = MagicMock()
        settings = MagicMock()

        proj = project_intervention(
            store, settings, "code from 8-10am",
            duration_days=14, weekdays_only=True,
        )

        # Weekend days (Sat=Apr 11,12 and Apr 18,19) should have delta=0
        for d in proj.days:
            if d.date.weekday() >= 5:
                assert d.delta_from_baseline == 0.0, (
                    f"Day {d.day_number} ({d.date}, weekday={d.date.weekday()}) "
                    f"should have zero delta on weekend"
                )

    @patch("life_world_model.simulation.projector.simulate")
    def test_weekdays_only_false_includes_weekends(self, mock_sim):
        mock_sim.return_value = self._mock_simulate()
        store = MagicMock()
        settings = MagicMock()

        proj = project_intervention(
            store, settings, "code from 8-10am",
            duration_days=14, weekdays_only=False,
        )

        # All days should have non-zero deltas (because delta is 0.09)
        for d in proj.days:
            assert d.delta_from_baseline > 0.0

    @patch("life_world_model.simulation.projector.simulate")
    def test_habit_consolidation_day(self, mock_sim):
        mock_sim.return_value = self._mock_simulate()
        store = MagicMock()
        settings = MagicMock()

        proj = project_intervention(
            store, settings, "code from 8-10am",
            duration_days=30, weekdays_only=False, time_constant=7,
        )

        # With time_constant=7, strength > 0.8 around day 11-12
        # (1 - e^(-d/7) > 0.8 => d > 7 * ln(5) ~ 11.3)
        if proj.habit_consolidation_day is not None:
            assert 10 <= proj.habit_consolidation_day <= 15

    @patch("life_world_model.simulation.projector.simulate")
    def test_compound_effect_positive_for_positive_delta(self, mock_sim):
        mock_sim.return_value = self._mock_simulate(delta=0.1)
        store = MagicMock()
        settings = MagicMock()

        proj = project_intervention(
            store, settings, "code from 8-10am",
            duration_days=7, weekdays_only=False,
        )

        assert proj.compound_effect > 0.0

    @patch("life_world_model.simulation.projector.simulate")
    def test_scores_clamped_to_zero_one(self, mock_sim):
        # Extreme delta that would push score above 1.0
        mock_sim.return_value = self._mock_simulate(baseline=0.95, delta=0.5)
        store = MagicMock()
        settings = MagicMock()

        proj = project_intervention(
            store, settings, "code from 8-10am",
            duration_days=7, weekdays_only=False,
        )

        for d in proj.days:
            assert 0.0 <= d.score <= 1.0


# ---------------------------------------------------------------------------
# Format output
# ---------------------------------------------------------------------------


class TestFormatProjection:
    def test_format_contains_key_elements(self):
        days = [
            ProjectionDay(
                day_number=1,
                date=date(2026, 4, 8),
                score=0.71,
                delta_from_baseline=0.09,
                habit_strength=0.12,
            ),
            ProjectionDay(
                day_number=2,
                date=date(2026, 4, 9),
                score=0.705,
                delta_from_baseline=0.085,
                habit_strength=0.22,
            ),
        ]

        output = format_projection(
            intervention="Code 8-10am",
            duration_days=14,
            baseline_score=0.62,
            days=days,
            trend="improving",
            consolidation_day=11,
            average_score=0.718,
            compound_total=0.035,
        )

        assert "PROJECTION" in output
        assert "Code 8-10am" in output
        assert "14 days" in output
        assert "Improving" in output
        assert "Day 11" in output
        assert "baseline" in output.lower()

    def test_format_no_consolidation(self):
        days = [
            ProjectionDay(
                day_number=1,
                date=date(2026, 4, 8),
                score=0.63,
                delta_from_baseline=0.01,
                habit_strength=0.1,
            ),
        ]

        output = format_projection(
            intervention="walk at lunch",
            duration_days=3,
            baseline_score=0.62,
            days=days,
            trend="plateauing",
            consolidation_day=None,
            average_score=0.63,
            compound_total=0.01,
        )

        assert "not reached" in output
