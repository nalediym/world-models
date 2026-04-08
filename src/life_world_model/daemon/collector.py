"""Daemon: event-driven continuous learning loop.

Replaces the flat while-True loop with:
- EventBus (Elixir PubSub) for fan-out event routing
- sched.scheduler (Go-style multi-rate timers) for scheduling
- Per-handler fault isolation (Elixir Supervisor)
- Cooperative shutdown (Go context / Rust CancellationToken)
"""

from __future__ import annotations

import sched
import time
from datetime import date

from life_world_model.config import Settings, load_settings
from life_world_model.daemon.bus import EventBus, ShutdownSignal
from life_world_model.daemon.events import DataCollected
from life_world_model.daemon.handlers import decay_patterns, register_all_handlers
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
        except Exception as e:
            print(f"[collector] {collector.source_name} error: {e}")

    return total


def _score_today(settings: Settings, store: SQLiteStore) -> float:
    """Bucket and score today's data. Returns total score (0.0-1.0)."""
    from life_world_model.goals.engine import load_goals
    from life_world_model.pipeline.bucketizer import build_life_states
    from life_world_model.scoring.formula import score_day

    today = date.today()
    events = store.load_raw_events_for_date(today)
    states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
    goals = load_goals()
    result = score_day(states, goals)
    return result["total"]


def run_daemon(interval_minutes: int = 60) -> None:
    """Event-driven daemon loop with multi-rate scheduling.

    Hourly: collect events → emit DataCollected → handlers fan out
    Daily @ midnight: pattern confidence decay
    Ctrl+C or SIGTERM to stop.
    """
    settings = load_settings()
    store = SQLiteStore(settings.database_path)
    bus = EventBus()
    shutdown = ShutdownSignal()
    shutdown.install_signal_handlers()

    # Wire all handlers to the bus
    register_all_handlers(bus, settings, store)

    scheduler = sched.scheduler(time.time, time.sleep)

    def collection_tick() -> None:
        if shutdown.is_set:
            return
        today = date.today()
        collected = _collect_cycle(settings, store)
        print(f"[daemon] {today} — collected {collected} events")

        bus.emit(DataCollected(collected_date=today, event_count=collected))

        # Re-schedule (Elixir Process.send_after pattern)
        if not shutdown.is_set:
            scheduler.enter(interval_minutes * 60, 1, collection_tick)

    def decay_tick() -> None:
        if shutdown.is_set:
            return
        print("[daemon] Running pattern confidence decay...")
        decay_patterns(store, bus)
        # Re-schedule daily
        if not shutdown.is_set:
            scheduler.enter(86400, 2, decay_tick)

    # Schedule initial ticks
    scheduler.enter(0, 1, collection_tick)     # collect immediately
    scheduler.enter(86400, 2, decay_tick)      # decay daily

    print(f"LWM daemon started (interval: {interval_minutes}min). Ctrl+C to stop.")
    print(f"  Handlers: {len(bus._handlers)} event types registered")

    try:
        while not shutdown.is_set:
            # Run pending scheduled events with a short timeout
            # so we can check the shutdown signal
            if scheduler.queue:
                scheduler.run(blocking=False)
            shutdown.wait(timeout=1.0)
    except KeyboardInterrupt:
        pass

    # Report handler health on exit
    errors = bus.handler_errors
    if errors:
        print("\n[daemon] Handler error summary:")
        for name, count in errors.items():
            print(f"  {name}: {count} errors")

    print("\nDaemon stopped.")
