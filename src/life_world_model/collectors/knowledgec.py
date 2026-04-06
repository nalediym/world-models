"""macOS knowledgeC.db collector — app focus, Safari history, and device wake events."""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from life_world_model.collectors.base import BaseCollector, register_collector
from life_world_model.types import RawEvent
from life_world_model.utils.timestamps import MAC_EPOCH, mac_epoch_to_datetime

# Stream types we care about.
STREAM_APP_IN_FOCUS = "/app/inFocus"
STREAM_SAFARI_HISTORY = "/safari/history"
STREAM_DEVICE_UNLOCKED = "/device/unlocked"

_TARGET_STREAMS = (STREAM_APP_IN_FOCUS, STREAM_SAFARI_HISTORY, STREAM_DEVICE_UNLOCKED)

# Bundle-ID-to-human-readable mapping for common macOS apps.
BUNDLE_ID_MAP: dict[str, str] = {
    "com.apple.Safari": "Safari",
    "com.google.Chrome": "Chrome",
    "com.microsoft.VSCode": "VS Code",
    "com.todesktop.runtime.cursor": "Cursor",
    "com.tinyspeck.slackmacgap": "Slack",
    "com.apple.mail": "Mail",
    "com.apple.Terminal": "Terminal",
    "com.googlecode.iterm2": "iTerm2",
    "com.apple.finder": "Finder",
    "com.anthropic.claudecode": "Claude Code",
}


def bundle_id_to_app_name(bundle_id: str | None) -> str:
    """Map a bundle ID to a human-readable app name.

    Known IDs are looked up in ``BUNDLE_ID_MAP``.  Unknown IDs fall
    back to the last dotted component (e.g. ``com.example.foo`` becomes
    ``foo``).  ``None`` or empty strings return ``"Unknown"``.
    """
    if not bundle_id:
        return "Unknown"
    if bundle_id in BUNDLE_ID_MAP:
        return BUNDLE_ID_MAP[bundle_id]
    # Fallback: take the last component of the bundle ID.
    parts = bundle_id.rsplit(".", 1)
    return parts[-1] if parts else bundle_id


@register_collector
class KnowledgeCCollector(BaseCollector):
    """Reads macOS knowledgeC.db for app-focus, Safari history, and wake events."""

    source_name = "knowledgec"

    def __init__(self, knowledgec_path: Path) -> None:
        self.knowledgec_path = knowledgec_path

    def is_available(self) -> bool:
        if not self.knowledgec_path.exists():
            return False
        try:
            with open(self.knowledgec_path, "rb") as f:
                f.read(1)
            return True
        except PermissionError:
            return False

    def collect_for_date(self, target_date: date) -> list[RawEvent]:
        if not self.is_available():
            return []

        # Copy to a temp file so we don't conflict with macOS locks.
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            shutil.copy2(self.knowledgec_path, tmp_path)
            return self._query(tmp_path, target_date)
        except (sqlite3.DatabaseError, OSError):
            return []
        finally:
            tmp_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _query(self, db_path: Path, target_date: date) -> list[RawEvent]:
        """Query the copied knowledgeC database for events on *target_date*."""
        day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        # Convert date boundaries to Mac epoch seconds.
        start_seconds = (day_start - MAC_EPOCH).total_seconds()
        end_seconds = (day_end - MAC_EPOCH).total_seconds()

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            rows = self._execute_query(conn, start_seconds, end_seconds)
        except sqlite3.OperationalError:
            # Table structure is unexpected — return empty, don't crash.
            return []
        finally:
            conn.close()

        return self._rows_to_events(rows)

    @staticmethod
    def _execute_query(
        conn: sqlite3.Connection,
        start_seconds: float,
        end_seconds: float,
    ) -> list[tuple]:
        """Run the SQL against ZOBJECT and return raw row tuples."""
        placeholders = ",".join("?" for _ in _TARGET_STREAMS)
        query = f"""
            SELECT ZCREATIONDATE, ZENDDATE, ZSTREAMNAME, ZVALUESTRING
            FROM ZOBJECT
            WHERE ZSTREAMNAME IN ({placeholders})
              AND ZCREATIONDATE >= ?
              AND ZCREATIONDATE < ?
            ORDER BY ZCREATIONDATE ASC
        """
        params: tuple = (*_TARGET_STREAMS, start_seconds, end_seconds)
        return conn.execute(query, params).fetchall()

    @staticmethod
    def _rows_to_events(rows: list[tuple]) -> list[RawEvent]:
        """Convert raw DB rows into ``RawEvent`` instances."""
        events: list[RawEvent] = []
        for creation_ts, end_ts, stream, value_string in rows:
            if creation_ts is None:
                continue

            timestamp = mac_epoch_to_datetime(creation_ts)

            duration: float | None = None
            if end_ts is not None and creation_ts is not None:
                duration = end_ts - creation_ts
                if duration < 0:
                    duration = None

            title: str | None = None
            domain: str | None = None
            url: str | None = None

            if stream == STREAM_APP_IN_FOCUS:
                title = bundle_id_to_app_name(value_string)
                domain = value_string  # raw bundle ID
            elif stream == STREAM_SAFARI_HISTORY:
                title = "Safari History"
                url = value_string
                domain = _extract_domain(value_string)
            elif stream == STREAM_DEVICE_UNLOCKED:
                title = "Device Unlocked"

            events.append(
                RawEvent(
                    timestamp=timestamp,
                    source="knowledgec",
                    title=title,
                    domain=domain,
                    url=url,
                    duration_seconds=duration,
                    metadata={"stream": stream},
                )
            )
        return events


def _extract_domain(url: str | None) -> str | None:
    """Best-effort domain extraction without external deps."""
    if not url:
        return None
    try:
        from urllib.parse import urlparse

        return urlparse(url).hostname
    except Exception:
        return None
