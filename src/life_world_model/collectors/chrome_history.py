from __future__ import annotations

import shutil
import sqlite3
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from life_world_model.collectors.base import BaseCollector, register_collector
from life_world_model.types import RawEvent
from life_world_model.utils.timestamps import chrome_time_to_datetime


def resolve_domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc or None


@register_collector
class ChromeHistoryCollector(BaseCollector):
    source_name = "chrome"

    def __init__(self, history_path: Path) -> None:
        self.history_path = history_path

    def is_available(self) -> bool:
        return self.history_path.exists()

    def collect_for_date(self, target_date: date) -> list[RawEvent]:
        if not self.history_path.exists():
            raise FileNotFoundError(f"Chrome history DB not found at {self.history_path}")

        start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        start_us = int((start - EPOCH_START).total_seconds() * 1_000_000)
        end_us = int((end - EPOCH_START).total_seconds() * 1_000_000)

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            shutil.copy2(self.history_path, temp_path)
            with sqlite3.connect(temp_path) as connection:
                rows = connection.execute(
                    """
                    SELECT visits.visit_time, urls.title, urls.url
                    FROM visits
                    JOIN urls ON visits.url = urls.id
                    WHERE visits.visit_time >= ? AND visits.visit_time < ?
                    ORDER BY visits.visit_time ASC
                    """,
                    (start_us, end_us),
                ).fetchall()
        finally:
            temp_path.unlink(missing_ok=True)

        events: list[RawEvent] = []
        for visit_time, title, url in rows:
            events.append(
                RawEvent(
                    timestamp=chrome_time_to_datetime(int(visit_time)).astimezone(),
                    source="chrome",
                    title=title,
                    domain=resolve_domain(url),
                    url=url,
                )
            )

        return events
