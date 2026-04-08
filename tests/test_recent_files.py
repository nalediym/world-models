"""Tests for the Recent Files (mdfind / Spotlight) collector.

All tests use mocked subprocess calls — never real Spotlight queries.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from life_world_model.collectors.recent_files import (
    RecentFilesCollector,
    _is_interesting,
)
from life_world_model.types import RawEvent


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _fake_home() -> str:
    return "/Users/testuser"


# ------------------------------------------------------------------
# 1. _is_interesting filter
# ------------------------------------------------------------------


class TestIsInteresting:
    def test_projects_file_is_interesting(self) -> None:
        assert _is_interesting("/Users/me/Projects/repo/main.py", "/Users/me") is True

    def test_documents_file_is_interesting(self) -> None:
        assert _is_interesting("/Users/me/Documents/notes.txt", "/Users/me") is True

    def test_desktop_file_is_interesting(self) -> None:
        assert _is_interesting("/Users/me/Desktop/report.pdf", "/Users/me") is True

    def test_downloads_file_is_interesting(self) -> None:
        assert _is_interesting("/Users/me/Downloads/setup.dmg", "/Users/me") is True

    def test_library_is_not_interesting(self) -> None:
        assert _is_interesting("/Users/me/Library/Preferences/com.apple.plist", "/Users/me") is False

    def test_hidden_dir_is_not_interesting(self) -> None:
        assert _is_interesting("/Users/me/Projects/.hidden/file.txt", "/Users/me") is False

    def test_node_modules_is_not_interesting(self) -> None:
        assert _is_interesting("/Users/me/Projects/repo/node_modules/pkg/index.js", "/Users/me") is False

    def test_pycache_is_not_interesting(self) -> None:
        assert _is_interesting("/Users/me/Projects/repo/__pycache__/mod.pyc", "/Users/me") is False

    def test_git_dir_is_not_interesting(self) -> None:
        assert _is_interesting("/Users/me/Projects/repo/.git/objects/abc", "/Users/me") is False

    def test_system_path_is_not_interesting(self) -> None:
        assert _is_interesting("/usr/local/bin/python3", "/Users/me") is False


# ------------------------------------------------------------------
# 2. is_available
# ------------------------------------------------------------------


class TestIsAvailable:
    def test_available_when_mdfind_exists(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/mdfind"):
            collector = RecentFilesCollector()
            assert collector.is_available() is True

    def test_unavailable_when_mdfind_missing(self) -> None:
        with patch("shutil.which", return_value=None):
            collector = RecentFilesCollector()
            assert collector.is_available() is False


# ------------------------------------------------------------------
# 3. collect_for_date
# ------------------------------------------------------------------


class TestCollectForDate:
    def test_returns_empty_when_mdfind_missing(self) -> None:
        with patch("shutil.which", return_value=None):
            collector = RecentFilesCollector()
            events = collector.collect_for_date(date(2026, 4, 6))
            assert events == []

    def test_parses_mdfind_output(self, tmp_path: Path) -> None:
        """Mock mdfind returning file paths and verify RawEvent creation."""
        target = date(2026, 4, 6)

        # Create fake files with controlled mtimes.
        projects_dir = tmp_path / "Projects" / "repo"
        projects_dir.mkdir(parents=True)
        test_file = projects_dir / "main.py"
        test_file.write_text("print('hello')")
        # Set mtime to the target date.
        target_ts = datetime(2026, 4, 6, 14, 30, 0, tzinfo=timezone.utc).timestamp()
        os.utime(test_file, (target_ts, target_ts))

        mdfind_output = str(test_file) + "\n"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mdfind_output

        with (
            patch("shutil.which", return_value="/usr/bin/mdfind"),
            patch("subprocess.run", return_value=mock_result),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            collector = RecentFilesCollector()
            events = collector.collect_for_date(target)

        assert len(events) == 1
        event = events[0]
        assert event.source == "files"
        assert event.title == "main.py"
        assert "Projects/repo" in event.domain
        assert event.timestamp.tzinfo is not None

    def test_filters_non_interesting_paths(self, tmp_path: Path) -> None:
        """Files under ~/Library should be excluded."""
        target = date(2026, 4, 6)

        library_file = tmp_path / "Library" / "Preferences" / "com.apple.plist"
        library_file.parent.mkdir(parents=True)
        library_file.write_text("plist")

        mdfind_output = str(library_file) + "\n"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mdfind_output

        with (
            patch("shutil.which", return_value="/usr/bin/mdfind"),
            patch("subprocess.run", return_value=mock_result),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            collector = RecentFilesCollector()
            events = collector.collect_for_date(target)

        assert events == []

    def test_handles_mdfind_failure(self) -> None:
        """Non-zero returncode should result in empty list."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"

        with (
            patch("shutil.which", return_value="/usr/bin/mdfind"),
            patch("subprocess.run", return_value=mock_result),
        ):
            collector = RecentFilesCollector()
            events = collector.collect_for_date(date(2026, 4, 6))

        assert events == []

    def test_handles_mdfind_timeout(self) -> None:
        """Timeout should result in empty list, not crash."""
        import subprocess

        with (
            patch("shutil.which", return_value="/usr/bin/mdfind"),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired("mdfind", 30)),
        ):
            collector = RecentFilesCollector()
            events = collector.collect_for_date(date(2026, 4, 6))

        assert events == []

    def test_handles_deleted_file(self, tmp_path: Path) -> None:
        """Files that disappear between mdfind and stat should be skipped."""
        target = date(2026, 4, 6)
        # A path that doesn't exist on disk.
        fake_path = tmp_path / "Projects" / "repo" / "deleted.py"

        mdfind_output = str(fake_path) + "\n"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mdfind_output

        with (
            patch("shutil.which", return_value="/usr/bin/mdfind"),
            patch("subprocess.run", return_value=mock_result),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            collector = RecentFilesCollector()
            events = collector.collect_for_date(target)

        assert events == []

    def test_events_sorted_by_timestamp(self, tmp_path: Path) -> None:
        """Multiple files should be returned sorted by mtime."""
        target = date(2026, 4, 6)

        projects_dir = tmp_path / "Projects" / "repo"
        projects_dir.mkdir(parents=True)

        file_early = projects_dir / "early.py"
        file_early.write_text("a")
        ts_early = datetime(2026, 4, 6, 8, 0, 0, tzinfo=timezone.utc).timestamp()
        os.utime(file_early, (ts_early, ts_early))

        file_late = projects_dir / "late.py"
        file_late.write_text("b")
        ts_late = datetime(2026, 4, 6, 20, 0, 0, tzinfo=timezone.utc).timestamp()
        os.utime(file_late, (ts_late, ts_late))

        # Return late first in mdfind output.
        mdfind_output = f"{file_late}\n{file_early}\n"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mdfind_output

        with (
            patch("shutil.which", return_value="/usr/bin/mdfind"),
            patch("subprocess.run", return_value=mock_result),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            collector = RecentFilesCollector()
            events = collector.collect_for_date(target)

        assert len(events) == 2
        assert events[0].title == "early.py"
        assert events[1].title == "late.py"

    def test_domain_uses_tilde_prefix(self, tmp_path: Path) -> None:
        """Domain should show ~/Projects/... format."""
        target = date(2026, 4, 6)

        projects_dir = tmp_path / "Documents" / "notes"
        projects_dir.mkdir(parents=True)
        test_file = projects_dir / "todo.md"
        test_file.write_text("stuff")
        target_ts = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        os.utime(test_file, (target_ts, target_ts))

        mdfind_output = str(test_file) + "\n"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mdfind_output

        with (
            patch("shutil.which", return_value="/usr/bin/mdfind"),
            patch("subprocess.run", return_value=mock_result),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            collector = RecentFilesCollector()
            events = collector.collect_for_date(target)

        assert len(events) == 1
        assert events[0].domain.startswith("~/Documents")
