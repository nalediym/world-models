from __future__ import annotations

import math
from datetime import date

from life_world_model.goals.engine import compute_metric
from life_world_model.types import Goal, LifeState


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
