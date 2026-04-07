from __future__ import annotations

import subprocess


def send_notification(title: str, message: str, sound: bool = True) -> bool:
    """Send a macOS notification via osascript.

    Returns True if the notification was sent, False on failure.
    All subprocess calls have a 5-second timeout.
    """
    # Escape double quotes and backslashes for AppleScript
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_message = message.replace("\\", "\\\\").replace('"', '\\"')

    sound_clause = ' sound name "Glass"' if sound else ""
    script = (
        f'display notification "{safe_message}" '
        f'with title "{safe_title}"{sound_clause}'
    )

    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
