from __future__ import annotations

from life_world_model.analysis.proactive import suggest_experiments
from life_world_model.types import ProposedExperiment, Suggestion


def _make_suggestion(
    title: str = "Protect focus window",
    impact: str = "high",
    intervention_type: str = "time_block",
    score_delta: float = 0.05,
    source_patterns: list[str] | None = None,
) -> Suggestion:
    if source_patterns is None:
        source_patterns = ["circadian_rhythm"]
    return Suggestion(
        title=title,
        rationale="Test rationale for suggestion.",
        intervention_type=intervention_type,
        source_patterns=source_patterns,
        predicted_impact=impact,
        score_delta=score_delta,
    )


class TestSuggestExperiments:
    def test_generates_from_high_impact(self) -> None:
        """Should generate a proposed experiment from HIGH impact suggestions."""
        suggestions = [_make_suggestion(impact="high")]
        result = suggest_experiments(suggestions)
        assert len(result) == 1
        assert isinstance(result[0], ProposedExperiment)
        assert result[0].duration_days == 3
        assert result[0].expected_impact == "high"

    def test_ignores_medium_impact(self) -> None:
        """Should NOT generate experiments from MEDIUM impact suggestions."""
        suggestions = [_make_suggestion(impact="medium")]
        result = suggest_experiments(suggestions)
        assert len(result) == 0

    def test_ignores_low_impact(self) -> None:
        """Should NOT generate experiments from LOW impact suggestions."""
        suggestions = [_make_suggestion(impact="low")]
        result = suggest_experiments(suggestions)
        assert len(result) == 0

    def test_max_one_experiment(self) -> None:
        """Should return at most 1 proposed experiment."""
        suggestions = [
            _make_suggestion(title="Protect focus window", impact="high"),
            _make_suggestion(title="Limit browsing", impact="high", intervention_type="limit"),
        ]
        result = suggest_experiments(suggestions)
        assert len(result) <= 1

    def test_empty_suggestions(self) -> None:
        """Empty suggestion list returns empty."""
        result = suggest_experiments([])
        assert result == []


class TestExperimentDedup:
    def test_skip_if_active_experiment_covers_intervention(self) -> None:
        """Don't suggest if an active experiment covers the same intervention type."""
        suggestions = [_make_suggestion(
            title="Protect focus window",
            impact="high",
            intervention_type="time_block",
        )]
        existing = [{"description": "some experiment", "intervention_type": "time_block"}]
        result = suggest_experiments(suggestions, existing_experiments=existing)
        assert len(result) == 0

    def test_skip_if_active_experiment_matches_title(self) -> None:
        """Don't suggest if an active experiment description contains the suggestion title."""
        suggestions = [_make_suggestion(
            title="Protect focus window",
            impact="high",
        )]
        existing = [{"description": "protect focus window experiment", "intervention_type": "other"}]
        result = suggest_experiments(suggestions, existing_experiments=existing)
        assert len(result) == 0

    def test_allow_if_no_overlap(self) -> None:
        """Allow experiment if no active experiment overlaps."""
        suggestions = [_make_suggestion(
            title="Protect focus window",
            impact="high",
            intervention_type="time_block",
        )]
        existing = [{"description": "limit browsing", "intervention_type": "limit"}]
        result = suggest_experiments(suggestions, existing_experiments=existing)
        assert len(result) == 1

    def test_no_existing_experiments(self) -> None:
        """With no existing experiments, should always propose."""
        suggestions = [_make_suggestion(impact="high")]
        result = suggest_experiments(suggestions, existing_experiments=None)
        assert len(result) == 1

    def test_falls_through_to_next_if_first_deduped(self) -> None:
        """If first HIGH suggestion is deduped, try the next one."""
        suggestions = [
            _make_suggestion(
                title="Protect focus window",
                impact="high",
                intervention_type="time_block",
            ),
            _make_suggestion(
                title="Limit browsing",
                impact="high",
                intervention_type="limit",
            ),
        ]
        existing = [{"description": "other", "intervention_type": "time_block"}]
        result = suggest_experiments(suggestions, existing_experiments=existing)
        assert len(result) == 1
        assert "Limit browsing" in result[0].source_suggestion_id


class TestProposedExperimentContent:
    def test_includes_predicted_delta(self) -> None:
        """Proposed experiment description should include the predicted score delta."""
        suggestions = [_make_suggestion(impact="high", score_delta=0.05)]
        result = suggest_experiments(suggestions)
        assert len(result) == 1
        assert "+5.0%" in result[0].description

    def test_source_suggestion_id_matches_title(self) -> None:
        """source_suggestion_id should reference the original suggestion title."""
        suggestions = [_make_suggestion(title="Protect focus window", impact="high")]
        result = suggest_experiments(suggestions)
        assert result[0].source_suggestion_id == "Protect focus window"

    def test_predicted_score_delta_stored(self) -> None:
        """predicted_score_delta should be set from the suggestion."""
        suggestions = [_make_suggestion(impact="high", score_delta=0.08)]
        result = suggest_experiments(suggestions)
        assert result[0].predicted_score_delta == 0.08
