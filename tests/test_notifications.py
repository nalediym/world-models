from __future__ import annotations

from unittest.mock import MagicMock, patch

from life_world_model.notifications.macos import send_notification


class TestSendNotification:
    @patch("life_world_model.notifications.macos.subprocess.run")
    def test_osascript_called(self, mock_run):
        """send_notification calls osascript with the correct script."""
        result = send_notification("Test Title", "Test Message")
        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args
        cmd = args[0][0]
        assert cmd[0] == "osascript"
        assert cmd[1] == "-e"
        assert "Test Title" in cmd[2]
        assert "Test Message" in cmd[2]
        # Verify timeout is set
        assert args[1]["timeout"] == 5

    @patch("life_world_model.notifications.macos.subprocess.run")
    def test_failure_returns_false(self, mock_run):
        """Subprocess failure returns False instead of raising."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="osascript", timeout=5)
        result = send_notification("Title", "Message")
        assert result is False

    @patch("life_world_model.notifications.macos.subprocess.run")
    def test_quote_escaping(self, mock_run):
        """Double quotes in title/message are escaped for AppleScript."""
        send_notification('Say "hello"', 'It\'s a "test"')
        args = mock_run.call_args
        script = args[0][0][2]
        assert '\\"hello\\"' in script
        assert '\\"test\\"' in script
