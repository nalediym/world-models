"""Tests for the LWM MCP server handler functions.

Each handler is tested directly without starting the server process.
Uses an in-memory SQLite database with fixture data.
"""

from __future__ import annotations

import json
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from life_world_model.config import Settings
from life_world_model.mcp_server.handlers import (
    handle_get_experiments,
    handle_get_goals,
    handle_get_patterns,
    handle_get_score_history,
    handle_get_sources,
    handle_get_suggestions,
    handle_get_timeline,
    handle_get_today_score,
    handle_simulate,
)
from life_world_model.mcp_server.server import TOOL_DEFS, _handle_jsonrpc
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import Experiment, ExperimentStatus, RawEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_mcp.sqlite3"


@pytest.fixture()
def settings(tmp_db: Path) -> Settings:
    return Settings(database_path=tmp_db)


@pytest.fixture()
def store(settings: Settings) -> SQLiteStore:
    s = SQLiteStore(settings.database_path)
    s.initialize()
    return s


def _seed_events(store: SQLiteStore, target_date: date, count: int = 40) -> None:
    """Seed the store with synthetic events spread across a day."""
    events: list[RawEvent] = []
    base = datetime.combine(target_date, datetime.min.time()).replace(
        tzinfo=timezone.utc, hour=8
    )
    activities = [
        ("coding", "github.com", "shell"),
        ("research", "arxiv.org", "chrome"),
        ("browsing", "reddit.com", "chrome"),
        ("communication", "slack.com", "chrome"),
    ]
    for i in range(count):
        ts = base + timedelta(minutes=i * 15)
        act_name, domain, source = activities[i % len(activities)]
        events.append(
            RawEvent(
                timestamp=ts,
                source=source,
                title=f"{act_name} item {i}",
                domain=domain,
                duration_seconds=900.0,
            )
        )
    store.save_raw_events(events)


def _seed_multi_day(store: SQLiteStore, days: int = 7) -> None:
    """Seed multiple days of data for pattern discovery."""
    today = date.today()
    for offset in range(days):
        _seed_events(store, today - timedelta(days=offset), count=30)


# ---------------------------------------------------------------------------
# get_today_score
# ---------------------------------------------------------------------------


class TestGetTodayScore:
    def test_empty_database(self, settings: Settings) -> None:
        result = handle_get_today_score(settings=settings)
        assert result["grade"] == "F"
        assert result["total"] == 0.0
        assert "note" in result

    def test_with_data(self, settings: Settings, store: SQLiteStore) -> None:
        _seed_events(store, date.today())
        result = handle_get_today_score(settings=settings)
        assert "total" in result
        assert "grade" in result
        assert result["grade"] in ("A", "B", "C", "D", "F")
        assert "metrics" in result
        assert isinstance(result["metrics"], dict)

    def test_returns_date(self, settings: Settings) -> None:
        result = handle_get_today_score(settings=settings)
        assert result["date"] == date.today().isoformat()


# ---------------------------------------------------------------------------
# get_patterns
# ---------------------------------------------------------------------------


class TestGetPatterns:
    def test_empty_database(self, settings: Settings) -> None:
        result = handle_get_patterns(settings=settings)
        assert result["patterns"] == []
        assert result["days_analyzed"] == 0

    def test_with_data(self, settings: Settings, store: SQLiteStore) -> None:
        _seed_multi_day(store, days=10)
        result = handle_get_patterns(settings=settings)
        assert "patterns" in result
        assert isinstance(result["patterns"], list)
        assert result["days_analyzed"] > 0

    def test_pattern_structure(self, settings: Settings, store: SQLiteStore) -> None:
        _seed_multi_day(store, days=10)
        result = handle_get_patterns(settings=settings)
        if result["patterns"]:
            p = result["patterns"][0]
            assert "name" in p
            assert "category" in p
            assert "description" in p
            assert "confidence" in p
            assert "days_observed" in p

    def test_custom_days(self, settings: Settings, store: SQLiteStore) -> None:
        _seed_multi_day(store, days=5)
        result = handle_get_patterns(days=5, settings=settings)
        assert result["days_analyzed"] <= 5


# ---------------------------------------------------------------------------
# get_suggestions
# ---------------------------------------------------------------------------


