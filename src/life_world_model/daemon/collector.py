from __future__ import annotations

import time
from datetime import date

from life_world_model.config import Settings, load_settings
from life_world_model.goals.engine import load_goals
from life_world_model.notifications.macos import send_notification
from life_world_model.pipeline.bucketizer import build_life_states
from life_world_model.scoring.formula import score_day
from life_world_model.storage.sqlite_store import SQLiteStore


def _collect_cycle(settings: Settings, store: SQLiteStore) -> int:
    """Import and run all collectors for today. Returns total events collected."""
    from life_world_model.cli import _build_collectors, _import_collectors

    _import_collectors()
    collectors = _build_collectors(settings)
    today = date.today()
    total = 0

    for collector in collectors:
        if not collector.is_available():
            continue
        try:
            events = collector.collect_for_date(today)
            store.save_raw_events(events)
            total += len(events)
        except Exception:
            pass  # daemon is silent — errors are swallowed

    return total


def _score_today(settings: Settings, store: SQLiteStore) -> float:
    """Bucket and score today's data. Returns total score (0.0-1.0)."""
    today = date.today()
    events = store.load_raw_events_for_date(today)
    states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
    goals = load_goals()
    result = score_day(states, goals)
    return result["total"]


def run_daemon(interval_minutes: int = 60) -> None:
    """Foreground daemon loop. Collects from all sources each cycle,
    scores today, sends macOS notification if score changes >5%.
    Ctrl+C to stop.
    """
    settings = load_settings()
    store = SQLiteStore(settings.database_path)

    last_score: float | None = None

    print(f"LWM daemon started (interval: {interval_minutes}min). Ctrl+C to stop.")

    try:
        while True:
            collected = _collect_cycle(settings, store)
            current_score = _score_today(settings, store)

            print(
                f"[{date.today()}] collected {collected} events, "
                f"score: {current_score:.1%}"
            )

            if last_score is not None:
                delta = abs(current_score - last_score)
                if delta > 0.05:
                    direction = "up" if current_score > last_score else "down"
                    send_notification(
                        "LWM Score Change",
                        f"Score {direction}: {last_score:.0%} -> {current_score:.0%}",
                    )

            last_score = current_score
            time.sleep(interval_minutes * 60)
    except KeyboardInterrupt:
        print("\nDaemon stopped.")
