"""Event handlers for the daemon event bus.

Each handler subscribes to one or more event types and emits new events.
Inspired by Elixir GenServer handle_info callbacks.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from life_world_model.analysis.pattern_discovery import compare_patterns, discover_patterns
from life_world_model.analysis.suggestions import generate_suggestions
from life_world_model.config import Settings
from life_world_model.daemon.bus import EventBus
from life_world_model.daemon.events import (
    DataCollected,
    ExperimentCompleted,
    PatternDecayed,
    PatternsUpdated,
    ScoreChanged,
    SuggestionsReady,
)
from life_world_model.experiments.engine import check_experiment_status
from life_world_model.goals.engine import load_goals
from life_world_model.notifications.macos import send_notification
from life_world_model.pipeline.bucketizer import build_life_states
from life_world_model.scoring.formula import decay_weight, score_day
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import ExperimentStatus, Pattern


def register_all_handlers(
    bus: EventBus,
    settings: Settings,
    store: SQLiteStore,
) -> None:
    """Wire all handlers to the bus."""
    bus.on(DataCollected, _make_pattern_handler(bus, settings, store), name="pattern_refresh")
    bus.on(DataCollected, _make_scorer_handler(bus, settings, store), name="scorer")
    bus.on(DataCollected, _make_experiment_handler(bus, store), name="experiment_check")
    bus.on(PatternsUpdated, _make_suggestion_handler(bus), name="suggestion_engine")
    bus.on(PatternsUpdated, _make_new_pattern_notifier(), name="new_pattern_notifier")
    bus.on(ScoreChanged, _make_score_notifier(), name="score_notifier")
    bus.on(ExperimentCompleted, _make_experiment_notifier(), name="experiment_notifier")


# ---------------------------------------------------------------------------
# Pattern refresh handler
# ---------------------------------------------------------------------------

def _make_pattern_handler(bus: EventBus, settings: Settings, store: SQLiteStore):
    def handle(event: DataCollected) -> None:
        end = event.collected_date
        start = end - timedelta(days=30)

        events = store.load_raw_events_for_range(start, end + timedelta(days=1))
        if not events:
            return

        day_events: dict[date, list] = defaultdict(list)
        for e in events:
            day_events[e.timestamp.date()].append(e)

        multi_day_states: dict[date, list] = {}
        for day, day_evts in day_events.items():
            states = build_life_states(day_evts, bucket_minutes=settings.bucket_minutes)
            if states:
                multi_day_states[day] = states

        if not multi_day_states:
            return

        new_patterns = discover_patterns(multi_day_states)
        old_patterns = store.load_patterns()
        novel = compare_patterns(old_patterns, new_patterns)

        store.save_patterns(new_patterns)
        bus.emit(PatternsUpdated(patterns=new_patterns, new_patterns=novel))

    return handle


# ---------------------------------------------------------------------------
# Scorer handler
# ---------------------------------------------------------------------------

def _make_scorer_handler(bus: EventBus, settings: Settings, store: SQLiteStore):
    last_score: dict[str, float] = {"value": 0.0}

    def handle(event: DataCollected) -> None:
        events = store.load_raw_events_for_date(event.collected_date)
        states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
        goals = load_goals()
        result = score_day(states, goals)

        old = last_score["value"]
        new = result["total"]
        last_score["value"] = new

        bus.emit(ScoreChanged(
            scored_date=event.collected_date,
            old_score=old,
            new_score=new,
            grade=result["grade"],
        ))

    return handle


# ---------------------------------------------------------------------------
# Experiment check handler
# ---------------------------------------------------------------------------

def _make_experiment_handler(bus: EventBus, store: SQLiteStore):
    def handle(event: DataCollected) -> None:
        active = store.load_experiments(status=ExperimentStatus.ACTIVE)
        for exp in active:
            updated = check_experiment_status(store, exp)
            if updated.status == ExperimentStatus.COMPLETED:
                bus.emit(ExperimentCompleted(experiment=updated))

    return handle


# ---------------------------------------------------------------------------
# Suggestion handler
# ---------------------------------------------------------------------------

def _make_suggestion_handler(bus: EventBus):
    def handle(event: PatternsUpdated) -> None:
        if not event.patterns:
            return
        suggestions = generate_suggestions(event.patterns)
        if suggestions:
            bus.emit(SuggestionsReady(suggestions=suggestions))

    return handle


# ---------------------------------------------------------------------------
# Notification handlers
# ---------------------------------------------------------------------------

def _make_new_pattern_notifier():
    def handle(event: PatternsUpdated) -> None:
        for p in event.new_patterns:
            send_notification(
                "New Pattern Discovered",
                f"{p.name}: {p.description} ({p.confidence:.0%} confidence)",
            )

    return handle


def _make_score_notifier():
    def handle(event: ScoreChanged) -> None:
        delta = abs(event.new_score - event.old_score)
        if delta > 0.05:
            direction = "up" if event.new_score > event.old_score else "down"
            send_notification(
                "LWM Score Change",
                f"Score {direction}: {event.old_score:.0%} -> {event.new_score:.0%} ({event.grade})",
            )

    return handle


def _make_experiment_notifier():
    def handle(event: ExperimentCompleted) -> None:
        exp = event.experiment
        summary = exp.result_summary or "completed"
        send_notification(
            "Experiment Complete",
            f"{exp.description}: {summary}",
        )

    return handle


# ---------------------------------------------------------------------------
# Pattern decay (called on daily schedule, not via event)
# ---------------------------------------------------------------------------

def decay_patterns(store: SQLiteStore, bus: EventBus, half_life: float = 14.0) -> None:
    """Apply exponential decay to pattern confidence. Prune dead patterns."""
    today = date.today()
    patterns = store.load_patterns()
    if not patterns:
        return

    surviving: list[Pattern] = []
    pruned_names: list[str] = []

    for p in patterns:
        if p.last_seen:
            days_ago = (today - p.last_seen).days
            p.confidence *= decay_weight(float(days_ago), half_life=half_life)

        if p.confidence > 0.1:
            surviving.append(p)
        else:
            pruned_names.append(p.name)

    if pruned_names:
        store.delete_patterns(pruned_names)

    if surviving:
        store.save_patterns(surviving)

    bus.emit(PatternDecayed(
        pruned_count=len(pruned_names),
        remaining_count=len(surviving),
    ))
