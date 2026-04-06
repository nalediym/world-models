from __future__ import annotations

from datetime import datetime

from life_world_model.goals.engine import (
    DEFAULT_GOALS,
    compute_metric,
    load_goals,
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


def test_default_goals_weights_sum_to_one() -> None:
    goals = load_goals()
    total = sum(g.weight for g in goals)
    assert abs(total - 1.0) < 1e-9


def test_compute_productive_focus_ratio() -> None:
    # 3 coding + 2 idle = 3/5 = 0.6
    states = [
        _make_state("coding"),
        _make_state("coding"),
        _make_state("coding"),
        _make_state("idle"),
        _make_state("idle"),
    ]
    result = compute_metric(states, "productive_focus_ratio")
    assert abs(result - 0.6) < 1e-9


def test_compute_recovery_ratio_ideal() -> None:
    # 1 idle + 4 coding = 0.2 ratio -> score should be ~1.0
    states = [
        _make_state("idle"),
        _make_state("coding"),
        _make_state("coding"),
        _make_state("coding"),
        _make_state("coding"),
    ]
    result = compute_metric(states, "recovery_ratio")
    assert abs(result - 1.0) < 1e-9


def test_compute_recovery_ratio_no_breaks() -> None:
    # 0 idle out of 5 = 0.0 ratio -> score = 1 - 0.2*3 = 0.4
    states = [_make_state("coding") for _ in range(5)]
    result = compute_metric(states, "recovery_ratio")
    assert abs(result - 0.4) < 1e-9


def test_compute_flow_score_no_switches() -> None:
    # All 0 switches -> 1 - 0/10 = 1.0
    states = [_make_state("coding", context_switches=0) for _ in range(5)]
    result = compute_metric(states, "flow_score")
    assert abs(result - 1.0) < 1e-9


def test_compute_flow_score_high_switches() -> None:
    # All 10+ switches -> 1 - 10/10 = 0.0
    states = [_make_state("coding", context_switches=10) for _ in range(5)]
    result = compute_metric(states, "flow_score")
    assert abs(result - 0.0) < 1e-9


def test_compute_metric_unknown_returns_zero() -> None:
    states = [_make_state("coding")]
    result = compute_metric(states, "nonexistent_metric")
    assert result == 0.0


def test_compute_metric_empty_states() -> None:
    assert compute_metric([], "productive_focus_ratio") == 0.0
    assert compute_metric([], "recovery_ratio") == 0.0
    assert compute_metric([], "flow_score") == 0.0
    assert compute_metric([], "nonexistent_metric") == 0.0
