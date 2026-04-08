from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from life_world_model.simulation.parallel_lives import (
    ParallelLife,
    ParallelLivesComparison,
    _generate_id,
    _projections_from_json,
    _projections_to_json,
    _save_parallel_life,
    compare_lives,
    create_parallel_life,
    format_comparison,
    load_parallel_life,
    load_parallel_lives,
    update_parallel_life_status,
)
from life_world_model.simulation.projector import ProjectionDay
from life_world_model.storage.sqlite_store import SQLiteStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_store(tmp_path: Path) -> SQLiteStore:
    """Create a real SQLiteStore backed by a temp database."""
    store = SQLiteStore(tmp_path / "test.sqlite3")
    store.initialize()
    return store


@pytest.fixture
def sample_projections() -> list[ProjectionDay]:
    base = date(2026, 4, 8)
    return [
        ProjectionDay(
            day_number=i + 1,
            date=base + timedelta(days=i),
            score=0.62 + 0.01 * (i + 1),
            delta_from_baseline=0.01 * (i + 1),
            habit_strength=min(1.0, 0.1 * (i + 1)),
        )
        for i in range(5)
    ]


@pytest.fixture
def sample_life(sample_projections: list[ProjectionDay]) -> ParallelLife:
    return ParallelLife(
        id="abc12345",
        name="Code first",
        intervention="code from 8-10am",
        created_date=date(2026, 4, 7),
        duration_days=14,
        projections=sample_projections,
        status="active",
    )


# ---------------------------------------------------------------------------
# SQLite table creation
# ---------------------------------------------------------------------------


class TestSQLiteTableCreation:
    def test_parallel_lives_table_exists(self, tmp_store: SQLiteStore):
        """The parallel_lives table should be created during initialize()."""
        with sqlite3.connect(tmp_store.database_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='parallel_lives'"
            ).fetchall()
        assert len(tables) == 1

    def test_parallel_lives_columns(self, tmp_store: SQLiteStore):
        """Verify the expected columns exist."""
        with sqlite3.connect(tmp_store.database_path) as conn:
            info = conn.execute("PRAGMA table_info(parallel_lives)").fetchall()
        col_names = {row[1] for row in info}
        expected = {
            "id", "name", "intervention", "created_date",
            "duration_days", "status", "projections_json",
        }
        assert expected == col_names


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


class TestProjectionSerialisation:
    def test_round_trip(self, sample_projections: list[ProjectionDay]):
        json_str = _projections_to_json(sample_projections)
        restored = _projections_from_json(json_str)
        assert len(restored) == len(sample_projections)
        for orig, rest in zip(sample_projections, restored):
            assert orig.day_number == rest.day_number
            assert orig.date == rest.date
            assert abs(orig.score - rest.score) < 1e-9
            assert abs(orig.delta_from_baseline - rest.delta_from_baseline) < 1e-9
            assert abs(orig.habit_strength - rest.habit_strength) < 1e-9

    def test_empty_json(self):
        assert _projections_from_json(None) == []
        assert _projections_from_json("") == []


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


class TestSaveAndLoadParallelLife:
    def test_save_and_load(
        self, tmp_store: SQLiteStore, sample_life: ParallelLife
    ):
        _save_parallel_life(tmp_store, sample_life)

        loaded = load_parallel_life(tmp_store, sample_life.id)
        assert loaded is not None
        assert loaded.id == sample_life.id
        assert loaded.name == sample_life.name
        assert loaded.intervention == sample_life.intervention
        assert loaded.created_date == sample_life.created_date
        assert loaded.duration_days == sample_life.duration_days
        assert loaded.status == sample_life.status
        assert len(loaded.projections) == len(sample_life.projections)

    def test_load_nonexistent(self, tmp_store: SQLiteStore):
        assert load_parallel_life(tmp_store, "nonexistent") is None

    def test_load_all(
        self, tmp_store: SQLiteStore, sample_life: ParallelLife
    ):
        _save_parallel_life(tmp_store, sample_life)
        lives = load_parallel_lives(tmp_store)
        assert len(lives) == 1
        assert lives[0].id == sample_life.id

    def test_load_by_status(
        self, tmp_store: SQLiteStore, sample_life: ParallelLife
    ):
        _save_parallel_life(tmp_store, sample_life)

        active = load_parallel_lives(tmp_store, status="active")
        assert len(active) == 1

        completed = load_parallel_lives(tmp_store, status="completed")
        assert len(completed) == 0


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


