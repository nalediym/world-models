"""Tests for the Apple Calendar collector."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from life_world_model.collectors.calendar import (
    MAC_EPOCH,
    CACHE_FILENAME,
    CalendarCollector,
    datetime_to_mac_epoch,
    mac_epoch_to_datetime,
)
from life_world_model.types import RawEvent


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _create_calendar_cache(db_path: Path, rows: list[tuple[str | None, float, float | None]]) -> None:
    """Create a minimal Calendar Cache database at *db_path* with the given rows.

    Each row is ``(title, start_mac_epoch, end_mac_epoch | None)``.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE ZCALENDARITEM (
                ZTITLE TEXT,
                ZSTARTDATE REAL,
                ZENDDATE REAL,
                ZCALENDAR INTEGER
            )
            """
        )
        for title, start, end in rows:
            conn.execute(
                "INSERT INTO ZCALENDARITEM (ZTITLE, ZSTARTDATE, ZENDDATE) VALUES (?, ?, ?)",
                (title, start, end),
            )
        conn.commit()


# ------------------------------------------------------------------
# Unit tests: timestamp conversion
# ------------------------------------------------------------------


def test_mac_epoch_to_datetime() -> None:
    """2001-01-01 + 0 seconds == MAC_EPOCH itself."""
    assert mac_epoch_to_datetime(0.0) == MAC_EPOCH

    # A known value: 2026-04-06 12:00:00 UTC
    target = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
    seconds = (target - MAC_EPOCH).total_seconds()
    assert mac_epoch_to_datetime(seconds) == target


def test_duration_calculation() -> None:
    """End - start should give the duration in seconds."""
    start = datetime_to_mac_epoch(datetime(2026, 4, 6, 10, 0, 0, tzinfo=timezone.utc))
    end = datetime_to_mac_epoch(datetime(2026, 4, 6, 11, 30, 0, tzinfo=timezone.utc))
    duration = end - start
    assert duration == pytest.approx(5400.0)  # 1.5 hours


# ------------------------------------------------------------------
# Integration tests: collect_for_date
# ------------------------------------------------------------------


def test_collect_for_date_parses_rows(tmp_path: Path) -> None:
    """CalendarCollector should return RawEvents for matching rows."""
    target = date(2026, 4, 6)
    day_start = datetime(2026, 4, 6, tzinfo=timezone.utc)

    event_start = datetime_to_mac_epoch(day_start + timedelta(hours=9))
    event_end = datetime_to_mac_epoch(day_start + timedelta(hours=10))

    cache_path = tmp_path / CACHE_FILENAME
    _create_calendar_cache(cache_path, [
        ("Standup", event_start, event_end),
    ])

    collector = CalendarCollector(calendar_path=tmp_path)
    events = collector.collect_for_date(target)

    assert len(events) == 1
    event = events[0]
    assert isinstance(event, RawEvent)
    assert event.source == "calendar"
    assert event.title == "Standup"
    assert event.domain == "calendar"
    assert event.duration_seconds == pytest.approx(3600.0)
    assert event.timestamp.tzinfo is not None


def test_collect_for_date_filters_other_dates(tmp_path: Path) -> None:
    """Events outside the target date should not appear."""
    target = date(2026, 4, 6)
    yesterday_start = datetime(2026, 4, 5, 10, 0, 0, tzinfo=timezone.utc)
    tomorrow_start = datetime(2026, 4, 7, 10, 0, 0, tzinfo=timezone.utc)

    cache_path = tmp_path / CACHE_FILENAME
    _create_calendar_cache(cache_path, [
        ("Yesterday meeting", datetime_to_mac_epoch(yesterday_start), datetime_to_mac_epoch(yesterday_start + timedelta(hours=1))),
        ("Tomorrow meeting", datetime_to_mac_epoch(tomorrow_start), datetime_to_mac_epoch(tomorrow_start + timedelta(hours=1))),
    ])

    collector = CalendarCollector(calendar_path=tmp_path)
    events = collector.collect_for_date(target)

    assert len(events) == 0


def test_collect_for_date_multiple_events_sorted(tmp_path: Path) -> None:
    """Multiple events on the same day should be sorted by start time."""
    target = date(2026, 4, 6)
    day_start = datetime(2026, 4, 6, tzinfo=timezone.utc)

    cache_path = tmp_path / CACHE_FILENAME
    _create_calendar_cache(cache_path, [
        ("Lunch", datetime_to_mac_epoch(day_start + timedelta(hours=12)), datetime_to_mac_epoch(day_start + timedelta(hours=13))),
        ("Standup", datetime_to_mac_epoch(day_start + timedelta(hours=9)), datetime_to_mac_epoch(day_start + timedelta(hours=9, minutes=30))),
        ("Review", datetime_to_mac_epoch(day_start + timedelta(hours=15)), datetime_to_mac_epoch(day_start + timedelta(hours=16))),
    ])

    collector = CalendarCollector(calendar_path=tmp_path)
    events = collector.collect_for_date(target)

    assert len(events) == 3
    assert [e.title for e in events] == ["Standup", "Lunch", "Review"]


# ------------------------------------------------------------------
# is_available
# ------------------------------------------------------------------


def test_is_available_returns_true_when_cache_exists(tmp_path: Path) -> None:
    """is_available returns True when the Calendar Cache file exists and is readable."""
    cache_path = tmp_path / CACHE_FILENAME
    cache_path.write_bytes(b"\x00")  # Minimal file content.

    collector = CalendarCollector(calendar_path=tmp_path)
    assert collector.is_available() is True


def test_is_available_returns_false_when_missing(tmp_path: Path) -> None:
    """is_available returns False when Calendar Cache does not exist."""
    collector = CalendarCollector(calendar_path=tmp_path)
    assert collector.is_available() is False


def test_is_available_returns_false_on_permission_error(tmp_path: Path) -> None:
    """is_available returns False when the Calendar Cache cannot be read (PermissionError)."""
    cache_path = tmp_path / CACHE_FILENAME
    cache_path.write_bytes(b"\x00")

    collector = CalendarCollector(calendar_path=tmp_path)

    with patch("builtins.open", side_effect=PermissionError("access denied")):
        # The exists() check happens on Path.exists(), which doesn't use builtins.open,
        # so we also need to make sure the file "exists" in the mocked context.
        assert collector.is_available() is False


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


def test_handles_null_titles(tmp_path: Path) -> None:
    """Events with NULL ZTITLE should be skipped (filtered by the SQL query)."""
    target = date(2026, 4, 6)
    day_start = datetime(2026, 4, 6, tzinfo=timezone.utc)

    event_start = datetime_to_mac_epoch(day_start + timedelta(hours=9))
    event_end = datetime_to_mac_epoch(day_start + timedelta(hours=10))

    cache_path = tmp_path / CACHE_FILENAME
    _create_calendar_cache(cache_path, [
        (None, event_start, event_end),
        ("Real event", event_start, event_end),
    ])

    collector = CalendarCollector(calendar_path=tmp_path)
    events = collector.collect_for_date(target)

    assert len(events) == 1
    assert events[0].title == "Real event"


def test_handles_null_end_date(tmp_path: Path) -> None:
    """An event with no end date should have duration_seconds=None."""
    target = date(2026, 4, 6)
    day_start = datetime(2026, 4, 6, tzinfo=timezone.utc)
    event_start = datetime_to_mac_epoch(day_start + timedelta(hours=9))

    cache_path = tmp_path / CACHE_FILENAME
    _create_calendar_cache(cache_path, [
        ("All-day maybe", event_start, None),
    ])

    collector = CalendarCollector(calendar_path=tmp_path)
    events = collector.collect_for_date(target)

    assert len(events) == 1
    assert events[0].duration_seconds is None


def test_collect_returns_empty_when_cache_missing(tmp_path: Path) -> None:
    """collect_for_date returns [] when the Calendar Cache file does not exist."""
    collector = CalendarCollector(calendar_path=tmp_path)
    events = collector.collect_for_date(date(2026, 4, 6))
    assert events == []


def test_collect_returns_empty_on_permission_error(tmp_path: Path) -> None:
    """collect_for_date returns [] when shutil.copy2 raises PermissionError."""
    cache_path = tmp_path / CACHE_FILENAME
    cache_path.write_bytes(b"\x00")

    collector = CalendarCollector(calendar_path=tmp_path)

    with patch("shutil.copy2", side_effect=PermissionError("access denied")):
        events = collector.collect_for_date(date(2026, 4, 6))
    assert events == []


def test_collect_returns_empty_on_malformed_database(tmp_path: Path) -> None:
    """collect_for_date returns [] when the database has an unexpected schema."""
    cache_path = tmp_path / CACHE_FILENAME
    # Create a valid SQLite DB but without the expected table.
    with sqlite3.connect(cache_path) as conn:
        conn.execute("CREATE TABLE something_else (id INTEGER)")
        conn.commit()

    collector = CalendarCollector(calendar_path=tmp_path)
    events = collector.collect_for_date(date(2026, 4, 6))
    assert events == []
