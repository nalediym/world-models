from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta

from life_world_model.config import Settings
from life_world_model.goals.engine import load_goals
from life_world_model.scoring.formula import score_day
from life_world_model.simulation.projector import ProjectionDay, project_intervention
from life_world_model.storage.sqlite_store import SQLiteStore


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ParallelLife:
    id: str  # short hash
    name: str  # user-friendly name
    intervention: str
    created_date: date
    duration_days: int
    projections: list[ProjectionDay]
    status: str  # "active", "completed", "abandoned"


@dataclass
class ParallelLivesComparison:
    real_life_scores: list[tuple[date, float | None]]  # None = no data
    lives: list[ParallelLife]
    divergence_points: list[str]  # "Day 3: Timeline B pulls ahead by 5%"


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def _generate_id(name: str, intervention: str, created: date) -> str:
    """Generate a short deterministic ID from name + intervention + date."""
    raw = f"{name}:{intervention}:{created.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _projections_to_json(projections: list[ProjectionDay]) -> str:
    """Serialise ProjectionDay list to JSON string."""
    return json.dumps(
        [
            {
                "day_number": p.day_number,
                "date": p.date.isoformat(),
                "score": p.score,
                "delta_from_baseline": p.delta_from_baseline,
                "habit_strength": p.habit_strength,
            }
            for p in projections
        ]
    )


def _projections_from_json(raw: str | None) -> list[ProjectionDay]:
    """Deserialise JSON string back to ProjectionDay list."""
    if not raw:
        return []
    items = json.loads(raw)
    return [
        ProjectionDay(
            day_number=item["day_number"],
            date=date.fromisoformat(item["date"]),
            score=item["score"],
            delta_from_baseline=item["delta_from_baseline"],
            habit_strength=item["habit_strength"],
        )
        for item in items
    ]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def create_parallel_life(
    store: SQLiteStore,
    settings: Settings,
    name: str,
    intervention: str,
    duration_days: int = 14,
) -> ParallelLife:
    """Create a new parallel life timeline.

    Runs the temporal projection, persists to SQLite, and returns the ParallelLife.
    """
    today = date.today()
    life_id = _generate_id(name, intervention, today)

    projection = project_intervention(
        store, settings, intervention, duration_days=duration_days
    )

    life = ParallelLife(
        id=life_id,
        name=name,
        intervention=intervention,
        created_date=today,
        duration_days=duration_days,
        projections=projection.days,
        status="active",
    )

    _save_parallel_life(store, life)
    return life


def _save_parallel_life(store: SQLiteStore, life: ParallelLife) -> None:
    """Persist a ParallelLife to SQLite."""
    import sqlite3

    store.initialize()
    with sqlite3.connect(store.database_path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO parallel_lives
               (id, name, intervention, created_date, duration_days, status, projections_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                life.id,
                life.name,
                life.intervention,
                life.created_date.isoformat(),
                life.duration_days,
                life.status,
                _projections_to_json(life.projections),
            ),
        )
        conn.commit()