class TestGetSuggestions:
    def test_empty_database(self, settings: Settings) -> None:
        result = handle_get_suggestions(settings=settings)
        assert result["suggestions"] == []

    def test_with_data(self, settings: Settings, store: SQLiteStore) -> None:
        _seed_multi_day(store, days=10)
        result = handle_get_suggestions(settings=settings)
        assert "suggestions" in result
        assert isinstance(result["suggestions"], list)

    def test_suggestion_structure(self, settings: Settings, store: SQLiteStore) -> None:
        _seed_multi_day(store, days=10)
        result = handle_get_suggestions(settings=settings)
        if result["suggestions"]:
            s = result["suggestions"][0]
            assert "id" in s
            assert "title" in s
            assert "rationale" in s
            assert "intervention_type" in s
            assert "predicted_impact" in s
            assert "score_delta" in s
            assert "source_patterns" in s


# ---------------------------------------------------------------------------
# get_timeline
# ---------------------------------------------------------------------------


class TestGetTimeline:
    def test_empty_date(self, settings: Settings) -> None:
        result = handle_get_timeline(target_date="2020-01-01", settings=settings)
        assert result["buckets"] == []

    def test_with_data(self, settings: Settings, store: SQLiteStore) -> None:
        target = date.today()
        _seed_events(store, target)
        result = handle_get_timeline(target_date=target.isoformat(), settings=settings)
        assert result["date"] == target.isoformat()
        assert len(result["buckets"]) > 0

    def test_bucket_structure(self, settings: Settings, store: SQLiteStore) -> None:
        target = date.today()
        _seed_events(store, target)
        result = handle_get_timeline(target_date=target.isoformat(), settings=settings)
        bucket = result["buckets"][0]
        assert "timestamp" in bucket
        assert "primary_activity" in bucket
        assert "event_count" in bucket

    def test_invalid_date(self, settings: Settings) -> None:
        result = handle_get_timeline(target_date="not-a-date", settings=settings)
        assert "error" in result

    def test_default_is_today(self, settings: Settings, store: SQLiteStore) -> None:
        _seed_events(store, date.today())
        result = handle_get_timeline(settings=settings)
        assert result["date"] == date.today().isoformat()


# ---------------------------------------------------------------------------
# get_score_history
# ---------------------------------------------------------------------------


class TestGetScoreHistory:
    def test_empty_database(self, settings: Settings) -> None:
        result = handle_get_score_history(settings=settings)
        assert result["days_with_data"] == 0
        assert result["history"] == []

    def test_with_data(self, settings: Settings, store: SQLiteStore) -> None:
        _seed_multi_day(store, days=5)
        result = handle_get_score_history(days=7, settings=settings)
        assert result["days_with_data"] > 0
        assert len(result["history"]) > 0

    def test_history_entry_structure(
        self, settings: Settings, store: SQLiteStore
    ) -> None:
        _seed_multi_day(store, days=3)
        result = handle_get_score_history(days=7, settings=settings)
        if result["history"]:
            entry = result["history"][0]
            assert "date" in entry
            assert "total" in entry
            assert "grade" in entry
            assert "metrics" in entry


# ---------------------------------------------------------------------------
# get_experiments
# ---------------------------------------------------------------------------


class TestGetExperiments:
    def test_empty(self, settings: Settings) -> None:
        result = handle_get_experiments(settings=settings)
        assert result["active"] == []
        assert result["completed"] == []
        assert result["cancelled"] == []

    def test_with_experiment(self, settings: Settings, store: SQLiteStore) -> None:
        exp = Experiment(
            id="test-001",
            description="Test coding in the morning",
            intervention="code from 8-10am",
            duration_days=3,
            start_date=date.today(),
            status=ExperimentStatus.ACTIVE,
            baseline_score=0.5,
        )
        store.save_experiment(exp)
        result = handle_get_experiments(settings=settings)
        assert len(result["active"]) == 1
        assert result["active"][0]["id"] == "test-001"
        assert result["active"][0]["description"] == "Test coding in the morning"


# ---------------------------------------------------------------------------
# simulate
# ---------------------------------------------------------------------------