class TestStatusTransitions:
    def test_update_status(
        self, tmp_store: SQLiteStore, sample_life: ParallelLife
    ):
        _save_parallel_life(tmp_store, sample_life)
        update_parallel_life_status(tmp_store, sample_life.id, "completed")

        loaded = load_parallel_life(tmp_store, sample_life.id)
        assert loaded is not None
        assert loaded.status == "completed"

    def test_abandon(
        self, tmp_store: SQLiteStore, sample_life: ParallelLife
    ):
        _save_parallel_life(tmp_store, sample_life)
        update_parallel_life_status(tmp_store, sample_life.id, "abandoned")

        loaded = load_parallel_life(tmp_store, sample_life.id)
        assert loaded is not None
        assert loaded.status == "abandoned"


# ---------------------------------------------------------------------------
# create_parallel_life (integration, mocked projection)
# ---------------------------------------------------------------------------


class TestCreateParallelLife:
    @patch("life_world_model.simulation.parallel_lives.project_intervention")
    def test_create_stores_correctly(self, mock_proj, tmp_store: SQLiteStore):
        mock_result = MagicMock()
        mock_result.days = [
            ProjectionDay(
                day_number=1,
                date=date(2026, 4, 8),
                score=0.71,
                delta_from_baseline=0.09,
                habit_strength=0.12,
            )
        ]
        mock_proj.return_value = mock_result

        settings = MagicMock()
        life = create_parallel_life(
            tmp_store, settings, "Morning code", "code from 8-10am", duration_days=14
        )

        assert life.name == "Morning code"
        assert life.intervention == "code from 8-10am"
        assert life.status == "active"
        assert len(life.projections) == 1

        # Verify persisted
        loaded = load_parallel_life(tmp_store, life.id)
        assert loaded is not None
        assert loaded.name == "Morning code"


# ---------------------------------------------------------------------------
# compare_lives
# ---------------------------------------------------------------------------


class TestCompareLives:
    def test_compare_with_no_lives(self, tmp_store: SQLiteStore):
        settings = MagicMock()
        result = compare_lives(tmp_store, settings)
        assert result.lives == []
        assert result.real_life_scores == []
        assert result.divergence_points == []

    @patch("life_world_model.simulation.parallel_lives._load_real_scores")
    def test_compare_with_multiple_timelines(
        self,
        mock_real_scores,
        tmp_store: SQLiteStore,
        sample_projections: list[ProjectionDay],
    ):
        settings = MagicMock()

        # Create two lives
        life_a = ParallelLife(
            id="aaa11111",
            name="Code first",
            intervention="code from 8-10am",
            created_date=date(2026, 4, 7),
            duration_days=5,
            projections=sample_projections,
            status="active",
        )
        life_b = ParallelLife(
            id="bbb22222",
            name="No browsing",
            intervention="stop browsing after 9pm",
            created_date=date(2026, 4, 7),
            duration_days=5,
            projections=[
                ProjectionDay(
                    day_number=p.day_number,
                    date=p.date,
                    score=p.score - 0.03,
                    delta_from_baseline=p.delta_from_baseline - 0.03,
                    habit_strength=p.habit_strength,
                )
                for p in sample_projections
            ],
            status="active",
        )

        _save_parallel_life(tmp_store, life_a)
        _save_parallel_life(tmp_store, life_b)

        # Mock real scores
        dates = sorted({p.date for p in sample_projections})
        mock_real_scores.return_value = [(d, 0.60) for d in dates]

        result = compare_lives(tmp_store, settings)
        assert len(result.lives) == 2
        assert len(result.real_life_scores) == len(dates)

    @patch("life_world_model.simulation.parallel_lives._load_real_scores")
    def test_compare_with_missing_real_data(
        self,
        mock_real_scores,
        tmp_store: SQLiteStore,
        sample_life: ParallelLife,
    ):
        """Missing real data should produce None scores, not crash."""
        settings = MagicMock()
        _save_parallel_life(tmp_store, sample_life)

        dates = sorted({p.date for p in sample_life.projections})
        # Some days have data, some don't
        mock_real_scores.return_value = [
            (dates[0], 0.62),
            (dates[1], None),
            (dates[2], 0.58),
            (dates[3], None),
            (dates[4], 0.65),
        ]

        result = compare_lives(tmp_store, settings)
        assert len(result.lives) == 1
        # Should not crash even with None scores
        none_scores = [s for _, s in result.real_life_scores if s is None]
        assert len(none_scores) == 2

    def test_compare_with_specific_ids(
        self, tmp_store: SQLiteStore, sample_projections: list[ProjectionDay]
    ):
        settings = MagicMock()

        life_a = ParallelLife(
            id="aaa11111",
            name="Code first",
            intervention="code from 8-10am",
            created_date=date(2026, 4, 7),
            duration_days=5,
            projections=sample_projections,
            status="active",
        )
        life_b = ParallelLife(
            id="bbb22222",
            name="No browsing",
            intervention="stop browsing after 9pm",
            created_date=date(2026, 4, 7),
            duration_days=5,
            projections=sample_projections,
            status="active",
        )
        _save_parallel_life(tmp_store, life_a)
        _save_parallel_life(tmp_store, life_b)

        # Request only one
        with patch(
            "life_world_model.simulation.parallel_lives._load_real_scores"
        ) as mock_rs:
            dates = sorted({p.date for p in sample_projections})
            mock_rs.return_value = [(d, 0.60) for d in dates]
            result = compare_lives(tmp_store, settings, life_ids=["aaa11111"])

        assert len(result.lives) == 1
        assert result.lives[0].id == "aaa11111"


