from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from life_world_model.types import (
    Experiment,
    ExperimentStatus,
    FeedbackAction,
    Pattern,
    RawEvent,
    SuggestionFeedback,
)


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

SUGGESTION_FEEDBACK_SCHEMA = """
CREATE TABLE IF NOT EXISTS suggestion_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  suggestion_id TEXT NOT NULL,
  suggestion_title TEXT NOT NULL,
  action TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  notes TEXT
)
"""

EXPERIMENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
  id TEXT PRIMARY KEY,
  description TEXT NOT NULL,
  intervention TEXT NOT NULL,
  duration_days INTEGER NOT NULL,
  start_date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  baseline_score REAL,
  result_score REAL,
  result_summary TEXT
)
"""

PATTERNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS discovered_patterns (
  name TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  description TEXT NOT NULL,
  evidence TEXT NOT NULL,
  confidence REAL NOT NULL,
  days_observed INTEGER NOT NULL,
  first_seen TEXT,
  last_seen TEXT
)
"""

PARALLEL_LIVES_SCHEMA = """
CREATE TABLE IF NOT EXISTS parallel_lives (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  intervention TEXT NOT NULL,
  created_date TEXT NOT NULL,
  duration_days INTEGER NOT NULL,
  status TEXT DEFAULT 'active',
  projections_json TEXT
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
            connection.execute(SUGGESTION_FEEDBACK_SCHEMA)
            connection.execute(EXPERIMENTS_SCHEMA)
            connection.execute(PATTERNS_SCHEMA)
            connection.execute(PARALLEL_LIVES_SCHEMA)
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

    # ------------------------------------------------------------------
    # Suggestion feedback
    # ------------------------------------------------------------------

    def save_suggestion_feedback(self, feedback: SuggestionFeedback) -> None:
        self.initialize()
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """INSERT INTO suggestion_feedback
                   (suggestion_id, suggestion_title, action, timestamp, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    feedback.suggestion_id,
                    feedback.suggestion_title,
                    feedback.action.value,
                    feedback.timestamp.isoformat(),
                    feedback.notes,
                ),
            )
            conn.commit()

    def load_suggestion_feedback(self) -> list[SuggestionFeedback]:
        self.initialize()
        with sqlite3.connect(self.database_path) as conn:
            rows = conn.execute(
                """SELECT suggestion_id, suggestion_title, action, timestamp, notes
                   FROM suggestion_feedback ORDER BY timestamp DESC"""
            ).fetchall()
        return [
            SuggestionFeedback(
                suggestion_id=sid,
                suggestion_title=title,
                action=FeedbackAction(action),
                timestamp=datetime.fromisoformat(ts),
                notes=notes,
            )
            for sid, title, action, ts, notes in rows
        ]

    # ------------------------------------------------------------------
    # Experiments
    # ------------------------------------------------------------------

    def save_experiment(self, exp: Experiment) -> None:
        self.initialize()
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """INSERT INTO experiments
                   (id, description, intervention, duration_days, start_date,
                    status, baseline_score, result_score, result_summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    exp.id,
                    exp.description,
                    exp.intervention,
                    exp.duration_days,
                    exp.start_date.isoformat(),
                    exp.status.value,
                    exp.baseline_score,
                    exp.result_score,
                    exp.result_summary,
                ),
            )
            conn.commit()

    def update_experiment(self, exp: Experiment) -> None:
        self.initialize()
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """UPDATE experiments
                   SET status = ?, baseline_score = ?, result_score = ?,
                       result_summary = ?
                   WHERE id = ?""",
                (
                    exp.status.value,
                    exp.baseline_score,
                    exp.result_score,
                    exp.result_summary,
                    exp.id,
                ),
            )
            conn.commit()

    def load_experiments(
        self, status: ExperimentStatus | None = None
    ) -> list[Experiment]:
        self.initialize()
        with sqlite3.connect(self.database_path) as conn:
            if status is not None:
                rows = conn.execute(
                    """SELECT id, description, intervention, duration_days,
                              start_date, status, baseline_score, result_score,
                              result_summary
                       FROM experiments WHERE status = ?
                       ORDER BY start_date DESC""",
                    (status.value,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, description, intervention, duration_days,
                              start_date, status, baseline_score, result_score,
                              result_summary
                       FROM experiments ORDER BY start_date DESC"""
                ).fetchall()
        return [
            Experiment(
                id=eid,
                description=desc,
                intervention=interv,
                duration_days=dur,
                start_date=date.fromisoformat(sd),
                status=ExperimentStatus(st),
                baseline_score=bscore,
                result_score=rscore,
                result_summary=rsummary,
            )
            for eid, desc, interv, dur, sd, st, bscore, rscore, rsummary in rows
        ]

    def load_experiment(self, experiment_id: str) -> Experiment | None:
        self.initialize()
        with sqlite3.connect(self.database_path) as conn:
            row = conn.execute(
                """SELECT id, description, intervention, duration_days,
                          start_date, status, baseline_score, result_score,
                          result_summary
                   FROM experiments WHERE id = ?""",
                (experiment_id,),
            ).fetchone()
        if row is None:
            return None
        eid, desc, interv, dur, sd, st, bscore, rscore, rsummary = row
        return Experiment(
            id=eid,
            description=desc,
            intervention=interv,
            duration_days=dur,
            start_date=date.fromisoformat(sd),
            status=ExperimentStatus(st),
            baseline_score=bscore,
            result_score=rscore,
            result_summary=rsummary,
        )

    # ------------------------------------------------------------------
    # Patterns
    # ------------------------------------------------------------------

    def save_patterns(self, patterns: list[Pattern]) -> None:
        """Upsert discovered patterns."""
        self.initialize()
        with sqlite3.connect(self.database_path) as conn:
            for p in patterns:
                conn.execute(
                    """INSERT OR REPLACE INTO discovered_patterns
                       (name, category, description, evidence, confidence,
                        days_observed, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        p.name,
                        p.category,
                        p.description,
                        json.dumps(p.evidence),
                        p.confidence,
                        p.days_observed,
                        p.first_seen.isoformat() if p.first_seen else None,
                        p.last_seen.isoformat() if p.last_seen else None,
                    ),
                )
            conn.commit()

    def load_patterns(self) -> list[Pattern]:
        self.initialize()
        with sqlite3.connect(self.database_path) as conn:
            rows = conn.execute(
                """SELECT name, category, description, evidence, confidence,
                          days_observed, first_seen, last_seen
                   FROM discovered_patterns
                   ORDER BY confidence DESC"""
            ).fetchall()
        return [
            Pattern(
                name=name,
                category=cat,
                description=desc,
                evidence=json.loads(ev),
                confidence=conf,
                days_observed=days,
                first_seen=date.fromisoformat(fs) if fs else None,
                last_seen=date.fromisoformat(ls) if ls else None,
            )
            for name, cat, desc, ev, conf, days, fs, ls in rows
        ]

    def delete_patterns(self, pattern_names: list[str]) -> None:
        """Remove patterns that have decayed below threshold."""
        self.initialize()
        if not pattern_names:
            return
        placeholders = ",".join("?" for _ in pattern_names)
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                f"DELETE FROM discovered_patterns WHERE name IN ({placeholders})",
                pattern_names,
            )
            conn.commit()
