"""Tests for the Safari History collector.

All tests use fixture / mock data — never real user databases.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from life_world_model.collectors.safari_history import (
    SafariHistoryCollector,
    _resolve_domain,
)
from life_world_model.types import RawEvent
from life_world_model.utils.timestamps import MAC_EPOCH, mac_epoch_from_datetime


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _dt_to_mac(dt: datetime) -> float:
    """Convert a timezone-aware datetime to Mac epoch seconds."""
    return mac_epoch_from_datetime(dt)


def _create_safari_db(path: Path, rows: list[tuple]) -> None:
    """Create a minimal Safari History.db with the given rows.

    Each row is ``(url, visit_time_mac_epoch, title)``.
    """
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE history_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            domain_expansion TEXT NULL,
            visit_count INTEGER NOT NULL DEFAULT 1,
            daily_visit_counts BLOB NOT NULL DEFAULT X'00',
            should_recompute_derived_visit_counts INTEGER NOT NULL DEFAULT 0,
            visit_count_score INTEGER NOT NULL DEFAULT 0,
            status_code INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE history_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            history_item INTEGER NOT NULL REFERENCES history_items(id),
            visit_time REAL NOT NULL,
            title TEXT NULL,
            load_successful BOOLEAN NOT NULL DEFAULT 1,
            http_non_get BOOLEAN NOT NULL DEFAULT 0,
            synthesized BOOLEAN NOT NULL DEFAULT 0,
            origin INTEGER NOT NULL DEFAULT 0,
            generation INTEGER NOT NULL DEFAULT 0,
            attributes INTEGER NOT NULL DEFAULT 0,
            score INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    for i, (url, visit_time, title) in enumerate(rows, start=1):
        conn.execute(
            "INSERT INTO history_items (id, url) VALUES (?, ?)",
            (i, url),
        )
        conn.execute(
            "INSERT INTO history_visits (history_item, visit_time, title) VALUES (?, ?, ?)",
            (i, visit_time, title),
        )
    conn.commit()
    conn.close()


# ------------------------------------------------------------------
# 1. _resolve_domain
# ------------------------------------------------------------------


class TestResolveDomain:
    def test_extracts_domain_from_url(self) -> None:
        assert _resolve_domain("https://github.com/user/repo") == "github.com"

    def test_returns_none_for_none(self) -> None:
        assert _resolve_domain(None) is None

    def test_returns_none_for_empty_string(self) -> None:
        assert _resolve_domain("") is None

    def test_handles_url_with_port(self) -> None:
        assert _resolve_domain("http://localhost:3000/path") == "localhost:3000"


# ------------------------------------------------------------------
# 2. collect_for_date
# ------------------------------------------------------------------


class TestCollectForDate:
    def test_parses_history_rows(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        ts = datetime(2026, 4, 6, 10, 30, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "History.db"
        _create_safari_db(
            db_path,
            [("https://example.com/page", _dt_to_mac(ts), "Example Page")],
        )

        collector = SafariHistoryCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        event = events[0]
        assert isinstance(event, RawEvent)
        assert event.source == "safari"
        assert event.title == "Example Page"
        assert event.domain == "example.com"
        assert event.url == "https://example.com/page"
        assert event.timestamp.tzinfo is not None

    def test_filters_events_from_other_days(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        in_range = datetime(2026, 4, 6, 14, 0, 0, tzinfo=timezone.utc)
        out_of_range = datetime(2026, 4, 7, 2, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "History.db"
        _create_safari_db(
            db_path,
            [
                ("https://example.com/today", _dt_to_mac(in_range), "Today"),
                ("https://example.com/tomorrow", _dt_to_mac(out_of_range), "Tomorrow"),
            ],
        )

        collector = SafariHistoryCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].title == "Today"

    def test_multiple_visits_sorted_by_time(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        base = datetime(2026, 4, 6, 8, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "History.db"
        _create_safari_db(
            db_path,
            [
                ("https://news.ycombinator.com", _dt_to_mac(base), "HN"),
                ("https://github.com", _dt_to_mac(base + timedelta(hours=2)), "GitHub"),
                ("https://docs.python.org", _dt_to_mac(base + timedelta(hours=4)), "Python Docs"),
            ],
        )

        collector = SafariHistoryCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 3
        assert [e.title for e in events] == ["HN", "GitHub", "Python Docs"]

    def test_null_title_falls_back_to_domain(self, tmp_path: Path) -> None:
        """When visit title is NULL, the event title should be the domain."""
        target = date(2026, 4, 6)
        ts = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "History.db"
        _create_safari_db(
            db_path,
            [("https://untitled-site.com/page", _dt_to_mac(ts), None)],
        )

        collector = SafariHistoryCollector(db_path)
        events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].title == "untitled-site.com"

    def test_all_timestamps_have_timezone(self, tmp_path: Path) -> None:
        target = date(2026, 4, 6)
        ts = datetime(2026, 4, 6, 9, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "History.db"
        _create_safari_db(
            db_path,
            [("https://example.com", _dt_to_mac(ts), "Example")],
        )

        collector = SafariHistoryCollector(db_path)
        events = collector.collect_for_date(target)

        for event in events:
            assert event.timestamp.tzinfo is not None


# ------------------------------------------------------------------
# 3. is_available
# ------------------------------------------------------------------


class TestIsAvailable:
    def test_returns_true_when_db_exists(self, tmp_path: Path) -> None:
        db_path = tmp_path / "History.db"
        db_path.touch()
        collector = SafariHistoryCollector(db_path)
        assert collector.is_available() is True

    def test_returns_false_when_missing(self) -> None:
        collector = SafariHistoryCollector(Path("/nonexistent/path/History.db"))
        assert collector.is_available() is False

    def test_collect_returns_empty_when_unavailable(self) -> None:
        collector = SafariHistoryCollector(Path("/nonexistent/path/History.db"))
        events = collector.collect_for_date(date(2026, 4, 6))
        assert events == []

    def test_returns_false_on_permission_error(self, tmp_path: Path) -> None:
        db_path = tmp_path / "History.db"
        db_path.touch()
        collector = SafariHistoryCollector(db_path)
        with patch("builtins.open", side_effect=PermissionError("access denied")):
            assert collector.is_available() is False


# ------------------------------------------------------------------
# 4. Edge cases
# ------------------------------------------------------------------


class TestEdgeCases:
    def test_returns_empty_on_malformed_database(self, tmp_path: Path) -> None:
        """A valid SQLite file without expected tables should return []."""
        db_path = tmp_path / "History.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE something_else (id INTEGER)")
        conn.commit()
        conn.close()

        collector = SafariHistoryCollector(db_path)
        events = collector.collect_for_date(date(2026, 4, 6))
        assert events == []

    def test_returns_empty_on_permission_error_during_copy(self, tmp_path: Path) -> None:
        db_path = tmp_path / "History.db"
        db_path.touch()

        collector = SafariHistoryCollector(db_path)
        with patch("shutil.copy2", side_effect=PermissionError("access denied")):
            events = collector.collect_for_date(date(2026, 4, 6))
        assert events == []

    def test_skips_rows_with_null_visit_time(self, tmp_path: Path) -> None:
        """Rows with NULL visit_time should be skipped.

        Note: visit_time is NOT NULL in the schema, but we handle it defensively.
        We test this by inserting directly with raw SQL.
        """
        target = date(2026, 4, 6)
        good_ts = datetime(2026, 4, 6, 10, 0, 0, tzinfo=timezone.utc)

        db_path = tmp_path / "History.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE history_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                domain_expansion TEXT NULL,
                visit_count INTEGER NOT NULL DEFAULT 1,
                daily_visit_counts BLOB NOT NULL DEFAULT X'00',
                should_recompute_derived_visit_counts INTEGER NOT NULL DEFAULT 0,
                visit_count_score INTEGER NOT NULL DEFAULT 0,
                status_code INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE history_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                history_item INTEGER NOT NULL,
                visit_time REAL,
                title TEXT NULL,
                load_successful BOOLEAN NOT NULL DEFAULT 1,
                http_non_get BOOLEAN NOT NULL DEFAULT 0,
                synthesized BOOLEAN NOT NULL DEFAULT 0,
                origin INTEGER NOT NULL DEFAULT 0,
                generation INTEGER NOT NULL DEFAULT 0,
                attributes INTEGER NOT NULL DEFAULT 0,
                score INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute("INSERT INTO history_items (id, url) VALUES (1, 'https://null.example.com')")
        conn.execute("INSERT INTO history_items (id, url) VALUES (2, 'https://good.example.com')")
        conn.execute("INSERT INTO history_visits (history_item, visit_time, title) VALUES (1, NULL, 'Null')")
        conn.execute(
            "INSERT INTO history_visits (history_item, visit_time, title) VALUES (2, ?, 'Good')",
            (_dt_to_mac(good_ts),),
        )
        conn.commit()
        conn.close()

        collector = SafariHistoryCollector(db_path)
        events = collector.collect_for_date(target)

        # The NULL visit_time row won't match the date range, only the good one appears.
        assert len(events) == 1
        assert events[0].title == "Good"
