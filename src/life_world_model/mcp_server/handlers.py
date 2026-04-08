"""Tool handler functions for the LWM MCP server.

Each handler is a plain function that takes keyword arguments and returns a dict.
This module can be tested independently without starting the MCP server.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import date, timedelta

from life_world_model.config import Settings, load_settings
from life_world_model.goals.engine import load_goals
from life_world_model.pipeline.bucketizer import build_life_states
from life_world_model.scoring.formula import score_day, score_day_detailed
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import ExperimentStatus, LifeState, RawEvent


def _get_store(settings: Settings | None = None) -> tuple[Settings, SQLiteStore]:
    """Return (settings, store) pair, loading settings if not provided."""
    if settings is None:
        settings = load_settings()
    store = SQLiteStore(settings.database_path)
    return settings, store


def _build_multi_day_states(
    store: SQLiteStore,
    settings: Settings,
    days: int = 30,
) -> dict[date, list[LifeState]]:
    """Load events for the last N days and build LifeStates per day."""
    end = date.today()
    start = end - timedelta(days=days)
    events = store.load_raw_events_for_range(start, end + timedelta(days=1))
    if not events:
        return {}

    day_events: dict[date, list[RawEvent]] = defaultdict(list)
    for event in events:
        day_events[event.timestamp.date()].append(event)

    multi_day_states: dict[date, list[LifeState]] = {}
    for day, day_evts in sorted(day_events.items()):
        states = build_life_states(day_evts, bucket_minutes=settings.bucket_minutes)
        if states:
            multi_day_states[day] = states
    return multi_day_states


def _life_state_to_dict(state: LifeState) -> dict:
    """Serialize a LifeState to a JSON-safe dict."""
    return {
        "timestamp": state.timestamp.isoformat(),
        "primary_activity": state.primary_activity,
        "secondary_activity": state.secondary_activity,
        "domain": state.domain,
        "event_count": state.event_count,
        "confidence": state.confidence,
        "sources": state.sources,
        "dwell_seconds": state.dwell_seconds,
        "context_switches": state.context_switches,
        "session_depth": state.session_depth,
    }


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def handle_get_today_score(
    settings: Settings | None = None,
) -> dict:
    """Return today's day score, grade, and per-goal breakdown."""
    settings, store = _get_store(settings)
    today = date.today()
    events = store.load_raw_events_for_date(today)
    states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
    goals = load_goals()

    if not states:
        return {
            "date": today.isoformat(),
            "total": 0.0,
            "grade": "F",
            "metrics": {},
            "note": "No data collected for today. Run 'lwm collect' first.",
        }

    breakdown = score_day_detailed(states, goals)
    return {
        "date": today.isoformat(),
        "total": breakdown.total,
        "grade": breakdown.grade,
        "metrics": breakdown.per_goal,
        "trade_offs": breakdown.trade_offs,
        "pareto_optimal": breakdown.pareto_optimal,
    }


def handle_get_patterns(
    days: int = 30,
    settings: Settings | None = None,
) -> dict:
    """Return discovered behavioral patterns over the last N days."""
    from life_world_model.analysis.pattern_discovery import discover_patterns

    settings, store = _get_store(settings)
    multi_day_states = _build_multi_day_states(store, settings, days=days)

    if not multi_day_states:
        return {
            "patterns": [],
            "days_analyzed": 0,
            "note": "No data found. Run 'lwm collect' first.",
        }

    patterns = discover_patterns(multi_day_states, reference_date=date.today())
    return {
        "patterns": [
            {
                "name": p.name,
                "category": p.category,
                "description": p.description,
                "confidence": p.confidence,
                "days_observed": p.days_observed,
                "first_seen": p.first_seen.isoformat() if p.first_seen else None,
                "last_seen": p.last_seen.isoformat() if p.last_seen else None,
            }
            for p in patterns
            if p.category != "stale"
        ],
        "days_analyzed": len(multi_day_states),
    }


def handle_get_suggestions(
    days: int = 30,
    settings: Settings | None = None,
) -> dict:
    """Return ranked actionable suggestions with impact predictions."""
    from life_world_model.analysis.pattern_discovery import discover_patterns
    from life_world_model.analysis.suggestions import generate_suggestions

    settings, store = _get_store(settings)
    multi_day_states = _build_multi_day_states(store, settings, days=days)

    if not multi_day_states:
        return {
            "suggestions": [],
            "note": "No data found. Run 'lwm collect' first.",
        }

    patterns = discover_patterns(multi_day_states)
    if not patterns:
        return {
            "suggestions": [],
            "note": "No patterns found yet — need more data.",
        }

    feedback = store.load_suggestion_feedback()
    suggestions = generate_suggestions(patterns, feedback=feedback or None)

    return {
        "suggestions": [
            {
                "id": s.id,
                "title": s.title,
                "rationale": s.rationale,
                "intervention_type": s.intervention_type,
                "predicted_impact": s.predicted_impact,
                "score_delta": s.score_delta,
                "source_patterns": s.source_patterns,
            }
            for s in suggestions
        ],
    }


