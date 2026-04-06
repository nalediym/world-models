from __future__ import annotations

import math
from datetime import date, datetime

from life_world_model.goals.engine import DEFAULT_GOALS, load_goals
from life_world_model.scoring.formula import (
    _grade,
    decay_weight,
    format_score_report,
    score_day,
)
from life_world_model.types import LifeState


def _make_state(
    activity: str = "coding",
    context_switches: int | None = None,
    hour: int = 9,
    minute: int = 0,
) -> LifeState:
    return LifeState(
        timestamp=datetime(2026, 4, 6, hour, minute),
        primary_activity=activity,
        secondary_activity=None,
        domain=None,
        event_count=1,
        confidence=0.8,
        context_switches=context_switches,
    )


def test_score_day_all_productive() -> None:
    # 5 coding states with 0 context switches, no idle breaks
    # productive_focus_ratio = 5/5 = 1.0 (weight 0.4) -> 0.4
    # recovery_ratio = 0 idle / 5 total = 0.0 ratio -> 1 - abs(0-0.2)*3 = 0.4 (weight 0.3) -> 0.12
    # flow_score = 1 - 0/10 = 1.0 (weight 0.3) -> 0.3
    # total = 0.4 + 0.12 + 0.3 = 0.82
    states = [_make_state("coding", context_switches=0) for _ in range(5)]
    goals = load_goals()
    result = score_day(states, goals)
    assert result["total"] == 0.82
    assert result["grade"] == "A"
    assert result["metrics"]["goal_alignment"]["raw"] == 1.0
    assert result["metrics"]["flow"]["raw"] == 1.0


def test_score_day_all_idle() -> None:
    # 5 idle states, no context switches
    # productive_focus_ratio = 0/5 = 0.0 (weight 0.4) -> 0.0
    # recovery_ratio = 5/5 = 1.0 ratio -> 1 - abs(1.0-0.2)*3 = 1 - 2.4 = clamped to 0.0 (weight 0.3) -> 0.0
    # flow_score = 0.5 (unknown, no switches) (weight 0.3) -> 0.15
    states = [_make_state("idle") for _ in range(5)]
    goals = load_goals()
    result = score_day(states, goals)
    assert result["total"] == 0.15
    assert result["grade"] == "F"
    assert result["metrics"]["goal_alignment"]["raw"] == 0.0


def test_score_day_mixed() -> None:
    # 3 coding + 1 idle + 1 research, 2 context switches each
    # productive_focus_ratio = 4/5 = 0.8 (coding + research) (weight 0.4) -> 0.32
    # recovery_ratio = 1/5 = 0.2 ratio -> score = 1.0 (weight 0.3) -> 0.3
    # flow_score = 1 - 2/10 = 0.8 (weight 0.3) -> 0.24
    # total = 0.32 + 0.3 + 0.24 = 0.86
    states = [
        _make_state("coding", context_switches=2),
        _make_state("coding", context_switches=2),
        _make_state("coding", context_switches=2),
        _make_state("idle", context_switches=2),
        _make_state("research", context_switches=2),
    ]
    goals = load_goals()
    result = score_day(states, goals)
    assert result["total"] == 0.86
    assert result["grade"] == "A"


def test_score_day_empty_states() -> None:
    goals = load_goals()
    result = score_day([], goals)
    assert result["total"] == 0.0
    assert result["metrics"] == {}
    assert result["grade"] == "F"


def test_grade_boundaries() -> None:
    assert _grade(0.80) == "A"
    assert _grade(0.95) == "A"
    assert _grade(0.79) == "B"
    assert _grade(0.65) == "B"
    assert _grade(0.64) == "C"
    assert _grade(0.50) == "C"
    assert _grade(0.49) == "D"
    assert _grade(0.35) == "D"
    assert _grade(0.34) == "F"
    assert _grade(0.0) == "F"


def test_decay_weight_at_half_life() -> None:
    w = decay_weight(14.0, half_life=14.0)
    assert abs(w - 0.5) < 0.01


def test_decay_weight_at_zero_days() -> None:
    w = decay_weight(0.0)
    assert abs(w - 1.0) < 1e-9


def test_format_score_report() -> None:
    result = {
        "total": 0.75,
        "grade": "B",
        "metrics": {
            "goal_alignment": {"raw": 0.8, "weight": 0.4, "weighted": 0.32},
            "energy": {"raw": 0.7, "weight": 0.3, "weighted": 0.21},
            "flow": {"raw": 0.6, "weight": 0.3, "weighted": 0.18},
        },
    }
    report = format_score_report(result, date(2026, 4, 6))
    assert "2026-04-06" in report
    assert "75.0%" in report
    assert "(B)" in report
    assert "goal_alignment" in report
    assert "energy" in report
    assert "flow" in report
    # Check bar characters are present
    assert "\u2588" in report
    assert "\u2591" in report