class TestSimulate:
    def test_with_data(self, settings: Settings, store: SQLiteStore) -> None:
        _seed_events(store, date.today())
        result = handle_simulate(
            intervention="code from 8-10am",
            settings=settings,
        )
        assert "baseline_score" in result
        assert "simulated_score" in result
        assert "score_delta" in result
        assert "summary" in result

    def test_invalid_baseline_date(self, settings: Settings) -> None:
        result = handle_simulate(
            intervention="code from 8-10am",
            baseline_date="bad-date",
            settings=settings,
        )
        assert "error" in result

    def test_empty_database(self, settings: Settings) -> None:
        result = handle_simulate(
            intervention="code from 8-10am",
            settings=settings,
        )
        # Should still succeed (with 0 scores) or return a simulation
        assert "baseline_score" in result or "error" in result


# ---------------------------------------------------------------------------
# get_sources
# ---------------------------------------------------------------------------


class TestGetSources:
    def test_returns_sources(self, settings: Settings) -> None:
        result = handle_get_sources(settings=settings)
        assert "sources" in result
        assert isinstance(result["sources"], list)
        assert len(result["sources"]) > 0

    def test_source_structure(self, settings: Settings) -> None:
        result = handle_get_sources(settings=settings)
        source = result["sources"][0]
        assert "name" in source
        assert "installed" in source
        assert "available" in source


# ---------------------------------------------------------------------------
# get_goals
# ---------------------------------------------------------------------------


class TestGetGoals:
    def test_returns_goals(self, settings: Settings) -> None:
        result = handle_get_goals(settings=settings)
        assert "goals" in result
        assert len(result["goals"]) == 3  # DEFAULT_GOALS has 3 goals

    def test_goal_structure(self, settings: Settings) -> None:
        result = handle_get_goals(settings=settings)
        goal = result["goals"][0]
        assert "name" in goal
        assert "description" in goal
        assert "metric" in goal
        assert "weight" in goal


# ---------------------------------------------------------------------------
# JSON-RPC protocol
# ---------------------------------------------------------------------------


class TestJsonRpcProtocol:
    def test_initialize(self) -> None:
        resp = _handle_jsonrpc({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })
        assert resp["id"] == 1
        assert "serverInfo" in resp["result"]
        assert resp["result"]["serverInfo"]["name"] == "life-world-model"

    def test_tools_list(self) -> None:
        resp = _handle_jsonrpc({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })
        assert resp["id"] == 2
        tools = resp["result"]["tools"]
        assert len(tools) == 9
        names = {t["name"] for t in tools}
        assert "get_today_score" in names
        assert "simulate" in names
        assert "get_goals" in names

    def test_tools_call_get_goals(self) -> None:
        resp = _handle_jsonrpc({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "get_goals", "arguments": {}},
        })
        assert resp["id"] == 3
        content = resp["result"]["content"]
        assert len(content) == 1
        assert content[0]["type"] == "text"
        data = json.loads(content[0]["text"])
        assert "goals" in data

    def test_unknown_tool(self) -> None:
        resp = _handle_jsonrpc({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}},
        })
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_unknown_method(self) -> None:
        resp = _handle_jsonrpc({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "unknown/method",
            "params": {},
        })
        assert "error" in resp

    def test_tool_defs_complete(self) -> None:
        """Every tool definition has name, description, and inputSchema."""
        for tool in TOOL_DEFS:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"


# ---------------------------------------------------------------------------
# All handlers return JSON-serializable data
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_all_handlers_json_serializable(
        self, settings: Settings, store: SQLiteStore
    ) -> None:
        """Every handler's output must be JSON-serializable."""
        _seed_multi_day(store, days=5)

        results = [
            handle_get_today_score(settings=settings),
            handle_get_patterns(settings=settings),
            handle_get_suggestions(settings=settings),
            handle_get_timeline(
                target_date=date.today().isoformat(), settings=settings
            ),
            handle_get_score_history(days=7, settings=settings),
            handle_get_experiments(settings=settings),
            handle_simulate(intervention="code from 8-10am", settings=settings),
            handle_get_sources(settings=settings),
            handle_get_goals(settings=settings),
        ]

        for i, result in enumerate(results):
            try:
                json.dumps(result)
            except (TypeError, ValueError) as exc:
                pytest.fail(f"Handler {i} returned non-serializable data: {exc}")
