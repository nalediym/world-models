from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

from life_world_model.config import Settings
from life_world_model.daemon.collector import _collect_cycle, _score_today
from life_world_model.types import RawEvent


def _make_settings() -> Settings:
    return Settings()


def _make_store_with_events() -> MagicMock:
    store = MagicMock()
    events = [
        RawEvent(
            timestamp=datetime(2025, 6, 15, h, 0),
            source="chrome",
            title="test",
            domain="github.com",
        )
        for h in range(8, 18)
    ]
    store.load_raw_events_for_date.return_value = events
    return store


class TestCollectCycle:
    @patch("life_world_model.cli._build_collectors")
    @patch("life_world_model.cli._import_collectors")
    def test_collect_cycle_returns_count(self, mock_import, mock_build):
        """Collect cycle runs collectors and returns event count."""
        mock_collector = MagicMock()
        mock_collector.is_available.return_value = True
        mock_collector.collect_for_date.return_value = [
            RawEvent(
                timestamp=datetime(2025, 6, 15, 9, 0),
                source="test",
                title="test",
            )
        ]
        mock_build.return_value = [mock_collector]

        settings = _make_settings()
        store = MagicMock()
        count = _collect_cycle(settings, store)

        assert count == 1
        store.save_raw_events.assert_called_once()


class TestScoreToday:
    def test_score_returns_float(self):
        """Score today returns a float between 0 and 1."""
        store = _make_store_with_events()
        settings = _make_settings()
        score = _score_today(settings, store)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_score_empty_data(self):
        """Empty data returns 0.0."""
        store = MagicMock()
        store.load_raw_events_for_date.return_value = []
        settings = _make_settings()
        score = _score_today(settings, store)
        assert score == 0.0