def load_parallel_lives(
    store: SQLiteStore, status: str | None = None
) -> list[ParallelLife]:
    """Load parallel lives from SQLite, optionally filtered by status."""
    import sqlite3

    store.initialize()
    with sqlite3.connect(store.database_path) as conn:
        if status is not None:
            rows = conn.execute(
                """SELECT id, name, intervention, created_date, duration_days,
                          status, projections_json
                   FROM parallel_lives WHERE status = ?
                   ORDER BY created_date DESC""",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, name, intervention, created_date, duration_days,
                          status, projections_json
                   FROM parallel_lives
                   ORDER BY created_date DESC"""
            ).fetchall()

    return [
        ParallelLife(
            id=lid,
            name=name,
            intervention=interv,
            created_date=date.fromisoformat(cd),
            duration_days=dur,
            projections=_projections_from_json(proj_json),
            status=st,
        )
        for lid, name, interv, cd, dur, st, proj_json in rows
    ]


def load_parallel_life(store: SQLiteStore, life_id: str) -> ParallelLife | None:
    """Load a single parallel life by ID."""
    import sqlite3

    store.initialize()
    with sqlite3.connect(store.database_path) as conn:
        row = conn.execute(
            """SELECT id, name, intervention, created_date, duration_days,
                      status, projections_json
               FROM parallel_lives WHERE id = ?""",
            (life_id,),
        ).fetchone()

    if row is None:
        return None

    lid, name, interv, cd, dur, st, proj_json = row
    return ParallelLife(
        id=lid,
        name=name,
        intervention=interv,
        created_date=date.fromisoformat(cd),
        duration_days=dur,
        projections=_projections_from_json(proj_json),
        status=st,
    )


def update_parallel_life_status(
    store: SQLiteStore, life_id: str, new_status: str
) -> None:
    """Update the status of a parallel life (active -> completed/abandoned)."""
    import sqlite3

    store.initialize()
    with sqlite3.connect(store.database_path) as conn:
        conn.execute(
            "UPDATE parallel_lives SET status = ? WHERE id = ?",
            (new_status, life_id),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def _load_real_scores(
    store: SQLiteStore,
    settings: Settings,
    dates: list[date],
) -> list[tuple[date, float | None]]:
    """Load real day scores for a list of dates. Returns None for missing days."""
    from life_world_model.pipeline.bucketizer import build_life_states

    goals = load_goals()
    results: list[tuple[date, float | None]] = []

    for d in dates:
        events = store.load_raw_events_for_date(d)
        if not events:
            results.append((d, None))
            continue
        states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
        if not states:
            results.append((d, None))
            continue
        score_result = score_day(states, goals)
        results.append((d, score_result["total"]))

    return results


def compare_lives(
    store: SQLiteStore,
    settings: Settings,
    life_ids: list[str] | None = None,
) -> ParallelLivesComparison:
    """Compare real life scores with all active parallel lives."""
    if life_ids is not None:
        lives = [
            life
            for lid in life_ids
            if (life := load_parallel_life(store, lid)) is not None
        ]
    else:
        lives = load_parallel_lives(store, status="active")

    if not lives:
        return ParallelLivesComparison(
            real_life_scores=[],
            lives=[],
            divergence_points=[],
        )

    # Collect all dates across all lives
    all_dates: set[date] = set()
    for life in lives:
        for p in life.projections:
            all_dates.add(p.date)

    sorted_dates = sorted(all_dates)

    # Load real scores for those dates
    real_scores = _load_real_scores(store, settings, sorted_dates)

    # Build date -> real score map for divergence detection
    real_map: dict[date, float | None] = {d: s for d, s in real_scores}

    # Detect divergence points
    divergence_points: list[str] = []

    # For each day, compare lives against each other and real life
    life_projection_maps: list[dict[date, ProjectionDay]] = []
    for life in lives:
        pmap: dict[date, ProjectionDay] = {p.date: p for p in life.projections}
        life_projection_maps.append(pmap)

    for day_idx, d in enumerate(sorted_dates):
        real_score = real_map.get(d)

        # Compare lives pairwise — find if any timeline pulls ahead significantly
        for i, life_a in enumerate(lives):
            score_a = life_projection_maps[i].get(d)
            if score_a is None:
                continue

            # Compare with real life
            if real_score is not None:
                diff = score_a.score - real_score
                if abs(diff) >= 0.05:  # 5% threshold
                    direction = "ahead of" if diff > 0 else "behind"
                    divergence_points.append(
                        f"Day {day_idx + 1} ({d.isoformat()}): "
                        f"\"{life_a.name}\" is {direction} real life by {abs(diff):.1%}"
                    )

            # Compare with other timelines
            for j, life_b in enumerate(lives):
                if j <= i:
                    continue
                score_b = life_projection_maps[j].get(d)
                if score_b is None:
                    continue
                diff = score_a.score - score_b.score
                if abs(diff) >= 0.05:
                    if diff > 0:
                        divergence_points.append(
                            f"Day {day_idx + 1} ({d.isoformat()}): "
                            f"\"{life_a.name}\" pulls ahead of \"{life_b.name}\" by {abs(diff):.1%}"
                        )
                    else:
                        divergence_points.append(
                            f"Day {day_idx + 1} ({d.isoformat()}): "
                            f"\"{life_b.name}\" pulls ahead of \"{life_a.name}\" by {abs(diff):.1%}"
                        )

    return ParallelLivesComparison(
        real_life_scores=real_scores,
        lives=lives,
        divergence_points=divergence_points,
    )


# ---------------------------------------------------------------------------
# Display formatting
# ---------------------------------------------------------------------------


def format_comparison(comparison: ParallelLivesComparison) -> str:
    """Format the comparison for terminal display."""
    lines: list[str] = []
    lines.append("\u2501\u2501\u2501 PARALLEL LIVES \u2501\u2501\u2501")
    lines.append("")

    if not comparison.lives:
        lines.append("No active parallel lives. Create one with `lwm parallel create`.")
        return "\n".join(lines)

    # Header row
    header_parts = [f"{'':>18s}"]
    header_parts.append(f"{'Real Life':>12s}")
    name_row_parts = [f"{'':>18s}"]
    name_row_parts.append(f"{'':>12s}")

    for life in comparison.lives:
        label = f"Timeline {life.id[:4]}"
        header_parts.append(f"{label:>20s}")
        # Truncate name to 18 chars
        short_name = life.name[:18] if len(life.name) > 18 else life.name
        name_row_parts.append(f"{repr(short_name):>20s}")

    lines.append("  ".join(header_parts))
    lines.append("  ".join(name_row_parts))

    # Build date -> projection score maps
    life_proj_maps: list[dict[date, ProjectionDay]] = []
    for life in comparison.lives:
        life_proj_maps.append({p.date: p for p in life.projections})

    # Build real score map
    real_map: dict[date, float | None] = {d: s for d, s in comparison.real_life_scores}

    # Get all dates in order
    all_dates: set[date] = set()
    for d, _ in comparison.real_life_scores:
        all_dates.add(d)
    for life in comparison.lives:
        for p in life.projections:
            all_dates.add(p.date)

    sorted_dates = sorted(all_dates)

    for day_idx, d in enumerate(sorted_dates):
        day_label = f"Day {day_idx + 1} ({d.strftime('%b %d')})"
        row_parts = [f"{day_label:>18s}"]

        # Real life score
        real_score = real_map.get(d)
        if real_score is not None:
            row_parts.append(f"{real_score:11.1%} ")
        else:
            row_parts.append(f"{'no data':>12s}")

        # Each timeline
        for pmap in life_proj_maps:
            proj = pmap.get(d)
            if proj is not None:
                # Show score and delta from real
                if real_score is not None:
                    diff = proj.score - real_score
                    sign = "+" if diff >= 0 else ""
                    row_parts.append(f"{proj.score:7.1%} ({sign}{diff:.0%})   ")
                else:
                    row_parts.append(f"{proj.score:7.1%}           ")
            else:
                row_parts.append(f"{'--':>20s}")

        lines.append("  ".join(row_parts))

    # Summary: which timeline is winning
    if comparison.lives:
        avg_scores: list[tuple[str, float]] = []
        for life in comparison.lives:
            if life.projections:
                avg = sum(p.score for p in life.projections) / len(life.projections)
                avg_scores.append((life.name, avg))

        if len(avg_scores) >= 2:
            avg_scores.sort(key=lambda x: -x[1])
            winner_name, winner_avg = avg_scores[0]
            runner_name, runner_avg = avg_scores[1]
            diff = winner_avg - runner_avg
            lines.append("")
            lines.append(
                f"\"{winner_name}\" is winning by +{diff:.1%} average"
            )

    # Divergence points
    if comparison.divergence_points:
        lines.append("")
        # Show at most 5 divergence points to avoid clutter
        for point in comparison.divergence_points[:5]:
            lines.append(f"Divergence: {point}")
        if len(comparison.divergence_points) > 5:
            lines.append(
                f"  ... and {len(comparison.divergence_points) - 5} more divergence points"
            )

    return "\n".join(lines)
