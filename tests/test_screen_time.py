"""Tests for the Screen Time collector.

All tests use fixture / mock data — never real user databases.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from life_world_model.collectors.screen_time import (
    STREAM_APP_USAGE,
    STREAM_WEB_USAGE,
    ScreenTimeCollector,
    _bundle_to_name,
)
from life_world_model.types import RawEvent
from life_world_model.utils.timestamps import MAC_EPOCH, mac_epoch_from_datetime


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _dt_to_mac(dt: datetime) -> float:
    """Convert a timezone-aware datetime to Mac epoch seconds."""
    return mac_epoch_from_datetime(dt)


def _create_fixture_db(path: Path, rows: list[tuple]) -> None:
    """Create a minimal knowledgeC-style SQLite DB with the given rows.

    Each row is ``(ZCREATIONDATE, ZENDDATE, ZSTREAMNAME, ZVALUESTRING)``.
    """
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE ZOBJECT (
            Z_PK INTEGER PRIMARY KEY,
            ZCREATIONDATE REAL,
            ZENDDATE REAL,
            ZSTREAMNAME TEXT,
            ZVALUESTRING TEXT
        )
        """
    )
    for i, (creation, end, stream, value) in enumerate(rows, start=1):
        conn.execute(
            "INSERT INTO ZOBJECT (Z_PK, ZCREATIONDATE, ZENDDATE, ZSTREAMNAME, ZVALUESTRING) "
            "VALUES (?, ?, ?, ?, ?)",
            (i, creation, end, stream, value),
        )
    conn.commit()
    conn.close()


# ------------------------------------------------------------------
# 1. _bundle_to_name
# ------------------------------------------------------------------


class TestBundleToName:
    def test_known_bundle_ids(self) -> None:
        assert _bundle_to_name("com.apple.Safari") == "Safari"
        assert _bundle_to_name("com.google.Chrome") == "Chrome"

    def test_unknown_bundle_id_uses_last_component(self) -> None:
        assert _bundle_to_name("com.example.SuperApp") == "SuperApp"

    def test_none_returns_unknown(self) -> None:
        assert _bundle_to_name(None) == "Unknown"

    def test_empty_string_returns_unknown(self) -> None:
        assert _bundle_to_name("") == "Unknown"


# ------------------------------------------------------------------
# 2. collect_for_date — parses rows into RawEvents
# ------------------------------------------------------------------


