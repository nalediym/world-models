from __future__ import annotations

import json
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

MIGRATIONS = [
    "ALTER TABLE raw_events ADD COLUMN duration_seconds REAL",
    "ALTER TABLE raw_events ADD COLUMN metadata TEXT",
]


class SQLiteStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(SCHEMA)
            self._run_migrations(connection)
            connection.commit()

    def _run_migrations(self, connection: sqlite3.Connection) -> None:
        existing = {
            row[1] for row in connection.execute("PRAGMA table_info(raw_events)").fetchall()
        }
        for migration in MIGRATIONS:
            col_name = migration.split("ADD COLUMN ")[1].split()[0]
            if col_name not in existing:
                connection.execute(migration)

    def save_raw_events(self, events: list[RawEvent]) -> None:
        self.initialize()
        rows = [
            (
                event.timestamp.isoformat(),
                event.source,
                event.title,
                event.domain,
                event.url,
                event.duration_seconds,
                json.dumps(event.metadata) if event.metadata else None,
            )
            for event in events
        ]
        with sqlite3.connect(self.database_path) as connection:
            connection.executemany(
                """INSERT OR IGNORE INTO raw_events
                   (timestamp, source, title, domain, url, duration_seconds, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            connection.commit()

    def load_raw_events_for_date(self, target_date: date) -> list[RawEvent]:
        return self.load_raw_events_for_range(target_date, target_date + timedelta(days=1))

    def load_raw_events_for_range(
        self, start_date: date, end_date: date
    ) -> list[RawEvent]:
        self.initialize()
        start = datetime.combine(start_date, datetime.min.time()).isoformat()
        end = datetime.combine(end_date, datetime.min.time()).isoformat()
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT timestamp, source, title, domain, url, duration_seconds, metadata
                FROM raw_events
                WHERE timestamp >= ? AND timestamp < ?
                ORDER BY timestamp ASC
                """,
                (start, end),
            ).fetchall()

        return [
            RawEvent(
                timestamp=datetime.fromisoformat(ts),
                source=source,
                title=title,
                domain=domain,
                url=url,
                duration_seconds=dur,
                metadata=json.loads(meta) if meta else None,
            )
            for ts, source, title, domain, url, dur, meta in rows
        ]
