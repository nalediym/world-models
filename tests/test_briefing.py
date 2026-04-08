from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from life_world_model.notifications.briefing import morning_briefing
from life_world_model.types import RawEvent


class TestMorningBriefing:
    @patch("life_world_model.notifications.briefing.send_notification")
    @patch("life_world_model.notifications.briefing.SQLiteStore")
    @patch("life_world_model.notifications.briefing.load_settings")
    def test_format_with_data(self, mock_settings, mock_store_cls, mock_notify):
        """Briefing with data returns formatted string with score, top activity, switches."""
        from life_world_model.config import Settings

        mock_settings.return_value = Settings()

        events = [
            RawEvent(
                timestamp=datetime(2025, 6, 14, h, 0),
                source="chrome",
                title="test",
                domain="github.com",
            )
            for h in range(8, 18)
        ]
        mock_store_cls.return_value.load_raw_events_for_date.return_value = events
        mock_store_cls.return_value.load_experiments.return_value = []
        mock_store_cls.return_value.load_patterns.return_value = []
        mock_store_cls.return_value.load_suggestion_feedback.return_value = []

        result = morning_briefing()

        assert "Yesterday:" in result
        assert "%" in result
        assert "Top:" in result
        assert "switches" in result
        mock_notify.assert_called_once()

    @patch("life_world_model.notifications.briefing.send_notification")
    @patch("life_world_model.notifications.briefing.SQLiteStore")
    @patch("life_world_model.notifications.briefing.load_settings")
    def test_no_data(self, mock_settings, mock_store_cls, mock_notify):
        """Briefing with no data returns a helpful message."""
        from life_world_model.config import Settings

        mock_settings.return_value = Settings()
        mock_store_cls.return_value.load_raw_events_for_date.return_value = []

        result = morning_briefing()

        assert "No data" in result
        mock_notify.assert_called_once()
