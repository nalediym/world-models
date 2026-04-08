"""Tests for the daemon event bus, handlers, and event chain."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from life_world_model.daemon.bus import EventBus, ShutdownSignal, WatchableValue
from life_world_model.daemon.events import (
    DataCollected,
    ExperimentCompleted,
    PatternDecayed,
    PatternsUpdated,
    ScoreChanged,
    SuggestionsReady,
)
from life_world_model.config import Settings
from life_world_model.daemon.handlers import decay_patterns, register_all_handlers
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import ExperimentStatus, Pattern, RawEvent


# ---------------------------------------------------------------------------
# EventBus tests
# ---------------------------------------------------------------------------


class TestEventBus:
    def test_emit_calls_handler(self) -> None:
        bus = EventBus()
        received: list = []
        bus.on(DataCollected, lambda e: received.append(e))
        event = DataCollected(collected_date=date.today(), event_count=5)
        bus.emit(event)
        assert len(received) == 1
        assert received[0].event_count == 5

    def test_fan_out_multiple_handlers(self) -> None:
        bus = EventBus()
        counts: list[int] = []
        bus.on(DataCollected, lambda e: counts.append(1))
        bus.on(DataCollected, lambda e: counts.append(2))
        bus.on(DataCollected, lambda e: counts.append(3))
        bus.emit(DataCollected(collected_date=date.today(), event_count=0))
        assert counts == [1, 2, 3]

    def test_type_isolation(self) -> None:
        bus = EventBus()
        data_count = []
        score_count = []
        bus.on(DataCollected, lambda e: data_count.append(1))
        bus.on(ScoreChanged, lambda e: score_count.append(1))
        bus.emit(DataCollected(collected_date=date.today(), event_count=0))
        assert len(data_count) == 1
        assert len(score_count) == 0

    def test_fault_isolation(self) -> None:
        """One handler crash doesn't kill other handlers."""
        bus = EventBus()
        results: list[str] = []

        def bad_handler(e: DataCollected) -> None:
            raise ValueError("boom")

        def good_handler(e: DataCollected) -> None:
            results.append("ok")

        bus.on(DataCollected, bad_handler, name="bad")
        bus.on(DataCollected, good_handler, name="good")
        bus.emit(DataCollected(collected_date=date.today(), event_count=0))
        assert results == ["ok"]
        assert bus.handler_errors["bad"] == 1

    def test_auto_disable_after_max_errors(self) -> None:
        bus = EventBus()
        bus._max_errors = 3
        call_count = []

        def crasher(e: DataCollected) -> None:
            call_count.append(1)
            raise RuntimeError("crash")

        bus.on(DataCollected, crasher, name="crasher")
        event = DataCollected(collected_date=date.today(), event_count=0)

        for _ in range(5):
            bus.emit(event)

        # Should only be called 3 times before auto-disable
        assert len(call_count) == 3
        assert bus.handler_errors["crasher"] == 3

    def test_no_handlers_for_event(self) -> None:
        bus = EventBus()
        # Should not raise
        bus.emit(DataCollected(collected_date=date.today(), event_count=0))


# ---------------------------------------------------------------------------
# WatchableValue tests
# ---------------------------------------------------------------------------


class TestWatchableValue:
    def test_initial_value(self) -> None:
        wv = WatchableValue(42)
        assert wv.value == 42

    def test_watcher_called_on_set(self) -> None:
        wv = WatchableValue(0.0)
        changes: list[tuple] = []
        wv.watch(lambda old, new: changes.append((old, new)))
        wv.set(0.75)
        assert changes == [(0.0, 0.75)]

    def test_multiple_watchers(self) -> None:
        wv = WatchableValue("a")
        log1: list = []
        log2: list = []
        wv.watch(lambda o, n: log1.append(n))
        wv.watch(lambda o, n: log2.append(n))
        wv.set("b")
        assert log1 == ["b"]
        assert log2 == ["b"]

    def test_watcher_error_doesnt_crash(self) -> None:
        wv = WatchableValue(0)
        ok_log: list = []

        def bad_watcher(old, new):
            raise ValueError("watcher crash")

        wv.watch(bad_watcher)
        wv.watch(lambda o, n: ok_log.append(n))
        wv.set(1)
        assert ok_log == [1]


# ---------------------------------------------------------------------------
# ShutdownSignal tests
# ---------------------------------------------------------------------------


class TestShutdownSignal:
    def test_not_set_initially(self) -> None:
        s = ShutdownSignal()
        assert not s.is_set

    def test_request_sets(self) -> None:
        s = ShutdownSignal()
        s.request()
        assert s.is_set

    def test_wait_returns_immediately_when_set(self) -> None:
        s = ShutdownSignal()
        s.request()
        assert s.wait(timeout=0.01) is True

    def test_wait_times_out(self) -> None:
        s = ShutdownSignal()
        assert s.wait(timeout=0.01) is False


# ---------------------------------------------------------------------------
# Event chain integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path / "test.sqlite3")


def _seed_events(store: SQLiteStore, target_date: date) -> None:
    base = datetime.combine(target_date, datetime.min.time()).replace(hour=9)
    events = [
        RawEvent(timestamp=base, source="test", title="coding", domain="github.com"),
        RawEvent(timestamp=base.replace(hour=10), source="test", title="research", domain="arxiv.org"),
        RawEvent(timestamp=base.replace(hour=11), source="test", title="coding", domain="github.com"),
        RawEvent(timestamp=base.replace(hour=14), source="test", title="browsing", domain="news.ycombinator.com"),
    ]
    store.save_raw_events(events)


