from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import FeedbackAction, SuggestionFeedback


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path / "test.sqlite3")


class TestSuggestionFeedback:
    def test_save_and_load(self, store: SQLiteStore) -> None:
        fb = SuggestionFeedback(
            suggestion_id="abc123",
            suggestion_title="Limit browsing",
            action=FeedbackAction.ACCEPT,
            timestamp=datetime(2026, 4, 7, 10, 0),
        )
        store.save_suggestion_feedback(fb)
        loaded = store.load_suggestion_feedback()
        assert len(loaded) == 1
        assert loaded[0].suggestion_id == "abc123"
        assert loaded[0].action == FeedbackAction.ACCEPT
        assert loaded[0].suggestion_title == "Limit browsing"

    def test_multiple_feedback(self, store: SQLiteStore) -> None:
        for i, action in enumerate([FeedbackAction.ACCEPT, FeedbackAction.REJECT]):
            fb = SuggestionFeedback(
                suggestion_id=f"id{i}",
                suggestion_title=f"Suggestion {i}",
                action=action,
                timestamp=datetime(2026, 4, 7, 10, i),
            )
            store.save_suggestion_feedback(fb)
        loaded = store.load_suggestion_feedback()
        assert len(loaded) == 2

    def test_feedback_with_notes(self, store: SQLiteStore) -> None:
        fb = SuggestionFeedback(
            suggestion_id="xyz",
            suggestion_title="Protect focus",
            action=FeedbackAction.REJECT,
            notes="Already doing this",
        )
        store.save_suggestion_feedback(fb)
        loaded = store.load_suggestion_feedback()
        assert loaded[0].notes == "Already doing this"


class TestSuggestionIds:
    def test_suggestions_have_ids(self) -> None:
        from datetime import date

        from life_world_model.analysis.suggestions import generate_suggestions
        from life_world_model.types import Pattern

        pattern = Pattern(
            name="time_sink_browsing",
            category="time_sink",
            description="browsing: 3h, high switching",
            evidence={"activity": "browsing", "total_hours": 3.0},
            confidence=0.6,
            days_observed=7,
            first_seen=date(2026, 4, 1),
            last_seen=date(2026, 4, 7),
        )
        suggestions = generate_suggestions([pattern])
        assert len(suggestions) == 1
        assert suggestions[0].id is not None
        assert len(suggestions[0].id) == 8

    def test_ids_are_stable(self) -> None:
        from datetime import date

        from life_world_model.analysis.suggestions import generate_suggestions
        from life_world_model.types import Pattern

        pattern = Pattern(
            name="time_sink_browsing",
            category="time_sink",
            description="browsing: 3h",
            evidence={"activity": "browsing", "total_hours": 3.0},
            confidence=0.6,
            days_observed=7,
        )
        s1 = generate_suggestions([pattern])
        s2 = generate_suggestions([pattern])
        assert s1[0].id == s2[0].id
