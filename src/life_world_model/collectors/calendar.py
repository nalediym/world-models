"""Apple Calendar collector — reads events from the local Calendar Cache SQLite database."""

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

CACHE_FILENAME = "Calendar Cache"

_EVENTS_QUERY = """
SELECT ZTITLE, ZSTARTDATE, ZENDDATE
FROM ZCALENDARITEM
WHERE ZSTARTDATE >= ? AND ZSTARTDATE < ?
  AND ZTITLE IS NOT NULL
ORDER BY ZSTARTDATE ASC
"""


@register_collector
class CalendarCollector(BaseCollector):
    """Reads Apple Calendar events from the local Calendar Cache database."""

    source_name = "calendar"

    def __init__(self, calendar_path: Path | None = None) -> None:
        if calendar_path is None:
            calendar_path = Path.home() / "Library" / "Calendars"
        self.calendar_path = calendar_path

    @property
    def _cache_path(self) -> Path:
        return self.calendar_path / CACHE_FILENAME

    def is_available(self) -> bool:
        """Check whether the Calendar Cache database exists and is readable.

        Returns False when the file is missing or when Full Disk Access has
        not been granted (PermissionError).
        """
        cache = self._cache_path
        if not cache.exists():
            return False
        try:
            with open(cache, "rb") as fh:
                fh.read(1)
            return True
        except PermissionError:
            return False

    def collect_for_date(self, target_date: date) -> list[RawEvent]:
        """Return calendar events for *target_date*.

        The Calendar Cache database may be locked by CalendarAgent, so we
        copy it to a temporary file before querying.
        """
        cache = self._cache_path
        if not cache.exists():
            return []

        # Build Mac-epoch boundaries for the target date (UTC day).
        day_start = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            tzinfo=timezone.utc,
        )
        day_end = day_start + timedelta(days=1)

        start_seconds = mac_epoch_from_datetime(day_start)
        end_seconds = mac_epoch_from_datetime(day_end)

        # Copy to temp to avoid locking issues.
        try:
            with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            shutil.copy2(cache, tmp_path)
        except PermissionError:
            logger.warning("Permission denied when copying Calendar Cache — grant Full Disk Access.")
            return []

        try:
            return self._query_events(tmp_path, start_seconds, end_seconds)
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _query_events(
        db_path: Path,
        start_seconds: float,
        end_seconds: float,
    ) -> list[RawEvent]:
        """Execute the event query against the copied database."""
        try:
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                rows = conn.execute(_EVENTS_QUERY, (start_seconds, end_seconds)).fetchall()
        except sqlite3.DatabaseError as exc:
            logger.warning("Failed to query Calendar Cache: %s", exc)
            return []

        events: list[RawEvent] = []
        for title, start_ts, end_ts in rows:
            timestamp = mac_epoch_to_datetime(start_ts)

            duration: float | None = None
            if end_ts is not None:
                duration = end_ts - start_ts

            events.append(
                RawEvent(
                    timestamp=timestamp,
                    source="calendar",
                    title=title,
                    domain="calendar",
                    duration_seconds=duration,
                )
            )

        return events
