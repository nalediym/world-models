"""Tests for the Life World Model web dashboard."""

from __future__ import annotations

import json
import tempfile
from datetime import date, datetime
from pathlib import Path

import pytest

from life_world_model.config import Settings
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import RawEvent
from life_world_model.web.app import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Return a fresh temporary database path."""
    return tmp_path / "test.sqlite3"


@pytest.fixture()
def settings(tmp_db: Path) -> Settings:
    """Settings pointing at the temporary database."""
    return Settings(database_path=tmp_db)


@pytest.fixture()
def seeded_store(settings: Settings) -> SQLiteStore:
    """A store seeded with demo events for today."""
    store = SQLiteStore(settings.database_path)
    store.initialize()
    today = date.today()
    iso = today.isoformat()
    events = [
        RawEvent(
            timestamp=datetime.fromisoformat(f"{iso}T08:05:00"),
            source="demo",
            title="Morning notes",
            domain="docs.example",
            url="https://docs.example/notes",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat(f"{iso}T08:20:00"),
            source="demo",
            title="GitHub PR review",
            domain="github.com",
            url="https://github.com/example/repo/pull/42",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat(f"{iso}T09:00:00"),
            source="demo",
            title="ArXiv paper",
            domain="arxiv.org",
            url="https://arxiv.org/abs/2401.00001",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat(f"{iso}T09:30:00"),
            source="demo",
            title="Slack thread",
            domain="slack.com",
            url=None,
        ),
        RawEvent(
            timestamp=datetime.fromisoformat(f"{iso}T10:00:00"),
            source="demo",
            title="Google search",
            domain="google.com",
            url="https://google.com/search?q=test",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat(f"{iso}T10:30:00"),
            source="demo",
            title="Code editing",
            domain="github.com",
            url="https://github.com/example/repo/blob/main/app.py",
        ),
    ]
    store.save_raw_events(events)
    return store


@pytest.fixture()
def client(settings: Settings, seeded_store: SQLiteStore):
    """Flask test client with seeded data."""
    app = create_app(settings)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def empty_client(settings: Settings):
    """Flask test client with an empty database."""
    store = SQLiteStore(settings.database_path)
    store.initialize()
    app = create_app(settings)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Page route tests
# ---------------------------------------------------------------------------


class TestPageRoutes:
    """Verify all page routes return 200 with expected content."""

    def test_today_page(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Today" in resp.data

    def test_patterns_page(self, client):
        resp = client.get("/patterns")
        assert resp.status_code == 200
        assert b"Patterns" in resp.data

    def test_suggestions_page(self, client):
        resp = client.get("/suggestions")
        assert resp.status_code == 200
        assert b"Suggestions" in resp.data

    def test_goals_page(self, client):
        resp = client.get("/goals")
        assert resp.status_code == 200
        assert b"Goals" in resp.data

    def test_history_page(self, client):
        resp = client.get("/history")
        assert resp.status_code == 200
        assert b"History" in resp.data

    def test_simulate_page(self, client):
        resp = client.get("/simulate")
        assert resp.status_code == 200
        assert b"Simulate" in resp.data


# ---------------------------------------------------------------------------
# API route tests
# ---------------------------------------------------------------------------


class TestAPIToday:
    """GET /api/today"""

    def test_returns_json(self, client):
        resp = client.get("/api/today")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "date" in data
        assert "timeline" in data
        assert "score" in data
        assert "event_count" in data
        assert "bucket_count" in data

    def test_score_structure(self, client):
        resp = client.get("/api/today")
        data = resp.get_json()
        score = data["score"]
        assert "total" in score
        assert "grade" in score
        assert "metrics" in score
        assert isinstance(score["total"], (int, float))
        assert score["grade"] in ("A", "B", "C", "D", "F")

    def test_timeline_has_entries(self, client):
        resp = client.get("/api/today")
        data = resp.get_json()
        assert data["event_count"] > 0
        assert len(data["timeline"]) > 0

    def test_timeline_bucket_structure(self, client):
        resp = client.get("/api/today")
        data = resp.get_json()
        if data["timeline"]:
            bucket = data["timeline"][0]
            assert "time" in bucket
            assert "activity" in bucket
            assert "event_count" in bucket
            assert "confidence" in bucket

    def test_empty_database(self, empty_client):
        resp = empty_client.get("/api/today")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["event_count"] == 0
        assert data["timeline"] == []
        assert data["score"]["grade"] == "F"


class TestAPIPatterns:
    """GET /api/patterns"""

    def test_returns_json(self, client):
        resp = client.get("/api/patterns")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "patterns" in data
        assert "days_analyzed" in data
        assert isinstance(data["patterns"], list)

    def test_empty_database(self, empty_client):
        resp = empty_client.get("/api/patterns")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["patterns"] == []
        assert data["days_analyzed"] == 0


class TestAPISuggestions:
    """GET /api/suggestions and POST accept/reject"""

    def test_returns_json(self, client):
        resp = client.get("/api/suggestions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "suggestions" in data
        assert "pattern_count" in data
        assert isinstance(data["suggestions"], list)

    def test_suggestion_structure(self, client):
        resp = client.get("/api/suggestions")
        data = resp.get_json()
        for s in data["suggestions"]:
            assert "id" in s
            assert "title" in s
            assert "rationale" in s
            assert "intervention_type" in s
            assert "predicted_impact" in s
            assert "score_delta" in s
            assert "status" in s

    def test_accept_suggestion(self, client):
        # Get suggestions first
        resp = client.get("/api/suggestions")
        data = resp.get_json()
        if data["suggestions"]:
            sid = data["suggestions"][0]["id"]
            resp2 = client.post(f"/api/suggestions/{sid}/accept")
            assert resp2.status_code == 200
            result = resp2.get_json()
            assert result["id"] == sid
            assert result["status"] == "accepted"

    def test_reject_suggestion(self, client):
        resp = client.get("/api/suggestions")
        data = resp.get_json()
        if data["suggestions"]:
            sid = data["suggestions"][0]["id"]
            resp2 = client.post(f"/api/suggestions/{sid}/reject")
            assert resp2.status_code == 200
            result = resp2.get_json()
            assert result["status"] == "rejected"

    def test_accept_unknown_id(self, client):
        resp = client.post("/api/suggestions/nonexistent123/accept")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "accepted"

    def test_empty_database(self, empty_client):
        resp = empty_client.get("/api/suggestions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["suggestions"] == []


class TestAPIGoals:
    """GET /api/goals"""

    def test_returns_json(self, client):
        resp = client.get("/api/goals")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "goals" in data
        assert "total_score" in data
        assert "grade" in data
        assert "date" in data

    def test_goals_structure(self, client):
        resp = client.get("/api/goals")
        data = resp.get_json()
        assert len(data["goals"]) > 0
        for g in data["goals"]:
            assert "name" in g
            assert "description" in g
            assert "metric" in g
            assert "weight" in g
            assert "raw" in g
            assert "weighted" in g

    def test_weights_sum_to_one(self, client):
        resp = client.get("/api/goals")
        data = resp.get_json()
        total_weight = sum(g["weight"] for g in data["goals"])
        assert abs(total_weight - 1.0) < 0.01

    def test_empty_database(self, empty_client):
        resp = empty_client.get("/api/goals")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["grade"] == "F"


class TestAPIHistory:
    """GET /api/history"""

    def test_returns_json(self, client):
        resp = client.get("/api/history?days=7")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "history" in data
        assert "days" in data
        assert isinstance(data["history"], list)

    def test_days_parameter(self, client):
        resp = client.get("/api/history?days=7")
        data = resp.get_json()
        assert data["days"] == 7
        # history includes start and end, so 7 days back + today = 8 entries
        assert len(data["history"]) == 8

    def test_default_days(self, client):
        resp = client.get("/api/history")
        data = resp.get_json()
        assert data["days"] == 30
        assert len(data["history"]) == 31  # 30 days back + today

    def test_history_entry_structure(self, client):
        resp = client.get("/api/history?days=1")
        data = resp.get_json()
        assert len(data["history"]) > 0
        entry = data["history"][0]
        assert "date" in entry
        assert "score" in entry
        assert "grade" in entry
        assert "bucket_count" in entry
        assert "event_count" in entry

    def test_caps_at_365(self, client):
        resp = client.get("/api/history?days=9999")
        data = resp.get_json()
        assert data["days"] == 365


class TestAPISimulate:
    """POST /api/simulate"""

    def test_basic_simulation(self, client):
        resp = client.post(
            "/api/simulate",
            data=json.dumps({"scenario": "code from 8-10am"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "baseline_score" in data
        assert "simulated_score" in data
        assert "score_delta" in data
        assert "summary" in data
        assert "intervention" in data

    def test_intervention_structure(self, client):
        resp = client.post(
            "/api/simulate",
            data=json.dumps({"scenario": "stop browsing after 9pm"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        iv = data["intervention"]
        assert "type" in iv
        assert "activity" in iv
        assert "params" in iv
        assert "description" in iv

    def test_missing_scenario(self, client):
        resp = client.post(
            "/api/simulate",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_empty_scenario(self, client):
        resp = client.post(
            "/api/simulate",
            data=json.dumps({"scenario": ""}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_invalid_baseline_date(self, client):
        resp = client.post(
            "/api/simulate",
            data=json.dumps({
                "scenario": "code from 8-10am",
                "baseline_date": "not-a-date",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_limit_intervention(self, client):
        resp = client.post(
            "/api/simulate",
            data=json.dumps({"scenario": "limit browsing to 1hr"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["intervention"]["type"] == "limit"

    def test_add_intervention(self, client):
        resp = client.post(
            "/api/simulate",
            data=json.dumps({"scenario": "add 30min walk at 12pm"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["intervention"]["type"] == "add"
