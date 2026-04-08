from __future__ import annotations

from life_world_model.types import ProposedExperiment, Suggestion


def suggest_experiments(
    suggestions: list[Suggestion],
    existing_experiments: list[dict] | None = None,
) -> list[ProposedExperiment]:
    """Propose experiments from HIGH-impact suggestions.

    Rules:
    - Only suggest from HIGH impact suggestions
    - Don't suggest if an active experiment already covers similar intervention
    - Max 1 proposed experiment at a time (don't overwhelm)
    """
    if not suggestions:
        return []

    if existing_experiments is None:
        existing_experiments = []

    # Collect descriptions of active experiments for dedup
    active_descriptions = {
        exp.get("description", "").lower() for exp in existing_experiments
    }
    active_interventions = {
        exp.get("intervention_type", "").lower() for exp in existing_experiments
    }

    high_impact = [
        s for s in suggestions if s.predicted_impact == "high"
    ]

    if not high_impact:
        return []

    for s in high_impact:
        # Check if an active experiment already covers this intervention type + activity
        title_lower = s.title.lower()
        if any(title_lower in desc for desc in active_descriptions):
            continue
        if s.intervention_type.lower() in active_interventions:
            continue

        proposed = ProposedExperiment(
            description=(
                f"Try: {s.title} for 3 days. "
                f"Predicted score change: {s.score_delta:+.1%}. "
                f"Rationale: {s.rationale}"
            ),
            duration_days=3,
            expected_impact=s.predicted_impact,
            source_suggestion_id=s.title,
            predicted_score_delta=s.score_delta,
        )
        # Max 1 proposed experiment
        return [proposed]

    return []