# ---------------------------------------------------------------------------
# Format comparison
# ---------------------------------------------------------------------------


class TestFormatComparison:
    def test_format_empty(self):
        comp = ParallelLivesComparison(
            real_life_scores=[], lives=[], divergence_points=[]
        )
        output = format_comparison(comp)
        assert "PARALLEL LIVES" in output
        assert "No active" in output

    def test_format_with_data(self, sample_projections: list[ProjectionDay]):
        life = ParallelLife(
            id="abc12345",
            name="Code first",
            intervention="code from 8-10am",
            created_date=date(2026, 4, 7),
            duration_days=5,
            projections=sample_projections,
            status="active",
        )
        dates = sorted({p.date for p in sample_projections})
        real_scores = [(d, 0.60) for d in dates]

        comp = ParallelLivesComparison(
            real_life_scores=real_scores,
            lives=[life],
            divergence_points=["Day 2: \"Code first\" is ahead of real life by 5.0%"],
        )

        output = format_comparison(comp)
        assert "PARALLEL LIVES" in output
        assert "Real Life" in output
        assert "Timeline" in output
        assert "Divergence" in output

    def test_format_with_no_data_days(self, sample_projections: list[ProjectionDay]):
        life = ParallelLife(
            id="abc12345",
            name="Code first",
            intervention="code from 8-10am",
            created_date=date(2026, 4, 7),
            duration_days=5,
            projections=sample_projections,
            status="active",
        )
        dates = sorted({p.date for p in sample_projections})
        # Mix of real data and None
        real_scores: list[tuple[date, float | None]] = [
            (dates[0], 0.62),
            (dates[1], None),
            (dates[2], 0.58),
            (dates[3], None),
            (dates[4], 0.65),
        ]

        comp = ParallelLivesComparison(
            real_life_scores=real_scores,
            lives=[life],
            divergence_points=[],
        )

        output = format_comparison(comp)
        assert "no data" in output


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


class TestGenerateId:
    def test_deterministic(self):
        id1 = _generate_id("test", "code from 8-10am", date(2026, 4, 7))
        id2 = _generate_id("test", "code from 8-10am", date(2026, 4, 7))
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        id1 = _generate_id("test", "code from 8-10am", date(2026, 4, 7))
        id2 = _generate_id("test", "walk at lunch", date(2026, 4, 7))
        assert id1 != id2

    def test_length(self):
        result = _generate_id("test", "code from 8-10am", date(2026, 4, 7))
        assert len(result) == 8
