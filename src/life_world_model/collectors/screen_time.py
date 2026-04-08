"""Screen Time collector — reads app usage duration from knowledgeC.db streams.

Captures ``/app/usage`` and ``/app/webUsage`` streams, which track how long
each app was actively used.  The existing knowledgeC collector already reads
``/app/inFocus`` (foreground window); this collector focuses on *duration-based*
usage data that Screen Time reports on — complementary, not overlapping.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from life_world_model.collectors.base import BaseCollector, register_collector
from life_world_model.types import RawEvent
from life_world_model.utils.timestamps import MAC_EPOCH, mac_epoch_to_datetime, mac_epoch_from_datetime

logger = logging.getLogger(__name__)

# Streams that carry Screen Time usage data (distinct from /app/inFocus).
STREAM_APP_USAGE = "/app/usage"
STREAM_WEB_USAGE = "/app/webUsage"

_TARGET_STREAMS = (STREAM_APP_USAGE, STREAM_WEB_USAGE)

# Bundle-ID-to-human-readable mapping (shared subset with knowledgeC collector).
_BUNDLE_SHORT: dict[str, str] = {
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


def _bundle_to_name(bundle_id: str | None) -> str:
    """Map a bundle ID to a short app name."""
    if not bundle_id:
        return "Unknown"
    if bundle_id in _BUNDLE_SHORT:
        return _BUNDLE_SHORT[bundle_id]
    parts = bundle_id.rsplit(".", 1)
    return parts[-1] if parts else bundle_id


@register_collector
class ScreenTimeCollector(BaseCollector):
    """Reads Screen Time app-usage durations from knowledgeC.db."""

    source_name = "screentime"

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
        """Query the copied database for usage events on *target_date*."""
        day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        start_seconds = mac_epoch_from_datetime(day_start)
        end_seconds = mac_epoch_from_datetime(day_end)

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            rows = self._execute_query(conn, start_seconds, end_seconds)
        except sqlite3.OperationalError:
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
        """Run the SQL and return raw row tuples."""
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

            if stream == STREAM_APP_USAGE:
                title = _bundle_to_name(value_string)
                domain = value_string  # raw bundle ID
                url = None
            elif stream == STREAM_WEB_USAGE:
                title = "Web Usage"
                domain = value_string
                url = None
            else:
                continue

            events.append(
                RawEvent(
                    timestamp=timestamp,
                    source="screentime",
                    title=title,
                    domain=domain,
                    url=url,
                    duration_seconds=duration,
                    metadata={"stream": stream},
                )
            )
        return events
