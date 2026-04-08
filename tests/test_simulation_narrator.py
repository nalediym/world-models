"""Tests for simulation narrator — side-by-side narrative generation."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from life_world_model.config import Settings
from life_world_model.pipeline.voices import get_voice
from life_world_model.simulation.narrator import (
    _build_baseline_summary,
    _fallback_comparison,
    _fallback_timeline,
    build_alternate_prompt,
    build_baseline_prompt,
    build_comparison_prompt,
    narrate_simulation,
    render_side_by_side,
)
from life_world_model.simulation.types import SimulationNarrative
from life_world_model.types import LifeState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(hour: int, activity: str = "browsing") -> LifeState:
    return LifeState(
        timestamp=datetime(2025, 6, 15, hour, 0),
        primary_activity=activity,
        secondary_activity=None,
        domain=None,
        event_count=5,
        confidence=0.8,
        context_switches=2,
        session_depth=1,
    )


def _day_of_states() -> list[LifeState]:
    """A representative day: coding 8-12, browsing 12-14, idle 14-16, coding 16-18."""
    states = []
    for h in range(8, 12):
        states.append(_make_state(h, "coding"))
    for h in range(12, 14):
        states.append(_make_state(h, "browsing"))
    for h in range(14, 16):
        states.append(_make_state(h, "idle"))
    for h in range(16, 18):
        states.append(_make_state(h, "coding"))
    return states


def _alternate_states() -> list[LifeState]:
    """Alternate day: coding 8-14, idle 14-16, coding 16-18."""
    states = []
    for h in range(8, 14):
        states.append(_make_state(h, "coding"))
    for h in range(14, 16):
        states.append(_make_state(h, "idle"))
    for h in range(16, 18):
        states.append(_make_state(h, "coding"))
    return states


# ---------------------------------------------------------------------------
# SimulationNarrative dataclass
# ---------------------------------------------------------------------------


class TestSimulationNarrative:
    def test_creation(self):
        narrative = SimulationNarrative(
            intervention="code from 8-10am",
            baseline_score=0.62,
            simulated_score=0.71,
            score_delta=0.09,
            baseline_narrative="The real day narrative.",
            simulated_narrative="The alternate day narrative.",
            voice="tolkien",
        )
        assert narrative.intervention == "code from 8-10am"
        assert narrative.baseline_score == 0.62
        assert narrative.simulated_score == 0.71
        assert narrative.score_delta == 0.09
        assert narrative.baseline_narrative == "The real day narrative."
        assert narrative.simulated_narrative == "The alternate day narrative."
        assert narrative.voice == "tolkien"
        assert narrative.comparison == ""  # default

    def test_creation_with_comparison(self):
        narrative = SimulationNarrative(
            intervention="stop browsing after 9pm",
            baseline_score=0.50,
            simulated_score=0.55,
            score_delta=0.05,
            baseline_narrative="Baseline prose.",
            simulated_narrative="Alternate prose.",
            voice="clinical",
            comparison="The alternate day is better because...",
        )
        assert narrative.comparison == "The alternate day is better because..."
        assert narrative.voice == "clinical"


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


class TestBuildBaselinePrompt:
    def test_includes_voice(self):
        states = _day_of_states()
        voice = get_voice("tolkien")
        prompt = build_baseline_prompt(states, date(2025, 6, 15), voice)
        assert "tolkien" in prompt

    def test_includes_date(self):
        states = _day_of_states()
        voice = get_voice("tolkien")
        prompt = build_baseline_prompt(states, date(2025, 6, 15), voice)
        assert "2025-06-15" in prompt

    def test_includes_ground_truth_warning(self):
        states = _day_of_states()
        voice = get_voice("tolkien")
        prompt = build_baseline_prompt(states, date(2025, 6, 15), voice)
        assert "ground truth" in prompt
        assert "Do not invent" in prompt

    def test_includes_day_as_it_happened(self):
        states = _day_of_states()
        voice = get_voice("tolkien")
        prompt = build_baseline_prompt(states, date(2025, 6, 15), voice)
        assert "day as it actually happened" in prompt

    def test_includes_timeline(self):
        states = _day_of_states()
        voice = get_voice("tolkien")
        prompt = build_baseline_prompt(states, date(2025, 6, 15), voice)
        assert "08:00" in prompt
        assert "coding" in prompt

    def test_empty_states(self):
        voice = get_voice("tolkien")
        prompt = build_baseline_prompt([], date(2025, 6, 15), voice)
        assert "Timeline:" in prompt


class TestBuildAlternatePrompt:
    def test_includes_intervention_text(self):
        states = _alternate_states()
        voice = get_voice("tolkien")
        prompt = build_alternate_prompt(
            states, date(2025, 6, 15), voice,
            "code from 8-10am", "Summary of real day."
        )
        assert "code from 8-10am" in prompt

    def test_includes_alternate_language(self):
        states = _alternate_states()
        voice = get_voice("tolkien")
        prompt = build_alternate_prompt(
            states, date(2025, 6, 15), voice,
            "code from 8-10am", "Summary of real day."
        )
        assert "ALTERNATE" in prompt or "alternate" in prompt.lower()
        assert "what if" in prompt.lower()

    def test_includes_contrast_instructions(self):
        states = _alternate_states()
        voice = get_voice("tolkien")
        prompt = build_alternate_prompt(
            states, date(2025, 6, 15), voice,
            "code from 8-10am", "Summary of real day."
        )
        assert "diverge" in prompt.lower()
        assert "In this version of the day" in prompt

    def test_includes_baseline_summary(self):
        states = _alternate_states()
        voice = get_voice("tolkien")
        baseline_summary = "coding 240min, browsing 120min"
        prompt = build_alternate_prompt(
            states, date(2025, 6, 15), voice,
            "code from 8-10am", baseline_summary
        )
        assert baseline_summary in prompt

    def test_includes_anti_hallucination(self):
        states = _alternate_states()
        voice = get_voice("tolkien")
        prompt = build_alternate_prompt(
            states, date(2025, 6, 15), voice,
            "code from 8-10am", "Summary."
        )
        assert "Do not invent" in prompt
        assert "ground truth" in prompt


class TestBuildComparisonPrompt:
    def test_includes_scores(self):
        voice = get_voice("tolkien")
        prompt = build_comparison_prompt("code from 8-10am", 0.62, 0.71, 0.09, voice)
        assert "62" in prompt
        assert "71" in prompt

    def test_positive_delta(self):
        voice = get_voice("tolkien")
        prompt = build_comparison_prompt("code from 8-10am", 0.62, 0.71, 0.09, voice)
        assert "higher" in prompt

    def test_negative_delta(self):
        voice = get_voice("tolkien")
        prompt = build_comparison_prompt("stop coding", 0.62, 0.50, -0.12, voice)
        assert "lower" in prompt

    def test_anti_hallucination(self):
        voice = get_voice("tolkien")
        prompt = build_comparison_prompt("code from 8-10am", 0.62, 0.71, 0.09, voice)
        assert "Do not hallucinate" in prompt


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


class TestRenderSideBySide:
    def test_includes_both_narratives(self):
        narrative = SimulationNarrative(
            intervention="code from 8-10am",
            baseline_score=0.62,
            simulated_score=0.71,
            score_delta=0.09,
            baseline_narrative="The real day was productive.",
            simulated_narrative="The alternate day was more productive.",
            voice="tolkien",
            comparison="The alternate scores higher due to focused coding.",
        )
        output = render_side_by_side(narrative)
        assert "The real day was productive." in output
        assert "The alternate day was more productive." in output

    def test_includes_scores(self):
        narrative = SimulationNarrative(
            intervention="code from 8-10am",
            baseline_score=0.62,
            simulated_score=0.71,
            score_delta=0.09,
            baseline_narrative="Baseline.",
            simulated_narrative="Alternate.",
            voice="tolkien",
        )
        output = render_side_by_side(narrative)
        assert "62%" in output
        assert "71%" in output
        assert "+9%" in output

    def test_includes_headers(self):
        narrative = SimulationNarrative(
            intervention="code from 8-10am",
            baseline_score=0.62,
            simulated_score=0.71,
            score_delta=0.09,
            baseline_narrative="Baseline.",
            simulated_narrative="Alternate.",
            voice="tolkien",
        )
        output = render_side_by_side(narrative)
        assert "THE DAY THAT WAS" in output
        assert "THE DAY THAT COULD HAVE BEEN" in output
        assert "DELTA" in output

    def test_includes_intervention_text(self):
        narrative = SimulationNarrative(
            intervention="stop browsing after 9pm",
            baseline_score=0.50,
            simulated_score=0.55,
            score_delta=0.05,
            baseline_narrative="Baseline.",
            simulated_narrative="Alternate.",
            voice="tolkien",
        )
        output = render_side_by_side(narrative)
        assert "stop browsing after 9pm" in output

    def test_includes_comparison(self):
        narrative = SimulationNarrative(
            intervention="code from 8-10am",
            baseline_score=0.62,
            simulated_score=0.71,
            score_delta=0.09,
            baseline_narrative="Baseline.",
            simulated_narrative="Alternate.",
            voice="tolkien",
            comparison="Alternate scores higher due to deep work.",
        )
        output = render_side_by_side(narrative)
        assert "Alternate scores higher due to deep work." in output

    def test_negative_delta(self):
        narrative = SimulationNarrative(
            intervention="stop coding",
            baseline_score=0.62,
            simulated_score=0.50,
            score_delta=-0.12,
            baseline_narrative="Baseline.",
            simulated_narrative="Alternate.",
            voice="tolkien",
        )
        output = render_side_by_side(narrative)
        assert "-12%" in output

    def test_simulation_header(self):
        narrative = SimulationNarrative(
            intervention="test",
            baseline_score=0.5,
            simulated_score=0.5,
            score_delta=0.0,
            baseline_narrative="B.",
            simulated_narrative="A.",
            voice="tolkien",
        )
        output = render_side_by_side(narrative)
        assert "LIFE WORLD MODEL" in output
        assert "SIMULATION" in output


# ---------------------------------------------------------------------------
# narrate_simulation with mocked LLM
# ---------------------------------------------------------------------------


class TestNarrateSimulation:
    def test_with_mocked_llm(self):
        """Mocked _generate_prose returns both narratives."""
        states = _day_of_states()
        alt = _alternate_states()

        with patch(
            "life_world_model.simulation.narrator._generate_prose"
        ) as mock_gen:
            mock_gen.side_effect = [
                "The real day unfolded...",
                "In the alternate world...",
                "The alternate scores higher.",
            ]
            narrative = narrate_simulation(
                baseline_states=states,
                simulated_states=alt,
                intervention_text="code from 8-10am",
                target_date=date(2025, 6, 15),
                settings=Settings(),
                baseline_score=0.62,
                simulated_score=0.71,
            )

        assert narrative.baseline_narrative == "The real day unfolded..."
        assert narrative.simulated_narrative == "In the alternate world..."
        assert narrative.comparison == "The alternate scores higher."
        assert narrative.voice == "tolkien"
        assert narrative.score_delta == pytest.approx(0.09)
        assert narrative.intervention == "code from 8-10am"

    def test_with_custom_voice(self):
        states = _day_of_states()
        alt = _alternate_states()

        with patch(
            "life_world_model.simulation.narrator._generate_prose"
        ) as mock_gen:
            mock_gen.side_effect = ["B.", "A.", "C."]
            narrative = narrate_simulation(
                baseline_states=states,
                simulated_states=alt,
                intervention_text="stop browsing",
                target_date=date(2025, 6, 15),
                settings=Settings(),
                baseline_score=0.50,
                simulated_score=0.55,
                voice_name="clinical",
            )

        assert narrative.voice == "clinical"

    def test_fallback_when_no_llm(self):
        """When _generate_prose returns None, falls back to timeline text."""
        states = _day_of_states()
        alt = _alternate_states()

        with patch(
            "life_world_model.simulation.narrator._generate_prose"
        ) as mock_gen:
            mock_gen.return_value = None
            narrative = narrate_simulation(
                baseline_states=states,
                simulated_states=alt,
                intervention_text="code from 8-10am",
                target_date=date(2025, 6, 15),
                settings=Settings(),
                baseline_score=0.62,
                simulated_score=0.71,
            )

        # Fallback should contain timeline data
        assert "08:00" in narrative.baseline_narrative
        assert "coding" in narrative.baseline_narrative
        assert "08:00" in narrative.simulated_narrative
        # Comparison should be a simple text fallback
        assert "code from 8-10am" in narrative.comparison

    def test_empty_states(self):
        """Handles empty states gracefully."""
        with patch(
            "life_world_model.simulation.narrator._generate_prose"
        ) as mock_gen:
            mock_gen.return_value = None
            narrative = narrate_simulation(
                baseline_states=[],
                simulated_states=[],
                intervention_text="code from 8-10am",
                target_date=date(2025, 6, 15),
                settings=Settings(),
                baseline_score=0.0,
                simulated_score=0.0,
            )

        assert narrative.baseline_narrative == "(no data)"
        assert narrative.simulated_narrative == "(no data)"


# ---------------------------------------------------------------------------
# Fallback helpers
# ---------------------------------------------------------------------------


class TestFallbackHelpers:
    def test_fallback_timeline(self):
        states = [_make_state(9, "coding"), _make_state(10, "browsing")]
        result = _fallback_timeline(states)
        assert "09:00" in result
        assert "10:00" in result
        assert "coding" in result
        assert "browsing" in result

    def test_fallback_timeline_empty(self):
        assert _fallback_timeline([]) == "(no data)"

    def test_fallback_comparison_positive(self):
        result = _fallback_comparison("code from 8-10am", 0.62, 0.71, 0.09)
        assert "higher" in result
        assert "9.0%" in result

    def test_fallback_comparison_negative(self):
        result = _fallback_comparison("stop coding", 0.62, 0.50, -0.12)
        assert "lower" in result
        assert "12.0%" in result


# ---------------------------------------------------------------------------
# Baseline summary helper
# ---------------------------------------------------------------------------


class TestBaselineSummary:
    def test_summary_includes_activities(self):
        states = _day_of_states()
        summary = _build_baseline_summary(states)
        assert "coding" in summary
        assert "browsing" in summary
        assert "idle" in summary

    def test_summary_includes_time_range(self):
        states = _day_of_states()
        summary = _build_baseline_summary(states)
        assert "08:00" in summary
        assert "17:00" in summary

    def test_summary_empty_states(self):
        summary = _build_baseline_summary([])
        assert "No data" in summary


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCLIIntegration:
    def test_narrate_flag_parsed(self):
        from life_world_model.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["simulate", "code from 8-10am", "--narrate"])
        assert args.narrate is True
        assert args.scenario == "code from 8-10am"

    def test_narrate_flag_default_false(self):
        from life_world_model.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["simulate", "code from 8-10am"])
        assert args.narrate is False

    def test_voice_flag_parsed(self):
        from life_world_model.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(
            ["simulate", "code from 8-10am", "--narrate", "--voice", "clinical"]
        )
        assert args.voice == "clinical"
        assert args.narrate is True

    def test_voice_flag_default_none(self):
        from life_world_model.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["simulate", "code from 8-10am"])
        assert args.voice is None

    def test_backwards_compatible(self):
        """Without --narrate, run_simulate just prints summary."""
        from life_world_model.cli import run_simulate

        with patch("life_world_model.cli.simulate") as mock_sim, \
             patch("life_world_model.cli.load_settings") as mock_settings, \
             patch("life_world_model.cli.SQLiteStore"):
            mock_settings.return_value = Settings()
            mock_result = MagicMock()
            mock_result.summary = "Intervention: test\nBaseline: 50%"
            mock_sim.return_value = mock_result
            ret = run_simulate("code from 8-10am")
            assert ret == 0
