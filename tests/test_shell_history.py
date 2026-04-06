"""Tests for the shell (zsh) history collector."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from life_world_model.collectors.shell_history import ShellHistoryCollector


def test_parse_zsh_history_line(tmp_path: Path) -> None:
    """Verify parsing of a standard `: EPOCH:0;command` line."""
    history = tmp_path / ".zsh_history"
    # 1712435820 == 2024-04-06 20:37:00 UTC
    history.write_text(": 1712435820:0;git status\n", encoding="utf-8")

    collector = ShellHistoryCollector(history)
    events = collector.collect_for_date(date(2024, 4, 6))

    assert len(events) == 1
    event = events[0]
    assert event.source == "shell"
    assert event.title == "git status"
    assert event.domain == "terminal"
    assert event.timestamp == datetime(2024, 4, 6, 20, 37, 0, tzinfo=timezone.utc)


def test_parse_line_with_duration(tmp_path: Path) -> None:
    """Verify parsing of a line with non-zero duration."""
    history = tmp_path / ".zsh_history"
    history.write_text(": 1712435820:30;make build\n", encoding="utf-8")

    collector = ShellHistoryCollector(history)
    events = collector.collect_for_date(date(2024, 4, 6))

    assert len(events) == 1
    assert events[0].title == "make build"
    assert events[0].timestamp.tzinfo is not None


def test_skip_malformed_lines(tmp_path: Path) -> None:
    """Lines without the timestamp prefix are silently skipped."""
    history = tmp_path / ".zsh_history"
    lines = [
        ": 1712435820:0;good line\n",
        "bad line without prefix\n",
        "another bad line\n",
        ": 1712435880:0;also good\n",
    ]
    history.write_text("".join(lines), encoding="utf-8")

    collector = ShellHistoryCollector(history)
    events = collector.collect_for_date(date(2024, 4, 6))

    assert len(events) == 2
    assert events[0].title == "good line"
    assert events[1].title == "also good"


def test_filter_to_target_date(tmp_path: Path) -> None:
    """Only events matching the target date are returned."""
    history = tmp_path / ".zsh_history"
    lines = [
        # 2024-04-06 22:57:00 UTC
        ": 1712435820:0;on target day\n",
        # 2024-04-07 00:00:00 UTC  (next day)
        ": 1712448000:0;next day command\n",
        # 2024-04-05 12:00:00 UTC  (previous day)
        ": 1712318400:0;previous day command\n",
    ]
    history.write_text("".join(lines), encoding="utf-8")

    collector = ShellHistoryCollector(history)
    events = collector.collect_for_date(date(2024, 4, 6))

    assert len(events) == 1
    assert events[0].title == "on target day"


def test_is_available_returns_false_when_missing(tmp_path: Path) -> None:
    """is_available() returns False when the history file does not exist."""
    missing_path = tmp_path / "nonexistent" / ".zsh_history"
    collector = ShellHistoryCollector(missing_path)

    assert collector.is_available() is False


def test_is_available_returns_true_when_present(tmp_path: Path) -> None:
    """is_available() returns True when the history file exists."""
    history = tmp_path / ".zsh_history"
    history.write_text("", encoding="utf-8")
    collector = ShellHistoryCollector(history)

    assert collector.is_available() is True


def test_collect_empty_file(tmp_path: Path) -> None:
    """An empty history file returns an empty list (no crash)."""
    history = tmp_path / ".zsh_history"
    history.write_text("", encoding="utf-8")

    collector = ShellHistoryCollector(history)
    events = collector.collect_for_date(date(2024, 4, 6))

    assert events == []


def test_collect_missing_file_returns_empty(tmp_path: Path) -> None:
    """A missing history file returns an empty list (no crash)."""
    missing_path = tmp_path / "nonexistent_history"
    collector = ShellHistoryCollector(missing_path)

    events = collector.collect_for_date(date(2024, 4, 6))
    assert events == []
