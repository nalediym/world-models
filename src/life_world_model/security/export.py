"""Redacted data export for sharing demo data or debugging."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from life_world_model.security.redaction import apply_privacy_filter
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import RawEvent


def export_redacted(
    store: SQLiteStore,
    output_path: Path,
    privacy_level: str = "enhanced",
) -> int:
    """Export the database with all sensitive data redacted.

    Creates a new SQLite database at *output_path* containing all events from
    the source *store*, filtered through :func:`apply_privacy_filter` at the
    given *privacy_level*.

    Returns the count of events exported.
    """
    # Load all events from the source database.
    store.initialize()
    with sqlite3.connect(store.database_path) as conn:
        rows = conn.execute(
            """SELECT timestamp, source, title, domain, url,
                      duration_seconds, metadata
               FROM raw_events ORDER BY timestamp ASC"""
        ).fetchall()

    events = [
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

    # Apply privacy filter.
    filtered = apply_privacy_filter(events, privacy_level)

    # Write to a new database.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_path) as out_conn:
        out_conn.execute(
            """CREATE TABLE IF NOT EXISTS raw_events (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 timestamp TEXT NOT NULL,
                 source TEXT NOT NULL,
                 title TEXT,
                 domain TEXT,
                 url TEXT,
                 duration_seconds REAL,
                 metadata TEXT
               )"""
        )
        out_conn.executemany(
            """INSERT INTO raw_events
               (timestamp, source, title, domain, url, duration_seconds, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    e.timestamp.isoformat(),
                    e.source,
                    e.title,
                    e.domain,
                    e.url,
                    e.duration_seconds,
                    json.dumps(e.metadata) if e.metadata else None,
                )
                for e in filtered
            ],
        )
        out_conn.commit()

    return len(filtered)