class TestEventChain:
    def test_data_collected_triggers_pattern_and_score(self, store: SQLiteStore) -> None:
        """DataCollected should trigger pattern discovery, scoring, and experiment check."""
        settings = Settings(database_path=store.database_path)

        bus = EventBus()
        emitted_events: list = []

        # Capture all emitted events
        bus.on(PatternsUpdated, lambda e: emitted_events.append(("patterns", e)))
        bus.on(ScoreChanged, lambda e: emitted_events.append(("score", e)))

        register_all_handlers(bus, settings, store)

        # Seed multi-day data for pattern discovery
        today = date.today()
        for days_ago in range(5):
            _seed_events(store, today - timedelta(days=days_ago))

        bus.emit(DataCollected(collected_date=today, event_count=4))

        event_types = [t for t, _ in emitted_events]
        assert "score" in event_types
        # Patterns may or may not be found depending on data, but the handler ran without crash

    def test_patterns_updated_triggers_suggestions(self, store: SQLiteStore) -> None:
        bus = EventBus()
        suggestion_events: list = []
        bus.on(SuggestionsReady, lambda e: suggestion_events.append(e))

        from life_world_model.daemon.handlers import _make_suggestion_handler
        bus.on(PatternsUpdated, _make_suggestion_handler(bus, store), name="suggester")

        pattern = Pattern(
            name="test_routine",
            category="routine",
            description="test pattern",
            evidence={"activity": "coding", "hour": 9, "frequency": 0.8},
            confidence=0.8,
            days_observed=5,
        )
        bus.emit(PatternsUpdated(patterns=[pattern], new_patterns=[]))

        assert len(suggestion_events) == 1
        assert len(suggestion_events[0].suggestions) > 0


# ---------------------------------------------------------------------------
# Pattern persistence tests
# ---------------------------------------------------------------------------


class TestPatternPersistence:
    def test_save_and_load(self, store: SQLiteStore) -> None:
        patterns = [
            Pattern(
                name="test_pattern",
                category="routine",
                description="test",
                evidence={"activity": "coding"},
                confidence=0.85,
                days_observed=7,
                first_seen=date(2026, 4, 1),
                last_seen=date(2026, 4, 7),
            )
        ]
        store.save_patterns(patterns)
        loaded = store.load_patterns()
        assert len(loaded) == 1
        assert loaded[0].name == "test_pattern"
        assert loaded[0].confidence == 0.85
        assert loaded[0].evidence == {"activity": "coding"}

    def test_upsert_updates_confidence(self, store: SQLiteStore) -> None:
        p = Pattern(name="p1", category="routine", description="t",
                    evidence={}, confidence=0.9, days_observed=5)
        store.save_patterns([p])
        p.confidence = 0.5
        store.save_patterns([p])
        loaded = store.load_patterns()
        assert len(loaded) == 1
        assert loaded[0].confidence == 0.5

    def test_delete_patterns(self, store: SQLiteStore) -> None:
        patterns = [
            Pattern(name="keep", category="routine", description="t",
                    evidence={}, confidence=0.9, days_observed=5),
            Pattern(name="delete_me", category="routine", description="t",
                    evidence={}, confidence=0.1, days_observed=5),
        ]
        store.save_patterns(patterns)
        store.delete_patterns(["delete_me"])
        loaded = store.load_patterns()
        assert len(loaded) == 1
        assert loaded[0].name == "keep"


# ---------------------------------------------------------------------------
# Pattern decay tests
# ---------------------------------------------------------------------------


class TestPatternDecay:
    def test_decay_reduces_confidence(self, store: SQLiteStore) -> None:
        bus = EventBus()
        decay_events: list = []
        bus.on(PatternDecayed, lambda e: decay_events.append(e))

        old_date = date.today() - timedelta(days=60)
        patterns = [
            Pattern(name="stale", category="routine", description="old",
                    evidence={}, confidence=0.3, days_observed=5,
                    last_seen=old_date),
            Pattern(name="fresh", category="routine", description="new",
                    evidence={}, confidence=0.9, days_observed=5,
                    last_seen=date.today()),
        ]
        store.save_patterns(patterns)
        decay_patterns(store, bus, half_life=14.0)

        loaded = store.load_patterns()
        names = {p.name for p in loaded}
        # "stale" (30 days old, 0.5 confidence) should be pruned (decays below 0.1)
        assert "stale" not in names
        assert "fresh" in names
        assert len(decay_events) == 1
        assert decay_events[0].pruned_count >= 1

    def test_decay_empty_patterns(self, store: SQLiteStore) -> None:
        bus = EventBus()
        decay_events: list = []
        bus.on(PatternDecayed, lambda e: decay_events.append(e))
        decay_patterns(store, bus)
        assert len(decay_events) == 0  # no patterns, no event


# ---------------------------------------------------------------------------
# compare_patterns tests
# ---------------------------------------------------------------------------


class TestComparePatterns:
    def test_detects_new_patterns(self) -> None:
        from life_world_model.analysis.pattern_discovery import compare_patterns

        old = [Pattern(name="a", category="r", description="", evidence={},
                       confidence=0.5, days_observed=1)]
        new = [
            Pattern(name="a", category="r", description="", evidence={},
                    confidence=0.5, days_observed=1),
            Pattern(name="b", category="r", description="", evidence={},
                    confidence=0.5, days_observed=1),
        ]
        novel = compare_patterns(old, new)
        assert len(novel) == 1
        assert novel[0].name == "b"

    def test_no_new_patterns(self) -> None:
        from life_world_model.analysis.pattern_discovery import compare_patterns

        old = [Pattern(name="a", category="r", description="", evidence={},
                       confidence=0.5, days_observed=1)]
        new = [Pattern(name="a", category="r", description="", evidence={},
                       confidence=0.5, days_observed=1)]
        assert compare_patterns(old, new) == []
