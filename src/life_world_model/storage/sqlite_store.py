from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from life_world_model.types import RawEvent


SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  source TEXT NOT NULL,
  title TEXT,
  domain TEXT,
  url TEXT
)
"""


class SQLiteStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(SCHEMA)
            connection.commit()

    def save_raw_events(self, events: list[RawEvent]) -> None:
        self.initialize()
        rows = [
            (event.timestamp.isoformat(), event.source, event.title, event.domain, event.url)
            for event in events
        ]
        with sqlite3.connect(self.database_path) as connection:
            connection.executemany(
                "INSERT INTO raw_events (timestamp, source, title, domain, url) VALUES (?, ?, ?, ?, ?)",
                rows,
            )
            connection.commit()

    def load_raw_events_for_date(self, target_date: date) -> list[RawEvent]:
        self.initialize()
        start = datetime.combine(target_date, datetime.min.time()).isoformat()
        end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat()
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT timestamp, source, title, domain, url
                FROM raw_events
                WHERE timestamp >= ? AND timestamp < ?
                ORDER BY timestamp ASC
                """,
                (start, end),
            ).fetchall()

        return [
            RawEvent(
                timestamp=datetime.fromisoformat(timestamp),
                source=source,
                title=title,
                domain=domain,
                url=url,
            )
            for timestamp, source, title, domain, url in rows
        ]
