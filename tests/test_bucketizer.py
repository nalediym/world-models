from __future__ import annotations

from datetime import datetime

from life_world_model.pipeline.bucketizer import build_life_states
from life_world_model.types import RawEvent


def test_build_life_states_groups_into_15_minute_windows() -> None:
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="chrome",
            title="World models paper",
            domain="arxiv.org",
            url="https://arxiv.org/abs/1234",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:11:00"),
            source="chrome",
            title="GitHub repo",
            domain="github.com",
            url="https://github.com/example",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:21:00"),
            source="chrome",
            title="Search results",
            domain="google.com",
            url="https://google.com/search?q=world+models",
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert [state.timestamp.strftime("%H:%M") for state in states] == ["09:00", "09:15"]
    assert states[0].event_count == 2
    assert states[1].event_count == 1


def test_build_life_states_marks_empty_bucket_as_idle() -> None:
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="chrome",
            title="GitHub repo",
            domain="github.com",
            url="https://github.com/example",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:33:00"),
            source="chrome",
            title="Later visit",
            domain="github.com",
            url="https://github.com/example/issues",
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert [state.timestamp.strftime("%H:%M") for state in states] == ["09:00", "09:15", "09:30"]
    assert states[1].primary_activity == "idle"
    assert states[1].event_count == 0


def test_build_life_states_labels_github_heavy_bucket() -> None:
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="chrome",
            title="GitHub pull request",
            domain="github.com",
            url="https://github.com/example/pull/1",
        )
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert states[0].primary_activity == "research"


# ---------------------------------------------------------------------------
# Multi-source priority cascade tests
# ---------------------------------------------------------------------------


def test_calendar_event_overrides_other_sources() -> None:
    """Calendar source takes the highest priority — overrides chrome and knowledgeC."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="calendar",
            title="Team standup",
            domain="calendar",
            duration_seconds=1800,
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:05:00"),
            source="chrome",
            title="GitHub pull request",
            domain="github.com",
            url="https://github.com/example/pull/1",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:08:00"),
            source="knowledgec",
            title="VS Code",
            domain="com.microsoft.VSCode",
            duration_seconds=600,
            metadata={"stream": "/app/inFocus"},
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert states[0].primary_activity == "meeting"
    assert states[0].secondary_activity == "Team standup"
    assert states[0].confidence == 0.95


def test_knowledgec_app_maps_to_activity() -> None:
    """knowledgeC bundle IDs are mapped to activity categories."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="knowledgec",
            title="VS Code",
            domain="com.microsoft.VSCode",
            duration_seconds=600,
            metadata={"stream": "/app/inFocus"},
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert states[0].primary_activity == "coding"
    assert states[0].confidence == 0.85


def test_knowledgec_slack_maps_to_communication() -> None:
    """Slack bundle ID maps to communication activity."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="knowledgec",
            title="Slack",
            domain="com.tinyspeck.slackmacgap",
            duration_seconds=300,
            metadata={"stream": "/app/inFocus"},
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert states[0].primary_activity == "communication"
    assert states[0].confidence == 0.80


def test_knowledgec_claude_maps_to_ai_tooling() -> None:
    """Claude Code bundle ID maps to ai_tooling activity."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="knowledgec",
            title="Claude Code",
            domain="com.anthropic.claudecode",
            duration_seconds=500,
            metadata={"stream": "/app/inFocus"},
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert states[0].primary_activity == "ai_tooling"
    assert states[0].confidence == 0.85


def test_knowledgec_finder_maps_to_file_management() -> None:
    """Finder bundle ID maps to file_management activity."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="knowledgec",
            title="Finder",
            domain="com.apple.finder",
            duration_seconds=200,
            metadata={"stream": "/app/inFocus"},
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert states[0].primary_activity == "file_management"
    assert states[0].confidence == 0.70


def test_knowledgec_browser_refines_by_url() -> None:
    """When knowledgeC reports a browser, URL events refine the classification."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="knowledgec",
            title="Chrome",
            domain="com.google.Chrome",
            duration_seconds=600,
            metadata={"stream": "/app/inFocus"},
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:03:00"),
            source="chrome",
            title="GitHub PR review",
            domain="github.com",
            url="https://github.com/example/pull/1",
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert states[0].primary_activity == "research"


def test_multi_source_sets_sources_field() -> None:
    """When multiple sources contribute to a bucket, all are listed in sources."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="chrome",
            title="GitHub PR",
            domain="github.com",
            url="https://github.com/example/pull/1",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:05:00"),
            source="git",
            title="fix: resolve merge conflict",
            domain="world-models",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:10:00"),
            source="shell",
            title="git push origin main",
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert sorted(states[0].sources) == ["chrome", "git", "shell"]


def test_git_commit_detected_as_coding() -> None:
    """Git source events are classified as coding with 0.90 confidence."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="git",
            title="feat: add bucketing pipeline",
            domain="world-models",
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert states[0].primary_activity == "coding"
    assert states[0].confidence == 0.90


def test_shell_command_detected_as_coding() -> None:
    """Shell source events are classified as coding with 0.70 confidence."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="shell",
            title="uv run pytest tests/ -v",
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert states[0].primary_activity == "coding"
    assert states[0].confidence == 0.70


def test_knowledgec_longest_duration_wins() -> None:
    """When multiple knowledgeC apps are in a bucket, the longest duration wins."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="knowledgec",
            title="Slack",
            domain="com.tinyspeck.slackmacgap",
            duration_seconds=200,
            metadata={"stream": "/app/inFocus"},
        ),
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:05:00"),
            source="knowledgec",
            title="VS Code",
            domain="com.microsoft.VSCode",
            duration_seconds=600,
            metadata={"stream": "/app/inFocus"},
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert states[0].primary_activity == "coding"


def test_chrome_only_fallback_still_works() -> None:
    """When only Chrome events exist (no knowledgeC), keyword matching still works."""
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat("2026-03-21T09:02:00"),
            source="chrome",
            title="Gmail inbox",
            domain="mail.google.com",
            url="https://mail.google.com/mail/u/0/#inbox",
        ),
    ]

    states = build_life_states(events, bucket_minutes=15)

    assert states[0].primary_activity == "communication"
