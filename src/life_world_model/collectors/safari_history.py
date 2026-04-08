"""Safari History collector — reads browsing history from Safari's History.db."""

from __future__ import annotations

import logging
import shutil
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from life_world_model.collectors.base import BaseCollector, register_collector
from life_world_model.types import RawEvent
from life_world_model.utils.timestamps import MAC_EPOCH, mac_epoch_to_datetime, mac_epoch_from_datetime

logger = logging.getLogger(__name__)

_HISTORY_QUERY = """
    SELECT hv.visit_time, hv.title, hi.url
    FROM history_visits hv
    JOIN history_items hi ON hv.history_item = hi.id
    WHERE hv.visit_time >= ? AND hv.visit_time < ?
    ORDER BY hv.visit_time ASC
"""


def _resolve_domain(url: str | None) -> str | None:
    """Extract the hostname from a URL."""
    if not url:
        return None
    try:
        return urlparse(url).netloc or None
    except Exception:
        return None


@register_collector
class SafariHistoryCollector(BaseCollector):
    """Reads Safari browsing history from its local SQLite database."""

    source_name = "safari"

    def __init__(self, history_path: Path) -> None:
        self.history_path = history_path

    def is_available(self) -> bool:
        if not self.history_path.exists():
            return False
        try:
            with open(self.history_path, "rb") as f:
                f.read(1)
            return True
        except PermissionError:
            return False

    def collect_for_date(self, target_date: date) -> list[RawEvent]:
        if not self.is_available():
            return []

        # Copy to temp to avoid locking issues.
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            shutil.copy2(self.history_path, tmp_path)
        except PermissionError:
            logger.warning("Permission denied copying Safari History.db — grant Full Disk Access.")
            return []
        except OSError as exc:
            logger.warning("Failed to copy Safari History.db: %s", exc)
            return []

        try:
            return self._query_history(tmp_path, target_date)
        finally:
            tmp_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _query_history(db_path: Path, target_date: date) -> list[RawEvent]:
        """Execute the history query against the copied database."""
        day_start = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            tzinfo=timezone.utc,
        )
        day_end = day_start + timedelta(days=1)

        start_seconds = mac_epoch_from_datetime(day_start)
        end_seconds = mac_epoch_from_datetime(day_end)

        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            rows = conn.execute(_HISTORY_QUERY, (start_seconds, end_seconds)).fetchall()
        except sqlite3.DatabaseError as exc:
            logger.warning("Failed to query Safari History: %s", exc)
            return []
        finally:
            try:
                conn.close()
            except Exception:
                pass

        events: list[RawEvent] = []
        for visit_time, title, url in rows:
            if visit_time is None:
                continue

            timestamp = mac_epoch_to_datetime(visit_time)

            events.append(
                RawEvent(
                    timestamp=timestamp,
                    source="safari",
                    title=title or _resolve_domain(url),
                    domain=_resolve_domain(url),
                    url=url,
                )
            )

        return events
