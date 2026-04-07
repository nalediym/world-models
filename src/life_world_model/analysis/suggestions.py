from __future__ import annotations

from life_world_model.types import Pattern, Suggestion

# ---------------------------------------------------------------------------
# Impact ranking: high > medium > low
# ---------------------------------------------------------------------------

_IMPACT_ORDER = {"high": 0, "medium": 1, "low": 2}


def _impact_rank(impact: str) -> int:
    return _IMPACT_ORDER.get(impact, 1)


# ---------------------------------------------------------------------------
# Suggestion generators per pattern category
# ---------------------------------------------------------------------------


def _suggestion_from_time_sink(pattern: Pattern) -> Suggestion | None:
    """time_sink -> limit intervention."""
    evidence = pattern.evidence
    activity = evidence.get("activity", "unknown")
    total_hours = evidence.get("total_hours", 0)

    impact = "high" if total_hours > 2 else "medium"

    return Suggestion(
        title=f"Limit {activity}",
        rationale=(
            f"{activity} consumes {total_hours:.1f}h with high context-switching. "
            f"Capping it would reduce scattered time."
        ),
        intervention_type="limit",
        source_patterns=[pattern.name],
        predicted_impact=impact,
        score_delta=-round(total_hours * 0.05, 3),
    )


def _suggestion_from_trigger(pattern: Pattern) -> Suggestion | None:
    """trigger (context_switching_recovery) -> time_block to protect focus."""
    evidence = pattern.evidence
    recovery_minutes = evidence.get("avg_recovery_minutes", 0)

    impact = "high" if recovery_minutes > 30 else "medium"

    return Suggestion(
        title="Protect focus after high switching",
        rationale=(
            f"After high context-switching, it takes ~{recovery_minutes:.0f} min "
            f"to regain deep focus. Block uninterrupted time to prevent this."
        ),
        intervention_type="time_block",
        source_patterns=[pattern.name],
        predicted_impact=impact,
        score_delta=round(recovery_minutes * 0.002, 3),
    )


def _suggestion_from_correlation(pattern: Pattern) -> Suggestion | None:
    """correlation -> reorder activities."""
    evidence = pattern.evidence
    precursor = evidence.get("precursor", "unknown")
    outcome = evidence.get("outcome", "unknown")
    probability = evidence.get("probability", 0)

    # Only suggest reorder for positive outcomes (deep_focus, coding, research)
    positive_outcomes = {"deep_focus", "coding", "research", "ai_tooling"}
    negative_outcomes = {"scattered"}

    if outcome in positive_outcomes:
        return Suggestion(
            title=f"Do {precursor} before {outcome}",
            rationale=(
                f"{precursor} precedes {outcome} {probability:.0%} of the time. "
                f"Sequencing {precursor} before deep work may boost focus."
            ),
            intervention_type="reorder",
            source_patterns=[pattern.name],
            predicted_impact="medium",
            score_delta=round(probability * 0.1, 3),
        )
    elif outcome in negative_outcomes:
        return Suggestion(
            title=f"Avoid {precursor} before deep work",
            rationale=(
                f"{precursor} precedes scattered buckets {probability:.0%} of the time. "
                f"Reordering away from focus blocks may reduce switching cost."
            ),
            intervention_type="reorder",
            source_patterns=[pattern.name],
            predicted_impact="medium",
            score_delta=round(probability * 0.08, 3),
        )

    return None


def _suggestion_from_rhythm(pattern: Pattern) -> Suggestion | None:
    """rhythm (circadian_rhythm) -> time_block to protect focus window."""
    evidence = pattern.evidence
    peak_hours = evidence.get("peak_hours", [])

    if not peak_hours:
        return None

    peak_str = ", ".join(f"{h}:00" for h in peak_hours)

    return Suggestion(
        title="Protect focus window",
        rationale=(
            f"Peak focus hours are {peak_str}. "
            f"Block these for deep work — no meetings, no Slack."
        ),
        intervention_type="time_block",
        source_patterns=[pattern.name],
        predicted_impact="high",
        score_delta=0.05,
    )


def _suggestion_from_routine(pattern: Pattern) -> Suggestion | None:
    """routine -> time_block to keep the routine."""
    evidence = pattern.evidence
    activity = evidence.get("activity", "unknown")
    hour = evidence.get("hour", 0)
    frequency = evidence.get("frequency", 0)

    return Suggestion(
        title=f"Keep {activity} routine at {hour}:00",
        rationale=(
            f"{activity} at {hour}:00 happens {frequency:.0%} of days. "
            f"This consistency is worth protecting."
        ),
        intervention_type="time_block",
        source_patterns=[pattern.name],
        predicted_impact="low",
        score_delta=round(frequency * 0.02, 3),
    )


# ---------------------------------------------------------------------------
# Category -> generator map
# ---------------------------------------------------------------------------

_GENERATORS: dict[str, object] = {
    "time_sink": _suggestion_from_time_sink,
    "trigger": _suggestion_from_trigger,
    "correlation": _suggestion_from_correlation,
    "rhythm": _suggestion_from_rhythm,
    "routine": _suggestion_from_routine,
}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_suggestions(patterns: list[Pattern]) -> list[Suggestion]:
    """Generate actionable suggestions from discovered patterns.

    Each suggestion is grounded in source_patterns — no suggestions without evidence.
    """
    if not patterns:
        return []

    suggestions: list[Suggestion] = []
    for pattern in patterns:
        generator = _GENERATORS.get(pattern.category)
        if generator is None:
            continue
        suggestion = generator(pattern)
        if suggestion is not None:
            suggestions.append(suggestion)

    # Deduplicate: same activity + intervention_type → keep higher |score_delta|
    seen: dict[tuple[str, str], Suggestion] = {}
    for s in suggestions:
        # Extract activity from title for dedup key
        key = (_extract_activity(s.title), s.intervention_type)
        existing = seen.get(key)
        if existing is None or abs(s.score_delta) > abs(existing.score_delta):
            # Merge source_patterns if replacing
            if existing is not None:
                merged_sources = list(
                    dict.fromkeys(existing.source_patterns + s.source_patterns)
                )
                s.source_patterns = merged_sources
            seen[key] = s

    deduped = list(seen.values())

    # Sort: impact (high > medium > low), then abs(score_delta) descending
    deduped.sort(key=lambda s: (_impact_rank(s.predicted_impact), -abs(s.score_delta)))

    return deduped


def _extract_activity(title: str) -> str:
    """Best-effort extraction of the activity name from a suggestion title."""
    # Handles patterns like "Limit browsing", "Keep coding routine at 9:00", etc.
    lower = title.lower()
    for prefix in ("limit ", "keep ", "do ", "avoid ", "protect "):
        if lower.startswith(prefix):
            rest = title[len(prefix):]
            # Take first word as activity
            return rest.split()[0].lower() if rest.split() else lower
    return lower
