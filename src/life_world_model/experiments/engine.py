from __future__ import annotations

import hashlib
from datetime import date, timedelta

from life_world_model.config import load_settings
from life_world_model.goals.engine import load_goals
from life_world_model.pipeline.bucketizer import build_life_states
from life_world_model.scoring.formula import score_day
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import Experiment, ExperimentStatus


def _make_id(description: str, start: date) -> str:
    import time

    key = f"{description}:{start.isoformat()}:{time.monotonic_ns()}"
    return hashlib.sha256(key.encode()).hexdigest()[:8]


def start_experiment(
    store: SQLiteStore,
    description: str,
    intervention: str,
    duration_days: int = 3,
    start_date: date | None = None,
) -> Experiment:
    """Create a new experiment. Computes baseline score from the pre-experiment period."""
    start = start_date or date.today()
    settings = load_settings()
    goals = load_goals()

    # Baseline: average score over the `duration_days` before the experiment
    baseline_scores: list[float] = []
    for days_ago in range(1, duration_days + 1):
        d = start - timedelta(days=days_ago)
        events = store.load_raw_events_for_date(d)
        if events:
            states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
            if states:
                result = score_day(states, goals)
                baseline_scores.append(result["total"])

    baseline = sum(baseline_scores) / len(baseline_scores) if baseline_scores else None

    exp = Experiment(
        id=_make_id(description, start),
        description=description,
        intervention=intervention,
        duration_days=duration_days,
        start_date=start,
        baseline_score=baseline,
    )
    store.save_experiment(exp)
    return exp


def check_experiment_status(
    store: SQLiteStore,
    exp: Experiment,
) -> Experiment:
    """Check whether an experiment is done and compute results if so."""
    if exp.status != ExperimentStatus.ACTIVE:
        return exp

    end_date = exp.start_date + timedelta(days=exp.duration_days)
    today = date.today()

    if today < end_date:
        return exp  # still running

    # Experiment period is over — compute result score
    settings = load_settings()
    goals = load_goals()

    experiment_scores: list[float] = []
    current = exp.start_date
    while current < end_date:
        events = store.load_raw_events_for_date(current)
        if events:
            states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
            if states:
                result = score_day(states, goals)
                experiment_scores.append(result["total"])
        current += timedelta(days=1)

    if not experiment_scores:
        exp.status = ExperimentStatus.COMPLETED
        exp.result_summary = "No data collected during experiment period."
        store.update_experiment(exp)
        return exp

    result_score = sum(experiment_scores) / len(experiment_scores)
    exp.result_score = result_score
    exp.status = ExperimentStatus.COMPLETED

    if exp.baseline_score is not None:
        delta = result_score - exp.baseline_score
        direction = "+" if delta >= 0 else ""
        exp.result_summary = (
            f"Baseline: {exp.baseline_score:.1%} -> Result: {result_score:.1%} "
            f"({direction}{delta:.1%}) over {len(experiment_scores)} days"
        )
    else:
        exp.result_summary = (
            f"Result: {result_score:.1%} over {len(experiment_scores)} days "
            f"(no baseline data to compare)"
        )

    store.update_experiment(exp)
    return exp


def cancel_experiment(store: SQLiteStore, exp: Experiment) -> Experiment:
    exp.status = ExperimentStatus.CANCELLED
    store.update_experiment(exp)
    return exp


def format_experiment_status(exp: Experiment) -> str:
    """Format an experiment for display."""
    lines: list[str] = []
    lines.append(f"[{exp.id}] {exp.description}")
    lines.append(f"  Intervention: {exp.intervention}")
    lines.append(f"  Period: {exp.start_date} to {exp.start_date + timedelta(days=exp.duration_days)}")
    lines.append(f"  Status: {exp.status.value}")

    if exp.baseline_score is not None:
        lines.append(f"  Baseline score: {exp.baseline_score:.1%}")

    if exp.status == ExperimentStatus.ACTIVE:
        today = date.today()
        days_left = (exp.start_date + timedelta(days=exp.duration_days) - today).days
        lines.append(f"  Days remaining: {max(0, days_left)}")

    if exp.result_score is not None:
        lines.append(f"  Result score: {exp.result_score:.1%}")

    if exp.result_summary:
        lines.append(f"  Summary: {exp.result_summary}")

    return "\n".join(lines)
