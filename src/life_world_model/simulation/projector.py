from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from life_world_model.config import Settings
from life_world_model.simulation.engine import simulate
from life_world_model.storage.sqlite_store import SQLiteStore


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ProjectionDay:
    day_number: int
    date: date
    score: float
    delta_from_baseline: float
    habit_strength: float  # 0-1, increases with consistency


@dataclass
class TemporalProjection:
    intervention: str
    duration_days: int
    days: list[ProjectionDay]
    average_score: float
    trend: str  # "improving", "plateauing", "declining"
    habit_consolidation_day: int | None  # day when habit "locks in" (>0.8 strength)
    compound_effect: float  # total score improvement over the period
    summary: str


# ---------------------------------------------------------------------------
# Habit strength curve
# ---------------------------------------------------------------------------

DEFAULT_TIME_CONSTANT = 7  # habits strengthen over ~7 days


def habit_strength(days_practiced: int, time_constant: float = DEFAULT_TIME_CONSTANT) -> float:
    """Compute habit strength: 1 - e^(-days_practiced / time_constant)."""
    if days_practiced <= 0:
        return 0.0
    return 1.0 - math.exp(-days_practiced / time_constant)


# ---------------------------------------------------------------------------
# Adaptation effect
# ---------------------------------------------------------------------------


def adaptation_factor(day_number: int, strength: float) -> float:
    """Model novelty adaptation over time.

    First 3 days: full effect (1.0)
    Days 4-7: effect * 0.9 (slight adaptation)
    Days 8+: effect * 0.85 + habit_bonus * 0.15
    """
    if day_number <= 3:
        return 1.0
    if day_number <= 7:
        return 0.9
    return 0.85 + strength * 0.15


# ---------------------------------------------------------------------------
# Compound bonus
# ---------------------------------------------------------------------------


def compound_bonus(strength: float) -> float:
    """Consistent practice unlocks score bonuses.

    strength > 0.8: +5% bonus (habit consolidated)
    strength > 0.5: +2% bonus (routine established)
    otherwise: no bonus
    """
    if strength > 0.8:
        return 0.05
    if strength > 0.5:
        return 0.02
    return 0.0


# ---------------------------------------------------------------------------
# Trend detection
# ---------------------------------------------------------------------------


