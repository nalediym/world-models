"""Tests for the git activity collector."""

from __future__ import annotations

import subprocess
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from life_world_model.collectors.git_activity import (
    GitActivityCollector,
    _find_repos,
    _parse_log_line,
    _repo_name,
)
from life_world_model.types import RawEvent


# ---------------------------------------------------------------------------
# _parse_log_line
# ---------------------------------------------------------------------------

class TestParseGitLogLine:
    def test_basic_line(self) -> None:
        line = "abc123|2026-04-05T14:30:00+02:00|feat: add widget"
        result = _parse_log_line(line)
        assert result is not None
        commit_hash, ts, message = result
        assert commit_hash == "abc123"
        assert ts == datetime.fromisoformat("2026-04-05T14:30:00+02:00")
        assert message == "feat: add widget"

    def test_pipe_in_message(self) -> None:
        """Pipe characters inside the commit message must be preserved."""
        line = "def456|2026-04-05T09:00:00+00:00|fix: handle a|b|c edge case"
        result = _parse_log_line(line)
        assert result is not None
        commit_hash, ts, message = result
        assert commit_hash == "def456"
        assert message == "fix: handle a|b|c edge case"

    def test_malformed_line_returns_none(self) -> None:
        assert _parse_log_line("no-pipes-here") is None

    def test_bad_date_returns_none(self) -> None:
        assert _parse_log_line("abc|not-a-date|message") is None


# ---------------------------------------------------------------------------
# _repo_name
# ---------------------------------------------------------------------------

class TestRepoName:
    def test_extracts_directory_name(self) -> None:
        assert _repo_name(Path("/home/user/Projects/world-models")) == "world-models"

    def test_trailing_slash_handled(self) -> None:
        # Path normalises trailing slashes anyway
        assert _repo_name(Path("/some/path/my-repo/")) == "my-repo"

    def test_nested_path(self) -> None:
        assert _repo_name(Path("/a/b/c/d")) == "d"


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------

class TestIsAvailable:
    def test_returns_false_when_no_scan_paths(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does-not-exist"
        collector = GitActivityCollector(scan_paths=[nonexistent])
        assert collector.is_available() is False

    def test_returns_true_when_path_exists(self, tmp_path: Path) -> None:
        collector = GitActivityCollector(scan_paths=[tmp_path])
        assert collector.is_available() is True


# ---------------------------------------------------------------------------
# _find_repos (uses real filesystem via tmp_path)
# ---------------------------------------------------------------------------

class TestFindRepos:
    def test_finds_git_dirs(self, tmp_path: Path) -> None:
        repo_a = tmp_path / "repo-a"
        repo_b = tmp_path / "repo-b"
        not_a_repo = tmp_path / "plain-dir"

        repo_a.mkdir()
        (repo_a / ".git").mkdir()
        (repo_a / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        repo_b.mkdir()
        (repo_b / ".git").mkdir()
        (repo_b / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        not_a_repo.mkdir()

        repos = _find_repos([tmp_path])
        names = [r.name for r in repos]
        assert "repo-a" in names
        assert "repo-b" in names
        assert "plain-dir" not in names

    def test_ignores_nested_git(self, tmp_path: Path) -> None:
        """Only scan one level deep, not nested repos."""
        outer = tmp_path / "outer"
        outer.mkdir()
        (outer / ".git").mkdir()
        (outer / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        inner = outer / "inner"
        inner.mkdir()
        (inner / ".git").mkdir()
        (inner / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

        repos = _find_repos([tmp_path])
        names = [r.name for r in repos]
        assert "outer" in names
        assert "inner" not in names


# ---------------------------------------------------------------------------
# collect_for_date with mocked subprocess
# ---------------------------------------------------------------------------

GIT_LOG_OUTPUT = (
    "aaa111|2026-04-05T10:00:00+00:00|feat: first commit\n"
    "bbb222|2026-04-05T15:30:00+00:00|fix: second commit\n"
)


class TestCollectForDate:
    def test_returns_raw_events_from_subprocess(self, tmp_path: Path) -> None:
        """Mock subprocess.run and verify RawEvent creation."""
        repo = tmp_path / "my-repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = GIT_LOG_OUTPUT
        mock_result.stderr = ""

        collector = GitActivityCollector(scan_paths=[tmp_path])

        with patch("life_world_model.collectors.git_activity.subprocess.run", return_value=mock_result) as mock_run:
            events = collector.collect_for_date(date(2026, 4, 5))

        assert len(events) == 2
        assert all(isinstance(e, RawEvent) for e in events)

        first = events[0]
        assert first.source == "git"
        assert first.title == "feat: first commit"
        assert first.domain == "my-repo"
        assert first.url == "aaa111"
        assert first.timestamp == datetime(2026, 4, 5, 10, 0, 0, tzinfo=timezone.utc)

        # Verify git was called with correct date range
        call_args = mock_run.call_args[0][0]
        assert "--after=2026-04-05" in call_args
        assert "--before=2026-04-06" in call_args

    def test_empty_output_returns_no_events(self, tmp_path: Path) -> None:
        repo = tmp_path / "empty-repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        collector = GitActivityCollector(scan_paths=[tmp_path])

        with patch("life_world_model.collectors.git_activity.subprocess.run", return_value=mock_result):
            events = collector.collect_for_date(date(2026, 4, 5))

        assert events == []

    def test_subprocess_timeout_handled(self, tmp_path: Path) -> None:
        """A timeout must not crash the collector — it should skip the repo."""
        repo = tmp_path / "slow-repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

        collector = GitActivityCollector(scan_paths=[tmp_path])

        with patch(
            "life_world_model.collectors.git_activity.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=10),
        ):
            events = collector.collect_for_date(date(2026, 4, 5))

        assert events == []

    def test_nonzero_returncode_skips_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "broken-repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        mock_result.stderr = "fatal: bad default revision 'HEAD'"

        collector = GitActivityCollector(scan_paths=[tmp_path])

        with patch("life_world_model.collectors.git_activity.subprocess.run", return_value=mock_result):
            events = collector.collect_for_date(date(2026, 4, 5))

        assert events == []

    def test_multiple_repos_combined(self, tmp_path: Path) -> None:
        """Events from multiple repos are collected into a single list."""
        for name in ("alpha", "beta"):
            r = tmp_path / name
            r.mkdir()
            (r / ".git").mkdir()
            (r / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ccc333|2026-04-05T12:00:00+00:00|chore: update deps\n"
        mock_result.stderr = ""

        collector = GitActivityCollector(scan_paths=[tmp_path])

        with patch("life_world_model.collectors.git_activity.subprocess.run", return_value=mock_result):
            events = collector.collect_for_date(date(2026, 4, 5))

        # Two repos, each returning one commit
        assert len(events) == 2
        domains = {e.domain for e in events}
        assert domains == {"alpha", "beta"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_collector_is_registered(self) -> None:
        from life_world_model.collectors.base import COLLECTOR_REGISTRY

        assert "git" in COLLECTOR_REGISTRY
        assert COLLECTOR_REGISTRY["git"] is GitActivityCollector
