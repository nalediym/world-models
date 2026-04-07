from __future__ import annotations

import copy
import re
from datetime import date, datetime, timedelta

from life_world_model.config import Settings
from life_world_model.goals.engine import load_goals
from life_world_model.scoring.formula import score_day
from life_world_model.simulation.types import Intervention, SimulationResult
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import LifeState

# ---------------------------------------------------------------------------
# Activity aliases — normalize common short names to canonical activities
# ---------------------------------------------------------------------------

ACTIVITY_ALIASES: dict[str, str] = {
    "code": "coding",
    "browse": "browsing",
    "walk": "walking",
    "slack": "communication",
    "email": "communication",
    "read": "research",
    "meeting": "meeting",
    "research": "research",
    "coding": "coding",
    "browsing": "browsing",
    "walking": "walking",
    "communication": "communication",
    "idle": "idle",
    "exercise": "exercise",
    "ai_tooling": "ai_tooling",
}


def _resolve_activity(raw: str) -> str:
    """Resolve a raw activity name to its canonical form."""
    return ACTIVITY_ALIASES.get(raw.lower(), raw.lower())


# ---------------------------------------------------------------------------
# Intervention parser
# ---------------------------------------------------------------------------

# Pattern: "code from 8-10am" or "coding from 14-16" or "research from 9am-11am"
_TIME_BLOCK_RE = re.compile(
    r"(\w+)\s+from\s+(\d{1,2})(?::(\d{2}))?\s*([ap]m)?\s*[-–to]+\s*(\d{1,2})(?::(\d{2}))?\s*([ap]m)?",
    re.IGNORECASE,
)

# Pattern: "stop X after 9pm" or "stop browsing after 21"
_ELIMINATE_RE = re.compile(
    r"stop\s+(\w+)(?:\s+after\s+(\d{1,2})\s*([ap]m)?)?",
    re.IGNORECASE,
)

# Pattern: "limit X to 1hr" or "limit browsing to 2 hours" or "limit X to 30min"
_LIMIT_RE = re.compile(
    r"limit\s+(\w+)\s+to\s+(\d+)\s*(hr|hour|hours|min|mins|minutes?)",
    re.IGNORECASE,
)

# Pattern: "add 30min walk at lunch" or "add 1hr exercise at 7am"
_ADD_RE = re.compile(
    r"add\s+(\d+)\s*(min|mins|minutes?|hr|hour|hours?)\s+(\w+)(?:\s+at\s+(\w+|\d{1,2}\s*[ap]m?))?",
    re.IGNORECASE,
)


def _parse_hour(hour_str: str, ampm: str | None) -> int:
    """Convert hour string + optional am/pm to 24h int."""
    h = int(hour_str)
    if ampm:
        ampm = ampm.lower()
        if ampm == "pm" and h != 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
    return h


def _duration_to_minutes(amount: int, unit: str) -> int:
    """Convert amount + unit to minutes."""
    unit = unit.lower()
    if unit.startswith("hr") or unit.startswith("hour"):
        return amount * 60
    return amount


def parse_intervention(text: str) -> Intervention:
    """Parse a natural-language intervention description into an Intervention."""
    text = text.strip()

    # Try time_block: "code from 8-10am"
    m = _TIME_BLOCK_RE.search(text)
    if m:
        activity = _resolve_activity(m.group(1))
        start_h = _parse_hour(m.group(2), m.group(4) or m.group(7))
        end_h = _parse_hour(m.group(5), m.group(7) or m.group(4))
        return Intervention(
            type="time_block",
            activity=activity,
            params={"start_hour": start_h, "end_hour": end_h},
            description=text,
        )

    # Try eliminate: "stop browsing after 9pm"
    m = _ELIMINATE_RE.search(text)
    if m:
        activity = _resolve_activity(m.group(1))
        params: dict = {}
        if m.group(2):
            params["after_hour"] = _parse_hour(m.group(2), m.group(3))
        return Intervention(
            type="eliminate",
            activity=activity,
            params=params,
            description=text,
        )

    # Try limit: "limit browsing to 1hr"
    m = _LIMIT_RE.search(text)
    if m:
        activity = _resolve_activity(m.group(1))
        max_minutes = _duration_to_minutes(int(m.group(2)), m.group(3))
        return Intervention(
            type="limit",
            activity=activity,
            params={"max_minutes": max_minutes},
            description=text,
        )

    # Try add: "add 30min walk at lunch"
    m = _ADD_RE.search(text)
    if m:
        duration_min = _duration_to_minutes(int(m.group(1)), m.group(2))
        activity = _resolve_activity(m.group(3))
        params = {"duration_minutes": duration_min}
        if m.group(4):
            # Try to parse as hour
            at_text = m.group(4).strip()
            at_match = re.match(r"(\d{1,2})\s*([ap]m)?", at_text, re.IGNORECASE)
            if at_match:
                params["at_hour"] = _parse_hour(at_match.group(1), at_match.group(2))
            else:
                params["at_label"] = at_text
        return Intervention(
            type="add",
            activity=activity,
            params=params,
            description=text,
        )

    # Unknown
    return Intervention(
        type="unknown",
        activity="",
        params={},
        description=text,
    )


