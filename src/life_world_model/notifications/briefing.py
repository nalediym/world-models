from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from life_world_model.analysis.pattern_discovery import discover_patterns
from life_world_model.analysis.suggestions import generate_suggestions
from life_world_model.config import load_settings
from life_world_model.goals.engine import load_goals
from life_world_model.notifications.macos import send_notification
from life_world_model.pipeline.bucketizer import build_life_states
from life_world_model.scoring.formula import score_day
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import ExperimentStatus


def morning_briefing() -> str:
    """Score yesterday, include experiments + top suggestion, send notification."""
    settings = load_settings()
    store = SQLiteStore(settings.database_path)

    yesterday = date.today() - timedelta(days=1)
    events = store.load_raw_events_for_date(yesterday)

    if not events:
        msg = f"No data for {yesterday}. Run 'lwm collect' to gather activity."
        send_notification("LWM Morning Briefing", msg)
        return msg

    states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
    goals = load_goals()
    result = score_day(states, goals)

    total = result["total"]
    grade = result["grade"]

    # Top activity by bucket count
    activity_counts = Counter(s.primary_activity for s in states)
    top_activity, top_count = activity_counts.most_common(1)[0]
    top_hours = top_count * settings.bucket_minutes / 60

    # Context switches
    switches = sum(
        s.context_switches for s in states if s.context_switches is not None
    )

    lines = [
        f"Yesterday: {total:.0%} ({grade}) | "
        f"Top: {top_activity} ({top_hours:.1f}hrs) | "
        f"{switches} switches"
    ]

    # Active experiments
    active = store.load_experiments(status=ExperimentStatus.ACTIVE)
    if active:
        exp = active[0]
        end_date = exp.start_date + timedelta(days=exp.duration_days)
        days_left = (end_date - date.today()).days
        lines.append(f"Experiment: {exp.description} ({max(0, days_left)}d left)")

    # Top suggestion
    patterns = store.load_patterns()
    if patterns:
        feedback = store.load_suggestion_feedback()
        suggestions = generate_suggestions(patterns, feedback=feedback or None)
        if suggestions:
            lines.append(f"Try: {suggestions[0].title}")

    msg = "\n".join(lines)
    send_notification("LWM Morning Briefing", msg)
    return msg