class TestCollectForDate:
    def test_parses_app_usage_rows(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        start = datetime(2026, 4, 6, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 6, 9, 30, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [(_dt_to_mac(start), _dt_to_mac(end), STREAM_APP_USAGE, "com.apple.Safari")],
        )

        collector = ScreenTimeCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        event = events[0]
        assert event.source == "screentime"
        assert event.title == "Safari"
        assert event.domain == "com.apple.Safari"
        assert event.duration_seconds == pytest.approx(1800.0)
        assert event.metadata == {"stream": STREAM_APP_USAGE}

    def test_parses_web_usage_rows(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        start = datetime(2026, 4, 6, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 6, 10, 15, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [(_dt_to_mac(start), _dt_to_mac(end), STREAM_WEB_USAGE, "github.com")],
        )

        collector = ScreenTimeCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        event = events[0]
        assert event.source == "screentime"
        assert event.title == "Web Usage"
        assert event.domain == "github.com"
        assert event.duration_seconds == pytest.approx(900.0)
        assert event.metadata == {"stream": STREAM_WEB_USAGE}

    def test_multiple_streams_in_one_day(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        base = datetime(2026, 4, 6, 9, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (_dt_to_mac(base), _dt_to_mac(base + timedelta(minutes=10)), STREAM_APP_USAGE, "com.google.Chrome"),
                (_dt_to_mac(base + timedelta(minutes=15)), _dt_to_mac(base + timedelta(minutes=25)), STREAM_WEB_USAGE, "news.ycombinator.com"),
                (_dt_to_mac(base + timedelta(minutes=30)), _dt_to_mac(base + timedelta(minutes=60)), STREAM_APP_USAGE, "com.microsoft.VSCode"),
            ],
        )

        collector = ScreenTimeCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 3
        assert events[0].title == "Chrome"
        assert events[1].title == "Web Usage"
        assert events[2].title == "VS Code"

    def test_filters_events_from_other_days(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        in_range = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
        out_of_range = datetime(2026, 4, 7, 1, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (_dt_to_mac(in_range), _dt_to_mac(in_range + timedelta(minutes=5)), STREAM_APP_USAGE, "com.apple.Safari"),
                (_dt_to_mac(out_of_range), _dt_to_mac(out_of_range + timedelta(minutes=5)), STREAM_APP_USAGE, "com.google.Chrome"),
            ],
        )

        collector = ScreenTimeCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].title == "Safari"

    def test_all_timestamps_have_timezone(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        ts = datetime(2026, 4, 6, 14, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [(_dt_to_mac(ts), _dt_to_mac(ts + timedelta(minutes=5)), STREAM_APP_USAGE, "com.apple.Terminal")],
        )

        collector = ScreenTimeCollector(db_path)
        events = collector.collect_for_date(target)

        for event in events:
            assert event.timestamp.tzinfo is not None


# ------------------------------------------------------------------
# 3. is_available
# ------------------------------------------------------------------


class TestIsAvailable:
    def test_returns_true_when_db_exists(self, tmp_path: Path) -> None:
        db_path = tmp_path / "knowledgeC.db"
        db_path.touch()
        collector = ScreenTimeCollector(db_path)
        assert collector.is_available() is True

    def test_returns_false_when_missing(self) -> None:
        collector = ScreenTimeCollector(Path("/nonexistent/path/knowledgeC.db"))
        assert collector.is_available() is False

    def test_collect_returns_empty_when_unavailable(self) -> None:
        collector = ScreenTimeCollector(Path("/nonexistent/path/knowledgeC.db"))
        events = collector.collect_for_date(date(2026, 4, 6))
        assert events == []

    def test_returns_false_on_permission_error(self, tmp_path: Path) -> None:
        db_path = tmp_path / "knowledgeC.db"
        db_path.touch()
        collector = ScreenTimeCollector(db_path)
        with patch("builtins.open", side_effect=PermissionError("access denied")):
            assert collector.is_available() is False


# ------------------------------------------------------------------
# 4. Duration calculation
# ------------------------------------------------------------------


class TestDuration:
    def test_positive_duration(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        start = datetime(2026, 4, 6, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 6, 10, 45, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [(_dt_to_mac(start), _dt_to_mac(end), STREAM_APP_USAGE, "com.microsoft.VSCode")],
        )

        collector = ScreenTimeCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].duration_seconds == pytest.approx(2700.0)

    def test_none_end_date_yields_none_duration(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        ts = datetime(2026, 4, 6, 11, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [(_dt_to_mac(ts), None, STREAM_APP_USAGE, "com.apple.Safari")],
        )

        collector = ScreenTimeCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].duration_seconds is None

    def test_negative_duration_treated_as_none(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        start = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
        bad_end = datetime(2026, 4, 6, 11, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [(_dt_to_mac(start), _dt_to_mac(bad_end), STREAM_APP_USAGE, "com.apple.Safari")],
        )

        collector = ScreenTimeCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].duration_seconds is None


# ------------------------------------------------------------------
# 5. Edge cases
# ------------------------------------------------------------------


class TestEdgeCases:
    def test_returns_empty_when_table_missing(self, tmp_path: Path) -> None:
        db_path = tmp_path / "knowledgeC.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE other_table (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        collector = ScreenTimeCollector(db_path)
        events = collector.collect_for_date(date(2026, 4, 6))
        assert events == []

    def test_skips_rows_with_null_creation_date(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        good_ts = datetime(2026, 4, 6, 9, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (None, None, STREAM_APP_USAGE, "com.apple.Safari"),
                (_dt_to_mac(good_ts), _dt_to_mac(good_ts + timedelta(minutes=5)), STREAM_APP_USAGE, "com.google.Chrome"),
            ],
        )

        collector = ScreenTimeCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].title == "Chrome"

    def test_ignores_unrelated_streams(self, tmp_path: Path) -> None:
        """Events from /app/inFocus should NOT be captured by screen time collector."""
        target = date(2026, 4, 6)
        ts = datetime(2026, 4, 6, 9, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (_dt_to_mac(ts), _dt_to_mac(ts + timedelta(minutes=10)), "/app/inFocus", "com.apple.Safari"),
                (_dt_to_mac(ts), _dt_to_mac(ts + timedelta(minutes=10)), STREAM_APP_USAGE, "com.apple.Safari"),
            ],
        )

        collector = ScreenTimeCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].metadata == {"stream": STREAM_APP_USAGE}