# ---------------------------------------------------------------------------
# Baseline loader
# ---------------------------------------------------------------------------


def load_baseline(
    store: SQLiteStore,
    settings: Settings,
    baseline_date: date | None = None,
) -> tuple[date, list[LifeState]]:
    """Load baseline states for a specific date or pick the best of the last 7 days."""
    from life_world_model.pipeline.bucketizer import build_life_states

    if baseline_date is not None:
        events = store.load_raw_events_for_date(baseline_date)
        states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
        return baseline_date, states

    # Pick the day with the most events from the last 7 days
    today = date.today()
    best_date = today
    best_states: list[LifeState] = []
    best_count = 0

    for days_ago in range(7):
        d = today - timedelta(days=days_ago)
        events = store.load_raw_events_for_date(d)
        if len(events) > best_count:
            states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
            best_date = d
            best_states = states
            best_count = len(events)

    return best_date, best_states


# ---------------------------------------------------------------------------
# Apply intervention to states (deep copy, never mutate originals)
# ---------------------------------------------------------------------------

BUCKET_MINUTES = 15


def apply_intervention(
    states: list[LifeState], intervention: Intervention
) -> list[LifeState]:
    """Apply an intervention to a copy of the states. Never mutates the originals."""
    if not states:
        return []

    result = copy.deepcopy(states)

    if intervention.type == "time_block":
        start_h = intervention.params.get("start_hour", 0)
        end_h = intervention.params.get("end_hour", 24)
        for s in result:
            if start_h <= s.timestamp.hour < end_h:
                s.primary_activity = intervention.activity
                s.confidence = 1.0

    elif intervention.type == "eliminate":
        after_hour = intervention.params.get("after_hour")
        for s in result:
            if s.primary_activity == intervention.activity:
                if after_hour is not None and s.timestamp.hour < after_hour:
                    continue
                s.primary_activity = "idle"
                s.confidence = 1.0

    elif intervention.type == "limit":
        max_minutes = intervention.params.get("max_minutes", 60)
        max_buckets = max(1, max_minutes // BUCKET_MINUTES)
        count = 0
        for s in result:
            if s.primary_activity == intervention.activity:
                count += 1
                if count > max_buckets:
                    s.primary_activity = "idle"
                    s.confidence = 1.0

    elif intervention.type == "add":
        duration_minutes = intervention.params.get("duration_minutes", 30)
        buckets_needed = max(1, duration_minutes // BUCKET_MINUTES)
        at_hour = intervention.params.get("at_hour")

        # Find idle buckets to replace, preferring those at the target hour
        idle_indices = [
            i for i, s in enumerate(result) if s.primary_activity == "idle"
        ]

        if at_hour is not None:
            # Prefer idle buckets near the target hour
            idle_indices.sort(
                key=lambda i: abs(result[i].timestamp.hour - at_hour)
            )

        replaced = 0
        for i in idle_indices:
            if replaced >= buckets_needed:
                break
            result[i].primary_activity = intervention.activity
            result[i].confidence = 1.0
            replaced += 1

    return result


# ---------------------------------------------------------------------------
# Full simulation
# ---------------------------------------------------------------------------


def simulate(
    store: SQLiteStore,
    settings: Settings,
    text: str,
    baseline_date: date | None = None,
) -> SimulationResult:
    """Run a what-if simulation: parse intervention, apply to baseline, compare scores."""
    intervention = parse_intervention(text)
    used_date, baseline_states = load_baseline(store, settings, baseline_date)

    goals = load_goals()
    baseline_result = score_day(baseline_states, goals)
    baseline_score = baseline_result["total"]

    simulated_states = apply_intervention(baseline_states, intervention)
    simulated_result = score_day(simulated_states, goals)
    simulated_score = simulated_result["total"]

    delta = simulated_score - baseline_score
    direction = "+" if delta >= 0 else ""
    summary = (
        f"Intervention: {intervention.description}\n"
        f"Baseline ({used_date}): {baseline_score:.1%} ({baseline_result['grade']})\n"
        f"Simulated: {simulated_score:.1%} ({simulated_result['grade']})\n"
        f"Delta: {direction}{delta:.1%}"
    )

    return SimulationResult(
        baseline_states=baseline_states,
        simulated_states=simulated_states,
        intervention=intervention,
        baseline_score=baseline_score,
        simulated_score=simulated_score,
        score_delta=delta,
        summary=summary,
    )
