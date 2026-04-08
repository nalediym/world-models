from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from life_world_model.analysis.pattern_discovery import discover_patterns
from life_world_model.analysis.proactive import suggest_experiments
from life_world_model.analysis.suggestions import generate_suggestions
from life_world_model.config import load_settings
from life_world_model.goals.engine import load_goals
from life_world_model.notifications.macos import send_notification
from life_world_model.pipeline.bucketizer import build_life_states
from life_world_model.scoring.formula import score_day
from life_world_model.pipeline.voices import Voice, get_voice
from life_world_model.storage.sqlite_store import SQLiteStore


def morning_briefing(voice: Voice | None = None) -> str:
    """Score yesterday, format a brief summary, send macOS notification, return text."""
    if voice is None:
        voice = get_voice("coach")
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

    msg = (
        f"Yesterday: {total:.0%} ({grade}) | "
        f"Top: {top_activity} ({top_hours:.1f}hrs) | "
        f"{switches} switches"
    )

    # Check for proposed experiments from recent patterns
    experiment_msg = _propose_experiment_summary(store, settings)
    if experiment_msg:
        msg = f"{msg} | {experiment_msg}"

    send_notification("LWM Morning Briefing", msg)
    return msg


def _propose_experiment_summary(
    store: SQLiteStore, settings: object
) -> str | None:
    """Build a brief experiment proposal from the last 30 days of patterns."""
    today = date.today()
    start = today - timedelta(days=30)

    multi_day_states: dict[date, list] = defaultdict(list)
    current = start
    while current <= today:
        events = store.load_raw_events_for_date(current)
        if events:
            day_states = build_life_states(
                events, bucket_minutes=getattr(settings, "bucket_minutes", 15)
            )
            if day_states:
                multi_day_states[current] = day_states
        current += timedelta(days=1)

    if not multi_day_states:
        return None

    patterns = discover_patterns(dict(multi_day_states), reference_date=today)
    active_patterns = [p for p in patterns if p.category != "stale"]

    if not active_patterns:
        return None

    suggestions = generate_suggestions(active_patterns)
    proposed = suggest_experiments(suggestions)

    if proposed:
        return f"Experiment: {proposed[0].source_suggestion_id}"

    return None
