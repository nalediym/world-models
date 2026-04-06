"""Tests for the knowledgeC.db collector.

All tests use fixture / mock data — never real user databases.
"""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from life_world_model.collectors.knowledgec import (
    MAC_EPOCH,
    STREAM_APP_IN_FOCUS,
    STREAM_DEVICE_UNLOCKED,
    STREAM_SAFARI_HISTORY,
    KnowledgeCCollector,
    bundle_id_to_app_name,
    mac_epoch_to_datetime,
)
from life_world_model.types import RawEvent


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _dt_to_mac_seconds(dt: datetime) -> float:
    """Convert a timezone-aware datetime to Mac epoch seconds."""
    return (dt - MAC_EPOCH).total_seconds()


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
# 1. mac_epoch_to_datetime
# ------------------------------------------------------------------


class TestMacEpochToDatetime:
    def test_epoch_zero_returns_2001_01_01(self) -> None:
        result = mac_epoch_to_datetime(0.0)
        assert result == datetime(2001, 1, 1, tzinfo=timezone.utc)

    def test_known_timestamp(self) -> None:
        # 2026-04-06 12:00:00 UTC
        target = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
        seconds = (target - MAC_EPOCH).total_seconds()
        assert mac_epoch_to_datetime(seconds) == target

    def test_result_has_timezone(self) -> None:
        result = mac_epoch_to_datetime(1000.0)
        assert result.tzinfo is not None


# ------------------------------------------------------------------
# 2. bundle_id_to_app_name
# ------------------------------------------------------------------


class TestBundleIdToAppName:
    @pytest.mark.parametrize(
        "bundle_id, expected",
        [
            ("com.apple.Safari", "Safari"),
            ("com.google.Chrome", "Chrome"),
            ("com.microsoft.VSCode", "VS Code"),
            ("com.todesktop.runtime.cursor", "Cursor"),
            ("com.tinyspeck.slackmacgap", "Slack"),
            ("com.apple.mail", "Mail"),
            ("com.apple.Terminal", "Terminal"),
            ("com.googlecode.iterm2", "iTerm2"),
            ("com.apple.finder", "Finder"),
            ("com.anthropic.claudecode", "Claude Code"),
        ],
    )
    def test_known_bundle_ids(self, bundle_id: str, expected: str) -> None:
        assert bundle_id_to_app_name(bundle_id) == expected

    def test_unknown_bundle_id_uses_last_component(self) -> None:
        assert bundle_id_to_app_name("com.example.SuperApp") == "SuperApp"

    def test_single_component_bundle_id(self) -> None:
        assert bundle_id_to_app_name("MyApp") == "MyApp"

    def test_none_returns_unknown(self) -> None:
        assert bundle_id_to_app_name(None) == "Unknown"

    def test_empty_string_returns_unknown(self) -> None:
        assert bundle_id_to_app_name("") == "Unknown"


# ------------------------------------------------------------------
# 3. collect_for_date — parses rows into RawEvents
# ------------------------------------------------------------------


class TestCollectForDate:
    def test_parses_app_in_focus_rows(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        day_start = datetime(2026, 4, 6, 9, 0, 0, tzinfo=timezone.utc)
        day_end = datetime(2026, 4, 6, 9, 30, 0, tzinfo=timezone.utc)

        creation = _dt_to_mac_seconds(day_start)
        end = _dt_to_mac_seconds(day_end)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (creation, end, STREAM_APP_IN_FOCUS, "com.apple.Safari"),
            ],
        )

        collector = KnowledgeCCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        event = events[0]
        assert event.source == "knowledgec"
        assert event.title == "Safari"
        assert event.domain == "com.apple.Safari"
        assert event.timestamp == day_start
        assert event.duration_seconds == pytest.approx(1800.0)

    def test_parses_safari_history_rows(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        ts = datetime(2026, 4, 6, 10, 15, 0, tzinfo=timezone.utc)
        creation = _dt_to_mac_seconds(ts)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (creation, None, STREAM_SAFARI_HISTORY, "https://example.com/page"),
            ],
        )

        collector = KnowledgeCCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        event = events[0]
        assert event.title == "Safari History"
        assert event.url == "https://example.com/page"
        assert event.domain == "example.com"
        assert event.duration_seconds is None

    def test_parses_device_unlocked_rows(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        ts = datetime(2026, 4, 6, 8, 0, 0, tzinfo=timezone.utc)
        creation = _dt_to_mac_seconds(ts)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (creation, _dt_to_mac_seconds(ts + timedelta(seconds=5)), STREAM_DEVICE_UNLOCKED, None),
            ],
        )

        collector = KnowledgeCCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].title == "Device Unlocked"

    def test_multiple_streams_in_one_day(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        base = datetime(2026, 4, 6, 9, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (_dt_to_mac_seconds(base), _dt_to_mac_seconds(base + timedelta(minutes=10)), STREAM_APP_IN_FOCUS, "com.google.Chrome"),
                (_dt_to_mac_seconds(base + timedelta(minutes=15)), None, STREAM_SAFARI_HISTORY, "https://news.ycombinator.com"),
                (_dt_to_mac_seconds(base + timedelta(minutes=30)), _dt_to_mac_seconds(base + timedelta(minutes=30, seconds=2)), STREAM_DEVICE_UNLOCKED, None),
            ],
        )

        collector = KnowledgeCCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 3
        assert events[0].title == "Chrome"
        assert events[1].title == "Safari History"
        assert events[2].title == "Device Unlocked"

    def test_filters_out_events_from_other_days(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        in_range = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
        out_of_range = datetime(2026, 4, 7, 1, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (_dt_to_mac_seconds(in_range), None, STREAM_APP_IN_FOCUS, "com.apple.Safari"),
                (_dt_to_mac_seconds(out_of_range), None, STREAM_APP_IN_FOCUS, "com.google.Chrome"),
            ],
        )

        collector = KnowledgeCCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].title == "Safari"

    def test_all_timestamps_have_timezone(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        ts = datetime(2026, 4, 6, 14, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (_dt_to_mac_seconds(ts), _dt_to_mac_seconds(ts + timedelta(minutes=5)), STREAM_APP_IN_FOCUS, "com.apple.Terminal"),
            ],
        )

        collector = KnowledgeCCollector(db_path)
        events = collector.collect_for_date(target)

        for event in events:
            assert event.timestamp.tzinfo is not None, f"Event {event} missing timezone"


