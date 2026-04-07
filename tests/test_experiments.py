from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from life_world_model.experiments.engine import (
    cancel_experiment,
    check_experiment_status,
    format_experiment_status,
    start_experiment,
)
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import Experiment, ExperimentStatus, RawEvent


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path / "test.sqlite3")


def _make_events(target_date: date) -> list[RawEvent]:
    """Generate some test events for a date."""
    base = datetime.combine(target_date, datetime.min.time()).replace(hour=9)
    return [
        RawEvent(timestamp=base, source="test", title="coding session", domain="github.com"),
        RawEvent(timestamp=base.replace(hour=10), source="test", title="research", domain="arxiv.org"),
        RawEvent(timestamp=base.replace(hour=14), source="test", title="browsing", domain="news.ycombinator.com"),
    ]


class TestExperimentStorage:
    def test_save_and_load(self, store: SQLiteStore) -> None:
        exp = Experiment(
            id="test1234",
            description="Code before email for 3 days",
            intervention="code from 8-10am",
            duration_days=3,
            start_date=date(2026, 4, 7),
            baseline_score=0.65,
        )
        store.save_experiment(exp)
        loaded = store.load_experiments()
        assert len(loaded) == 1
        assert loaded[0].id == "test1234"
        assert loaded[0].description == "Code before email for 3 days"
        assert loaded[0].status == ExperimentStatus.ACTIVE

    def test_update_experiment(self, store: SQLiteStore) -> None:
        exp = Experiment(
            id="test5678",
            description="Test experiment",
            intervention="test",
            duration_days=3,
            start_date=date(2026, 4, 7),
        )
        store.save_experiment(exp)
        exp.status = ExperimentStatus.COMPLETED
        exp.result_score = 0.72
        exp.result_summary = "Improved"
        store.update_experiment(exp)

        loaded = store.load_experiment("test5678")
        assert loaded is not None
        assert loaded.status == ExperimentStatus.COMPLETED
        assert loaded.result_score == 0.72

    def test_load_by_status(self, store: SQLiteStore) -> None:
        for i, status in enumerate(
            [ExperimentStatus.ACTIVE, ExperimentStatus.COMPLETED, ExperimentStatus.ACTIVE]
        ):
            exp = Experiment(
                id=f"exp{i}",
                description=f"Experiment {i}",
                intervention="test",
                duration_days=3,
                start_date=date(2026, 4, 7),
                status=status,
            )
            store.save_experiment(exp)
        active = store.load_experiments(status=ExperimentStatus.ACTIVE)
        assert len(active) == 2
        completed = store.load_experiments(status=ExperimentStatus.COMPLETED)
        assert len(completed) == 1

    def test_load_nonexistent(self, store: SQLiteStore) -> None:
        assert store.load_experiment("nope") is None


class TestStartExperiment:
    def test_start_creates_experiment(self, store: SQLiteStore) -> None:
        # Seed some baseline data
        today = date.today()
        for days_ago in range(1, 4):
            d = today - timedelta(days=days_ago)
            store.save_raw_events(_make_events(d))

        exp = start_experiment(
            store,
            description="Code before email",
            intervention="code from 8-10am",
            duration_days=3,
        )
        assert exp.status == ExperimentStatus.ACTIVE
        assert exp.id is not None
        assert len(exp.id) == 8
        assert exp.start_date == today

    def test_start_without_baseline_data(self, store: SQLiteStore) -> None:
        exp = start_experiment(
            store,
            description="Test with no data",
            intervention="test",
            duration_days=3,
        )
        assert exp.baseline_score is None


class TestCheckExperimentStatus:
    def test_still_active(self, store: SQLiteStore) -> None:
        exp = Experiment(
            id="active1",
            description="Still running",
            intervention="test",
            duration_days=3,
            start_date=date.today(),
        )
        store.save_experiment(exp)
        result = check_experiment_status(store, exp)
        assert result.status == ExperimentStatus.ACTIVE

    def test_completes_after_duration(self, store: SQLiteStore) -> None:
        start = date.today() - timedelta(days=5)
        # Add events during experiment period
        for d_offset in range(3):
            d = start + timedelta(days=d_offset)
            store.save_raw_events(_make_events(d))

        exp = Experiment(
            id="done1",
            description="Should complete",
            intervention="test",
            duration_days=3,
            start_date=start,
            baseline_score=0.5,
        )
        store.save_experiment(exp)
        result = check_experiment_status(store, exp)
        assert result.status == ExperimentStatus.COMPLETED
        assert result.result_score is not None
        assert result.result_summary is not None

    def test_completes_with_no_data(self, store: SQLiteStore) -> None:
        start = date.today() - timedelta(days=5)
        exp = Experiment(
            id="nodata1",
            description="No data experiment",
            intervention="test",
            duration_days=3,
            start_date=start,
        )
        store.save_experiment(exp)
        result = check_experiment_status(store, exp)
        assert result.status == ExperimentStatus.COMPLETED
        assert "No data" in result.result_summary


class TestCancelExperiment:
    def test_cancel(self, store: SQLiteStore) -> None:
        exp = Experiment(
            id="cancel1",
            description="Cancel me",
            intervention="test",
            duration_days=3,
            start_date=date.today(),
        )
        store.save_experiment(exp)
        result = cancel_experiment(store, exp)
        assert result.status == ExperimentStatus.CANCELLED
        loaded = store.load_experiment("cancel1")
        assert loaded.status == ExperimentStatus.CANCELLED


class TestFormatExperimentStatus:
    def test_active_format(self) -> None:
        exp = Experiment(
            id="fmt1",
            description="Test format",
            intervention="code from 8-10am",
            duration_days=3,
            start_date=date.today(),
            baseline_score=0.65,
        )
        text = format_experiment_status(exp)
        assert "fmt1" in text
        assert "Test format" in text
        assert "active" in text
        assert "65.0%" in text

    def test_completed_format(self) -> None:
        exp = Experiment(
            id="fmt2",
            description="Done experiment",
            intervention="test",
            duration_days=3,
            start_date=date(2026, 4, 1),
            status=ExperimentStatus.COMPLETED,
            baseline_score=0.5,
            result_score=0.72,
            result_summary="Improved by 22%",
        )
        text = format_experiment_status(exp)
        assert "completed" in text
        assert "72.0%" in text
        assert "Improved" in text