def detect_trend(days: list[ProjectionDay]) -> str:
    """Detect the overall trend from projection days.

    Compares average delta of the last third vs the first third.
    """
    if len(days) < 3:
        return "plateauing"

    third = max(1, len(days) // 3)
    first_avg = sum(d.delta_from_baseline for d in days[:third]) / third
    last_avg = sum(d.delta_from_baseline for d in days[-third:]) / third

    diff = last_avg - first_avg
    if diff > 0.005:  # >0.5% improvement
        return "improving"
    if diff < -0.005:
        return "declining"
    return "plateauing"


# ---------------------------------------------------------------------------
# Main projection function
# ---------------------------------------------------------------------------


def project_intervention(
    store: SQLiteStore,
    settings: Settings,
    intervention_text: str,
    duration_days: int = 14,
    weekdays_only: bool = True,
    time_constant: float = DEFAULT_TIME_CONSTANT,
) -> TemporalProjection:
    """Project the effect of an intervention over multiple days.

    Models:
    1. Habit strength curve: starts at 0, builds toward 1.0
       Formula: strength = 1 - e^(-days_practiced / time_constant)
       Default time_constant = 7 (habits strengthen over ~7 days)

    2. Adaptation effect: initial score boost may decrease as novelty wears off
       First 3 days: full effect
       Days 4-7: effect * 0.9 (slight adaptation)
       Days 8+: effect * 0.85 + habit_bonus * 0.15

    3. Compound effects: consistent practice unlocks bonuses
       If habit_strength > 0.5: +2% bonus (routine established)
       If habit_strength > 0.8: +5% bonus (habit consolidated)

    4. Weekend modeling: if weekdays_only, weekends show baseline scores
    """
    # Run the single-day simulation to get baseline and raw delta
    sim_result = simulate(store, settings, intervention_text)
    baseline_score = sim_result.baseline_score
    raw_delta = sim_result.score_delta  # raw single-day effect

    today = date.today()
    projection_days: list[ProjectionDay] = []
    days_practiced = 0
    consolidation_day: int | None = None

    for day_num in range(1, duration_days + 1):
        current_date = today + timedelta(days=day_num)
        weekday = current_date.weekday()  # 0=Mon, 6=Sun
        is_weekend = weekday >= 5

        if weekdays_only and is_weekend:
            # Weekend: baseline score, no practice, but habit doesn't decay
            projection_days.append(
                ProjectionDay(
                    day_number=day_num,
                    date=current_date,
                    score=baseline_score,
                    delta_from_baseline=0.0,
                    habit_strength=habit_strength(days_practiced, time_constant),
                )
            )
            continue

        days_practiced += 1
        strength = habit_strength(days_practiced, time_constant)
        adapt = adaptation_factor(days_practiced, strength)
        bonus = compound_bonus(strength)

        # Adjusted delta = raw_delta * adaptation + compound bonus
        adjusted_delta = raw_delta * adapt + bonus
        projected_score = baseline_score + adjusted_delta

        # Clamp to [0, 1]
        projected_score = max(0.0, min(1.0, projected_score))
        actual_delta = projected_score - baseline_score

        projection_days.append(
            ProjectionDay(
                day_number=day_num,
                date=current_date,
                score=projected_score,
                delta_from_baseline=actual_delta,
                habit_strength=strength,
            )
        )

        if consolidation_day is None and strength > 0.8:
            consolidation_day = day_num

    # Compute aggregate stats
    if projection_days:
        average_score = sum(d.score for d in projection_days) / len(projection_days)
    else:
        average_score = baseline_score

    trend = detect_trend(projection_days)
    compound_total = sum(d.delta_from_baseline for d in projection_days)

    summary = format_projection(
        intervention_text,
        duration_days,
        baseline_score,
        projection_days,
        trend,
        consolidation_day,
        average_score,
        compound_total,
    )

    return TemporalProjection(
        intervention=intervention_text,
        duration_days=duration_days,
        days=projection_days,
        average_score=average_score,
        trend=trend,
        habit_consolidation_day=consolidation_day,
        compound_effect=compound_total,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def _strength_bar(strength: float, width: int = 10) -> str:
    """Render a habit strength bar like: filled_empty  pct%."""
    filled = int(strength * width)
    empty = width - filled
    return "\u2593" * filled + "\u2591" * empty


def format_projection(
    intervention: str,
    duration_days: int,
    baseline_score: float,
    days: list[ProjectionDay],
    trend: str,
    consolidation_day: int | None,
    average_score: float,
    compound_total: float,
) -> str:
    """Format the projection for terminal display."""
    lines: list[str] = []
    lines.append(
        f"\u2501\u2501\u2501 PROJECTION: \"{intervention}\" over {duration_days} days \u2501\u2501\u2501"
    )
    lines.append("")
    lines.append(
        f"{'Day':>4s}  {'Date':<12s}  {'Score':>7s}  {'Delta':>7s}  {'Habit Strength'}"
    )

    for d in days:
        delta_str = f"+{d.delta_from_baseline:.1%}" if d.delta_from_baseline >= 0 else f"{d.delta_from_baseline:.1%}"
        bar = _strength_bar(d.habit_strength)
        pct = f"{d.habit_strength:.0%}"
        lines.append(
            f"{d.day_number:4d}  {d.date.isoformat():<12s}  {d.score:6.1%}  {delta_str:>7s}  {bar}  {pct}"
        )

    lines.append("")

    direction = "+" if compound_total >= 0 else ""
    lines.append(f"Trend: {trend.capitalize()} ({direction}{compound_total:.1%} compound effect)")

    if consolidation_day is not None:
        lines.append(f"Habit consolidation: Day {consolidation_day}")
    else:
        lines.append("Habit consolidation: not reached in this period")

    lines.append(f"Average score: {average_score:.1%} (baseline: {baseline_score:.1%})")

    return "\n".join(lines)
