"""Flask application for the Life World Model dashboard."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from life_world_model.analysis.pattern_discovery import discover_patterns
from life_world_model.analysis.suggestions import generate_suggestions
from life_world_model.config import Settings, load_settings
from life_world_model.goals.engine import load_goals
from life_world_model.pipeline.bucketizer import build_life_states
from life_world_model.scoring.formula import score_day
from life_world_model.simulation.engine import simulate
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import LifeState


def _get_store(settings: Settings) -> SQLiteStore:
    """Create and initialize a SQLiteStore from settings."""
    store = SQLiteStore(settings.database_path)
    store.initialize()
    return store


def _build_multi_day_states(
    store: SQLiteStore, settings: Settings, days: int = 30
) -> dict[date, list[LifeState]]:
    """Load events for the last N days and build per-day LifeStates."""
    end = date.today()
    start = end - timedelta(days=days)
    multi_day_states: dict[date, list[LifeState]] = {}
    current = start
    while current <= end:
        events = store.load_raw_events_for_date(current)
        if events:
            states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
            if states:
                multi_day_states[current] = states
        current += timedelta(days=1)
    return multi_day_states


def _suggestion_id(title: str) -> str:
    """Deterministic short ID for a suggestion based on its title."""
    return hashlib.sha256(title.encode()).hexdigest()[:12]


def _states_to_timeline(states: list[LifeState]) -> list[dict]:
    """Convert LifeStates to a JSON-serializable timeline."""
    return [
        {
            "time": s.timestamp.strftime("%H:%M"),
            "hour": s.timestamp.hour,
            "minute": s.timestamp.minute,
            "activity": s.primary_activity,
            "secondary": s.secondary_activity,
            "domain": s.domain,
            "event_count": s.event_count,
            "confidence": round(s.confidence, 2),
            "sources": s.sources or [],
            "dwell_seconds": s.dwell_seconds,
            "context_switches": s.context_switches,
            "session_depth": s.session_depth,
        }
        for s in states
    ]


def _pattern_to_dict(p) -> dict:
    """Convert a Pattern to a JSON-serializable dict."""
    return {
        "name": p.name,
        "category": p.category,
        "description": p.description,
        "evidence": p.evidence,
        "confidence": round(p.confidence, 3),
        "days_observed": p.days_observed,
        "first_seen": p.first_seen.isoformat() if p.first_seen else None,
        "last_seen": p.last_seen.isoformat() if p.last_seen else None,
    }


def _suggestion_to_dict(s) -> dict:
    """Convert a Suggestion to a JSON-serializable dict."""
    return {
        "id": _suggestion_id(s.title),
        "title": s.title,
        "rationale": s.rationale,
        "intervention_type": s.intervention_type,
        "source_patterns": s.source_patterns,
        "predicted_impact": s.predicted_impact,
        "score_delta": round(s.score_delta, 4),
    }


# In-memory suggestion status tracking (accept/reject)
# Maps suggestion ID -> "accepted" | "rejected"
_suggestion_status: dict[str, str] = {}


def create_app(settings: Settings | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )

    if settings is None:
        settings = load_settings()

    # Store settings on app for access in routes
    app.config["LWM_SETTINGS"] = settings

    # -----------------------------------------------------------------------
    # Page routes
    # -----------------------------------------------------------------------

    @app.route("/")
    def page_today():
        return render_template("today.html")

    @app.route("/patterns")
    def page_patterns():
        return render_template("patterns.html")

    @app.route("/suggestions")
    def page_suggestions():
        return render_template("suggestions.html")

    @app.route("/goals")
    def page_goals():
        return render_template("goals.html")

    @app.route("/history")
    def page_history():
        return render_template("history.html")

    @app.route("/simulate")
    def page_simulate():
        return render_template("simulate.html")

    # -----------------------------------------------------------------------
    # API routes
    # -----------------------------------------------------------------------

    @app.route("/api/today")
    def api_today():
        store = _get_store(settings)
        today = date.today()
        events = store.load_raw_events_for_date(today)
        states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
        goals = load_goals()
        result = score_day(states, goals)
        timeline = _states_to_timeline(states)

        return jsonify({
            "date": today.isoformat(),
            "timeline": timeline,
            "score": result,
            "event_count": len(events),
            "bucket_count": len(states),
        })

    @app.route("/api/patterns")
    def api_patterns():
        store = _get_store(settings)
        multi_day_states = _build_multi_day_states(store, settings)
        patterns = discover_patterns(multi_day_states)
        return jsonify({
            "patterns": [_pattern_to_dict(p) for p in patterns],
            "days_analyzed": len(multi_day_states),
        })

    @app.route("/api/suggestions")
    def api_suggestions():
        store = _get_store(settings)
        multi_day_states = _build_multi_day_states(store, settings)
        patterns = discover_patterns(multi_day_states)
        suggestions = generate_suggestions(patterns)
        result = []
        for s in suggestions:
            d = _suggestion_to_dict(s)
            d["status"] = _suggestion_status.get(d["id"], "pending")
            result.append(d)
        return jsonify({
            "suggestions": result,
            "pattern_count": len(patterns),
        })

    @app.route("/api/suggestions/<suggestion_id>/accept", methods=["POST"])
    def api_accept_suggestion(suggestion_id: str):
        _suggestion_status[suggestion_id] = "accepted"
        return jsonify({"id": suggestion_id, "status": "accepted"})

    @app.route("/api/suggestions/<suggestion_id>/reject", methods=["POST"])
    def api_reject_suggestion(suggestion_id: str):
        _suggestion_status[suggestion_id] = "rejected"
        return jsonify({"id": suggestion_id, "status": "rejected"})

    @app.route("/api/goals")
    def api_goals():
        store = _get_store(settings)
        today = date.today()
        events = store.load_raw_events_for_date(today)
        states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
        goals = load_goals()
        result = score_day(states, goals)

        goals_data = []
        for g in goals:
            metric_data = result["metrics"].get(g.name, {})
            goals_data.append({
                "name": g.name,
                "description": g.description,
                "metric": g.metric,
                "weight": g.weight,
                "target": g.target,
                "raw": metric_data.get("raw", 0.0),
                "weighted": metric_data.get("weighted", 0.0),
            })

        return jsonify({
            "goals": goals_data,
            "total_score": result["total"],
            "grade": result["grade"],
            "date": today.isoformat(),
        })

    @app.route("/api/history")
    def api_history():
        store = _get_store(settings)
        days = request.args.get("days", 30, type=int)
        days = min(days, 365)  # Cap at 1 year
        goals = load_goals()

        end = date.today()
        start = end - timedelta(days=days)
        history = []
        current = start
        while current <= end:
            events = store.load_raw_events_for_date(current)
            if events:
                states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
                result = score_day(states, goals)
                history.append({
                    "date": current.isoformat(),
                    "score": result["total"],
                    "grade": result["grade"],
                    "bucket_count": len(states),
                    "event_count": len(events),
                })
            else:
                history.append({
                    "date": current.isoformat(),
                    "score": 0.0,
                    "grade": "F",
                    "bucket_count": 0,
                    "event_count": 0,
                })
            current += timedelta(days=1)

        return jsonify({
            "history": history,
            "days": days,
        })

    @app.route("/api/simulate", methods=["POST"])
    def api_simulate():
        data = request.get_json(silent=True) or {}
        scenario = data.get("scenario", "")
        baseline_date_str = data.get("baseline_date")
        narrate = data.get("narrate", False)
        voice_name = data.get("voice")

        if not scenario:
            return jsonify({"error": "scenario is required"}), 400

        store = _get_store(settings)
        bl_date = None
        if baseline_date_str:
            try:
                bl_date = date.fromisoformat(baseline_date_str)
            except ValueError:
                return jsonify({"error": "invalid baseline_date format"}), 400

        result = simulate(store, settings, scenario, baseline_date=bl_date)

        response_data = {
            "intervention": {
                "type": result.intervention.type,
                "activity": result.intervention.activity,
                "params": result.intervention.params,
                "description": result.intervention.description,
            },
            "baseline_score": round(result.baseline_score, 4),
            "simulated_score": round(result.simulated_score, 4),
            "score_delta": round(result.score_delta, 4),
            "summary": result.summary,
        }

        if narrate:
            from life_world_model.simulation.narrator import narrate_simulation

            target_date = bl_date or date.today()
            if result.baseline_states:
                target_date = result.baseline_states[0].timestamp.date()

            try:
                narrative = narrate_simulation(
                    baseline_states=result.baseline_states,
                    simulated_states=result.simulated_states,
                    intervention_text=scenario,
                    target_date=target_date,
                    settings=settings,
                    baseline_score=result.baseline_score,
                    simulated_score=result.simulated_score,
                    voice_name=voice_name,
                )
                response_data["baseline_narrative"] = narrative.baseline_narrative
                response_data["simulated_narrative"] = narrative.simulated_narrative
                response_data["comparison"] = narrative.comparison
                response_data["voice"] = narrative.voice
            except Exception:
                response_data["baseline_narrative"] = None
                response_data["simulated_narrative"] = None
                response_data["comparison"] = None
                response_data["voice"] = None

        return jsonify(response_data)

    return app


def run_dashboard(port: int = 8765, debug: bool = True) -> None:
    """Start the Flask development server."""
    settings = load_settings()
    app = create_app(settings)
    print(f"Starting Life World Model dashboard at http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=debug)