def handle_get_timeline(
    target_date: str | None = None,
    settings: Settings | None = None,
) -> dict:
    """Return the 15-min bucketed timeline for a specific date."""
    settings, store = _get_store(settings)

    if target_date is None:
        d = date.today()
    else:
        try:
            d = date.fromisoformat(target_date)
        except ValueError:
            return {"error": f"Invalid date format: {target_date}. Use YYYY-MM-DD."}

    events = store.load_raw_events_for_date(d)
    states = build_life_states(events, bucket_minutes=settings.bucket_minutes)

    if not states:
        return {
            "date": d.isoformat(),
            "buckets": [],
            "note": f"No data for {d}.",
        }

    return {
        "date": d.isoformat(),
        "bucket_count": len(states),
        "buckets": [_life_state_to_dict(s) for s in states],
    }


def handle_get_score_history(
    days: int = 30,
    settings: Settings | None = None,
) -> dict:
    """Return daily scores for the last N days."""
    settings, store = _get_store(settings)
    goals = load_goals()

    today = date.today()
    history: list[dict] = []

    for days_ago in range(days):
        d = today - timedelta(days=days_ago)
        events = store.load_raw_events_for_date(d)
        if not events:
            continue
        states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
        if not states:
            continue
        result = score_day(states, goals)
        history.append({
            "date": d.isoformat(),
            "total": result["total"],
            "grade": result["grade"],
            "metrics": result["metrics"],
        })

    return {
        "days_requested": days,
        "days_with_data": len(history),
        "history": history,
    }


def handle_get_experiments(
    settings: Settings | None = None,
) -> dict:
    """Return active and recent experiments with results."""
    settings, store = _get_store(settings)

    active = store.load_experiments(status=ExperimentStatus.ACTIVE)
    completed = store.load_experiments(status=ExperimentStatus.COMPLETED)
    cancelled = store.load_experiments(status=ExperimentStatus.CANCELLED)

    def _exp_dict(exp):
        return {
            "id": exp.id,
            "description": exp.description,
            "intervention": exp.intervention,
            "duration_days": exp.duration_days,
            "start_date": exp.start_date.isoformat(),
            "status": exp.status.value,
            "baseline_score": exp.baseline_score,
            "result_score": exp.result_score,
            "result_summary": exp.result_summary,
        }

    return {
        "active": [_exp_dict(e) for e in active],
        "completed": [_exp_dict(e) for e in completed],
        "cancelled": [_exp_dict(e) for e in cancelled],
    }


def handle_simulate(
    intervention: str,
    baseline_date: str | None = None,
    settings: Settings | None = None,
) -> dict:
    """Run a what-if simulation and return score delta."""
    from life_world_model.simulation.engine import simulate

    settings, store = _get_store(settings)

    bl_date = None
    if baseline_date:
        try:
            bl_date = date.fromisoformat(baseline_date)
        except ValueError:
            return {"error": f"Invalid date format: {baseline_date}. Use YYYY-MM-DD."}

    try:
        result = simulate(store, settings, intervention, baseline_date=bl_date)
    except Exception as exc:
        return {"error": f"Simulation failed: {exc}"}

    return {
        "intervention": result.intervention.description,
        "intervention_type": result.intervention.type,
        "baseline_score": result.baseline_score,
        "simulated_score": result.simulated_score,
        "score_delta": result.score_delta,
        "summary": result.summary,
    }


def handle_get_sources(
    settings: Settings | None = None,
) -> dict:
    """Return which data collectors are available and working."""
    import importlib

    settings, store = _get_store(settings)

    # Collector module names and their config paths
    collector_specs: list[tuple[str, str, str]] = [
        ("chrome", "life_world_model.collectors.chrome_history", "ChromeHistoryCollector"),
        ("knowledgec", "life_world_model.collectors.knowledgec", "KnowledgeCCollector"),
        ("shell", "life_world_model.collectors.shell_history", "ShellHistoryCollector"),
        ("git", "life_world_model.collectors.git_activity", "GitActivityCollector"),
        ("calendar", "life_world_model.collectors.calendar", "CalendarCollector"),
        ("screentime", "life_world_model.collectors.screen_time", "ScreenTimeCollector"),
        ("files", "life_world_model.collectors.recent_files", "RecentFilesCollector"),
        ("safari", "life_world_model.collectors.safari_history", "SafariHistoryCollector"),
    ]

    # Config-to-constructor-arg mapping
    config_map: dict[str, object] = {
        "chrome": lambda: (settings.chrome_history_path,),
        "knowledgec": lambda: (settings.knowledgec_path,),
        "shell": lambda: (settings.zsh_history_path,),
        "git": lambda: (settings.git_scan_paths or [],),
        "calendar": lambda: (settings.calendar_path,),
        "screentime": lambda: (settings.knowledgec_path,),
        "files": lambda: (),
        "safari": lambda: (settings.safari_history_path,),
    }

    sources: list[dict] = []
    for name, module_path, class_name in collector_specs:
        entry: dict = {"name": name, "installed": False, "available": False}
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            entry["installed"] = True
            args = config_map[name]()
            collector = cls(*args)
            entry["available"] = collector.is_available()
        except (ImportError, Exception):
            pass
        sources.append(entry)

    return {"sources": sources}


def handle_get_goals(
    settings: Settings | None = None,
) -> dict:
    """Return the user's configured goals and weights."""
    goals = load_goals()
    return {
        "goals": [
            {
                "name": g.name,
                "description": g.description,
                "metric": g.metric,
                "weight": g.weight,
                "target": g.target,
            }
            for g in goals
        ],
    }