# ------------------------------------------------------------------
# 4. is_available — graceful handling when DB is missing
# ------------------------------------------------------------------


class TestIsAvailable:
    def test_returns_true_when_db_exists(self, tmp_path: Path) -> None:
        db_path = tmp_path / "knowledgeC.db"
        db_path.touch()
        collector = KnowledgeCCollector(db_path)
        assert collector.is_available() is True

    def test_returns_false_when_missing(self) -> None:
        collector = KnowledgeCCollector(Path("/nonexistent/path/knowledgeC.db"))
        assert collector.is_available() is False

    def test_collect_returns_empty_when_unavailable(self) -> None:
        collector = KnowledgeCCollector(Path("/nonexistent/path/knowledgeC.db"))
        events = collector.collect_for_date(date(2026, 4, 6))
        assert events == []


# ------------------------------------------------------------------
# 5. Duration calculation
# ------------------------------------------------------------------


class TestDurationCalculation:
    def test_positive_duration(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        start = datetime(2026, 4, 6, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 6, 10, 45, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (_dt_to_mac_seconds(start), _dt_to_mac_seconds(end), STREAM_APP_IN_FOCUS, "com.microsoft.VSCode"),
            ],
        )

        collector = KnowledgeCCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].duration_seconds == pytest.approx(2700.0)  # 45 minutes

    def test_zero_duration(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        ts = datetime(2026, 4, 6, 11, 0, 0, tzinfo=timezone.utc)
        mac_ts = _dt_to_mac_seconds(ts)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (mac_ts, mac_ts, STREAM_APP_IN_FOCUS, "com.apple.finder"),
            ],
        )

        collector = KnowledgeCCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].duration_seconds == pytest.approx(0.0)

    def test_none_end_date_yields_none_duration(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        ts = datetime(2026, 4, 6, 11, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (_dt_to_mac_seconds(ts), None, STREAM_APP_IN_FOCUS, "com.apple.Safari"),
            ],
        )

        collector = KnowledgeCCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].duration_seconds is None

    def test_negative_duration_treated_as_none(self, tmp_path: Path) -> None:
        """If ZENDDATE < ZCREATIONDATE for some reason, duration should be None."""
        target = date(2026, 4, 6)
        start = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
        bad_end = datetime(2026, 4, 6, 11, 0, 0, tzinfo=timezone.utc)  # before start

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (_dt_to_mac_seconds(start), _dt_to_mac_seconds(bad_end), STREAM_APP_IN_FOCUS, "com.apple.Safari"),
            ],
        )

        collector = KnowledgeCCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].duration_seconds is None


# ------------------------------------------------------------------
# Edge cases: unexpected DB structure
# ------------------------------------------------------------------


class TestUnexpectedDbStructure:
    def test_returns_empty_when_table_missing(self, tmp_path: Path) -> None:
        """If the DB exists but has no ZOBJECT table, return [] without crashing."""
        db_path = tmp_path / "knowledgeC.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE other_table (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        collector = KnowledgeCCollector(db_path)
        events = collector.collect_for_date(date(2026, 4, 6))

        assert events == []

    def test_skips_rows_with_null_creation_date(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        good_ts = datetime(2026, 4, 6, 9, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "knowledgeC.db"
        _create_fixture_db(
            db_path,
            [
                (None, None, STREAM_APP_IN_FOCUS, "com.apple.Safari"),
                (_dt_to_mac_seconds(good_ts), None, STREAM_APP_IN_FOCUS, "com.google.Chrome"),
            ],
        )

        collector = KnowledgeCCollector(db_path)
        events = collector.collect_for_date(target)

        # The NULL-timestamp row is skipped; only the valid row remains.
        assert len(events) == 1
        assert events[0].title == "Chrome"
