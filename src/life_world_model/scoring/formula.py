from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from life_world_model.goals.engine import compute_metric
from life_world_model.types import Goal, LifeState


@dataclass
class ScoreBreakdown:
    total: float
    grade: str
    per_goal: dict[str, dict]  # goal_name -> {"raw", "weight", "weighted"}
    trade_offs: list[str] = field(default_factory=list)
    pareto_optimal: bool = True


def score_day(states: list[LifeState], goals: list[Goal]) -> dict:
    """Score a day against user goals. Returns detailed breakdown."""
    if not states:
        return {"total": 0.0, "metrics": {}, "grade": "F"}

    metrics: dict[str, dict] = {}
    total = 0.0
    for goal in goals:
        value = compute_metric(states, goal.metric)
        weighted = value * goal.weight
        total += weighted
        metrics[goal.name] = {
            "raw": round(value, 3),
            "weight": goal.weight,
            "weighted": round(weighted, 3),
        }

    total = round(total, 3)
    grade = _grade(total)

    return {"total": total, "metrics": metrics, "grade": grade}


def _grade(score: float) -> str:
    if score >= 0.8:
        return "A"
    if score >= 0.65:
        return "B"
    if score >= 0.5:
        return "C"
    if score >= 0.35:
        return "D"
    return "F"


def decay_weight(days_ago: float, half_life: float = 14.0) -> float:
    """Exponential temporal decay. Default 2-week half-life, tunable from data."""
    return math.exp(-0.693 * days_ago / half_life)


def format_score_report(result: dict, target_date: date | None = None) -> str:
    """Format score as human-readable text."""
    lines: list[str] = []
    if target_date:
        lines.append(
            f"Day Score for {target_date}: {result['total']:.1%} ({result['grade']})"
        )
    else:
        lines.append(f"Day Score: {result['total']:.1%} ({result['grade']})")
    lines.append("")
    for name, m in result["metrics"].items():
        bar = "\u2588" * int(m["raw"] * 10) + "\u2591" * (10 - int(m["raw"] * 10))
        lines.append(
            f"  {name:20s} {bar} {m['raw']:.0%} (weight: {m['weight']:.0%})"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Multi-objective scoring with trade-off detection
# ---------------------------------------------------------------------------

# Known competing metric pairs: improving one tends to decrease the other.
# Each entry is (goal_metric_a, goal_metric_b, description).
_COMPETING_METRICS: list[tuple[str, str, str]] = [
    (
        "productive_focus_ratio",
        "recovery_ratio",
        "More productive time trades off with recovery breaks",
    ),
    (
        "productive_focus_ratio",
        "flow_score",
        "More coding time can increase context-switching if spread across tasks",
    ),
]


def _detect_trade_offs(
    per_goal: dict[str, dict], goals: list[Goal]
) -> list[str]:
    """Detect trade-offs: when one goal is strong but a competing goal is weak."""
    trade_offs: list[str] = []
    metric_to_goal: dict[str, str] = {g.metric: g.name for g in goals}
    metric_to_raw: dict[str, float] = {}
    for g in goals:
        goal_data = per_goal.get(g.name)
        if goal_data:
            metric_to_raw[g.metric] = goal_data["raw"]

    for metric_a, metric_b, desc in _COMPETING_METRICS:
        raw_a = metric_to_raw.get(metric_a)
        raw_b = metric_to_raw.get(metric_b)
        if raw_a is None or raw_b is None:
            continue
        # Trade-off exists when one is strong (>0.7) and the other is weak (<0.4)
        if raw_a > 0.7 and raw_b < 0.4:
            goal_a = metric_to_goal.get(metric_a, metric_a)
            goal_b = metric_to_goal.get(metric_b, metric_b)
            trade_offs.append(
                f"{goal_a} is strong ({raw_a:.0%}) but {goal_b} is weak ({raw_b:.0%}): {desc}"
            )
        elif raw_b > 0.7 and raw_a < 0.4:
            goal_a = metric_to_goal.get(metric_a, metric_a)
            goal_b = metric_to_goal.get(metric_b, metric_b)
            trade_offs.append(
                f"{goal_b} is strong ({raw_b:.0%}) but {goal_a} is weak ({raw_a:.0%}): {desc}"
            )

    return trade_offs


def _is_pareto_optimal(per_goal: dict[str, dict]) -> bool:
    """A day is Pareto-optimal if no single goal can improve without another declining.

    Heuristic: if all goals are above 0.5, consider it Pareto-optimal (balanced).
    If any goal is below 0.3, it's clearly not optimal.
    """
    raw_values = [g["raw"] for g in per_goal.values()]
    if not raw_values:
        return True
    return all(v >= 0.3 for v in raw_values)


def score_day_detailed(
    states: list[LifeState], goals: list[Goal]
) -> ScoreBreakdown:
    """Score a day with per-goal breakdown, trade-off detection, and Pareto check."""
    if not states:
        return ScoreBreakdown(
            total=0.0,
            grade="F",
            per_goal={},
            trade_offs=[],
            pareto_optimal=True,
        )

    per_goal: dict[str, dict] = {}
    total = 0.0
    for goal in goals:
        value = compute_metric(states, goal.metric)
        weighted = value * goal.weight
        total += weighted
        per_goal[goal.name] = {
            "raw": round(value, 3),
            "weight": goal.weight,
            "weighted": round(weighted, 3),
        }

    total = round(total, 3)
    grade = _grade(total)
    trade_offs = _detect_trade_offs(per_goal, goals)
    pareto = _is_pareto_optimal(per_goal)

    return ScoreBreakdown(
        total=total,
        grade=grade,
        per_goal=per_goal,
        trade_offs=trade_offs,
        pareto_optimal=pareto,
    )


def format_detailed_report(
    breakdown: ScoreBreakdown, target_date: date | None = None
) -> str:
    """Format a ScoreBreakdown as human-readable text with per-goal bars and trade-offs."""
    lines: list[str] = []
    if target_date:
        lines.append(
            f"Day Score for {target_date}: {breakdown.total:.1%} ({breakdown.grade})"
        )
    else:
        lines.append(f"Day Score: {breakdown.total:.1%} ({breakdown.grade})")

    pareto_label = "yes" if breakdown.pareto_optimal else "no"
    lines.append(f"Pareto-optimal: {pareto_label}")
    lines.append("")

    for name, m in breakdown.per_goal.items():
        bar = "\u2588" * int(m["raw"] * 10) + "\u2591" * (10 - int(m["raw"] * 10))
        lines.append(
            f"  {name:20s} {bar} {m['raw']:.0%} (weight: {m['weight']:.0%})"
        )

    if breakdown.trade_offs:
        lines.append("")
        lines.append("Trade-offs detected:")
        for t in breakdown.trade_offs:
            lines.append(f"  - {t}")

    return "\n".join(lines)
