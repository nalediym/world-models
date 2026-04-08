"""Tests for the Future Self dialogue system."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from life_world_model.goals.engine import DEFAULT_GOALS, load_goals
from life_world_model.simulation.future_self import (
    FutureSelfProfile,
    _derive_personality,
    _derive_future_personality,
    _project_achievements,
    _project_pattern_shifts,
    _project_struggles,
    build_conversation_prompt,
    build_future_self_from_data,
    build_future_self_system_prompt,
    build_opening_message,
    format_conversation_header,
    generate_future_self_response,
)
from life_world_model.types import Goal, LifeState, Pattern


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_state(
    hour: int,
    activity: str = "browsing",
    switches: int = 2,
    depth: int = 1,
    dwell: float = 300.0,
) -> LifeState:
    return LifeState(
        timestamp=datetime(2025, 6, 15, hour, 0),
        primary_activity=activity,
        secondary_activity=None,
        domain=None,
        event_count=5,
        confidence=0.8,
        context_switches=switches,
        session_depth=depth,
        dwell_seconds=dwell,
    )


def _day_of_states() -> list[LifeState]:
    """A representative day: coding 8-12, browsing 12-14, idle 14-16, coding 16-18."""
    states = []
    for h in range(8, 12):
        states.append(_make_state(h, "coding", switches=1, depth=3))
    for h in range(12, 14):
        states.append(_make_state(h, "browsing", switches=6, depth=0))
    for h in range(14, 16):
        states.append(_make_state(h, "idle", switches=0, depth=0))
    for h in range(16, 18):
        states.append(_make_state(h, "coding", switches=2, depth=2))
    return states


def _sample_patterns() -> list[Pattern]:
    return [
        Pattern(
            name="coding_at_9",
            category="routine",
            description="coding occurs at 9:00 on 80% of days",
            evidence={"hour": 9, "activity": "coding", "frequency": 0.8, "days_observed": 5},
            confidence=0.8,
            days_observed=5,
            first_seen=date(2025, 6, 10),
            last_seen=date(2025, 6, 15),
        ),
        Pattern(
            name="circadian_rhythm",
            category="rhythm",
            description="Peak focus hours: [9, 10, 11]. Most scattered hours: [13, 14, 15].",
            evidence={
                "peak_hours": [9, 10, 11],
                "scattered_hours": [13, 14, 15],
                "avg_switches_by_hour": {"9": 1.0, "13": 5.5},
                "avg_dwell_by_hour": {"9": 600.0, "13": 120.0},
            },
            confidence=0.7,
            days_observed=5,
            first_seen=date(2025, 6, 10),
            last_seen=date(2025, 6, 15),
        ),
        Pattern(
            name="context_switching_recovery",
            category="trigger",
            description="After high context switching, takes 3.0 buckets (45 min) to regain focus.",
            evidence={
                "avg_recovery_buckets": 3.0,
                "avg_recovery_minutes": 45.0,
                "sample_size": 8,
            },
            confidence=0.4,
            days_observed=5,
            first_seen=date(2025, 6, 10),
            last_seen=date(2025, 6, 15),
        ),
        Pattern(
            name="time_sink_browsing",
            category="time_sink",
            description="browsing: 2.5h total, avg dwell 120s, avg switches 5.5",
            evidence={
                "activity": "browsing",
                "total_hours": 2.5,
                "avg_dwell": 120.0,
                "avg_switches": 5.5,
                "score": 0.115,
            },
            confidence=0.5,
            days_observed=5,
            first_seen=date(2025, 6, 10),
            last_seen=date(2025, 6, 15),
        ),
    ]


def _sample_profile() -> FutureSelfProfile:
    return FutureSelfProfile(
        intervention="Code 8-10am before email",
        duration_description="6 months of Code 8-10am before email",
        projected_patterns=[
            "Peak focus hours ([9, 10, 11]) became even more productive",
            "Context-switch recovery dropped from 45min to ~32min",
        ],
        projected_scores={
            "goal_alignment": 0.72,
            "energy": 0.65,
            "flow": 0.81,
        },
        personality_traits=["focused, with better attention control", "structured, routine-driven"],
        achievements=[
            "Focus time went from 3.8h/day to ~4.5h/day",
            "Day score improved from 52% to ~71%",
            "Shipped 2 major features with the extra focus time",
        ],
        struggles=[
            "The first two weeks were the hardest — old habits kept pulling back",
            "The guilt of not responding immediately was real",
            "The afternoon slump didn't disappear — it just moved later",
        ],
        voice_style="warm, grounded, slightly proud",
        baseline_score=0.52,
        simulated_score=0.62,
    )


# ---------------------------------------------------------------------------
# Profile creation tests
# ---------------------------------------------------------------------------


class TestFutureSelfProfile:
    def test_profile_dataclass(self):
        profile = _sample_profile()
        assert profile.intervention == "Code 8-10am before email"
        assert profile.baseline_score == 0.52
        assert profile.simulated_score == 0.62
        assert len(profile.achievements) == 3
        assert len(profile.struggles) == 3

    def test_profile_has_projected_scores(self):
        profile = _sample_profile()
        assert "goal_alignment" in profile.projected_scores
        assert 0 <= profile.projected_scores["goal_alignment"] <= 1

    def test_profile_has_personality_traits(self):
        profile = _sample_profile()
        assert len(profile.personality_traits) >= 1
        assert isinstance(profile.personality_traits[0], str)


# ---------------------------------------------------------------------------
# Personality derivation tests
# ---------------------------------------------------------------------------


class TestDerivePersonality:
    def test_high_focus_yields_disciplined(self):
        # 8 of 10 states are coding -> >50% focus
        states = []
        for h in range(8, 16):
            states.append(_make_state(h, "coding", switches=1, depth=3))
        for h in range(16, 18):
            states.append(_make_state(h, "browsing", switches=5, depth=0))
        traits = _derive_personality(states, [])
        assert any("disciplined" in t for t in traits)

    def test_low_focus_yields_exploratory(self):
        states = []
        for h in range(8, 18):
            states.append(_make_state(h, "browsing", switches=6, depth=0))
        traits = _derive_personality(states, [])
        assert any("exploratory" in t or "pulled" in t for t in traits)

    def test_high_switches_yields_restless(self):
        states = [_make_state(h, "browsing", switches=8) for h in range(8, 18)]
        traits = _derive_personality(states, [])
        assert any("restless" in t or "juggling" in t for t in traits)

    def test_deep_sessions_yields_flow(self):
        states = [_make_state(h, "coding", depth=3) for h in range(8, 18)]
        traits = _derive_personality(states, [])
        assert any("flow" in t or "deep" in t for t in traits)

    def test_routine_patterns_yield_structured(self):
        patterns = _sample_patterns()
        # Add more routine patterns to hit threshold
        extra_routines = [
            Pattern(
                name="browsing_at_12",
                category="routine",
                description="browsing at 12",
                evidence={"hour": 12, "activity": "browsing", "frequency": 0.7},
                confidence=0.7,
                days_observed=5,
            ),
            Pattern(
                name="idle_at_14",
                category="routine",
                description="idle at 14",
                evidence={"hour": 14, "activity": "idle", "frequency": 0.8},
                confidence=0.8,
                days_observed=5,
            ),
        ]
        all_patterns = patterns + extra_routines
        states = _day_of_states()
        traits = _derive_personality(states, all_patterns)
        assert any("structured" in t or "routine" in t for t in traits)

    def test_late_night_yields_night_owl(self):
        states = [_make_state(h % 24, "coding") for h in range(22, 26)]
        # Hours 22, 23, 0, 1
        traits = _derive_personality(states, [])
        assert any("night" in t for t in traits)

    def test_empty_states_yields_sparse(self):
        traits = _derive_personality([], [])
        assert any("sparse" in t for t in traits)


class TestDeriveFuturePersonality:
    def test_restless_becomes_focused(self):
        current = ["curious, restless — always juggling"]
        future = _derive_future_personality(current, "code from 8-10am", 6)
        assert any("focused" in t or "channeled" in t for t in future)

    def test_night_owl_becomes_morning_person(self):
        current = ["night owl"]
        future = _derive_future_personality(current, "code from 8-10am", 6)
        assert any("morning" in t for t in future)

    def test_night_owl_stays_if_unrelated(self):
        current = ["night owl"]
        future = _derive_future_personality(current, "limit browsing to 1hr", 6)
        assert any("night owl" in t for t in future)

    def test_routine_resistant_evolves(self):
        current = ["spontaneous, routine-resistant"]
        future = _derive_future_personality(current, "code from 8-10am", 6)
        assert any("consistency" in t or "effective" in t for t in future)


# ---------------------------------------------------------------------------
# build_future_self_from_data tests
# ---------------------------------------------------------------------------


class TestBuildFutureSelf:
    def test_builds_profile_from_data(self):
        states = _day_of_states()
        patterns = _sample_patterns()
        goals = load_goals()
        profile = build_future_self_from_data(
            states, patterns, goals, "code from 8-10am", months_ahead=6
        )
        assert isinstance(profile, FutureSelfProfile)
        assert profile.intervention == "code from 8-10am"
        assert "6 months" in profile.duration_description

    def test_includes_actual_numbers(self):
        states = _day_of_states()
        patterns = _sample_patterns()
        goals = load_goals()
        profile = build_future_self_from_data(
            states, patterns, goals, "code from 8-10am", months_ahead=6
        )
        # Projected scores should contain actual goal names
        assert "goal_alignment" in profile.projected_scores or len(profile.projected_scores) > 0
        # Scores should be numeric
        for score in profile.projected_scores.values():
            assert isinstance(score, float)
            assert 0 <= score <= 1

    def test_includes_personality_traits(self):
        states = _day_of_states()
        patterns = _sample_patterns()
        goals = load_goals()
        profile = build_future_self_from_data(
            states, patterns, goals, "code from 8-10am", months_ahead=6
        )
        assert len(profile.personality_traits) >= 1

    def test_includes_realistic_struggles(self):
        states = _day_of_states()
        patterns = _sample_patterns()
        goals = load_goals()
        profile = build_future_self_from_data(
            states, patterns, goals, "code from 8-10am before email", months_ahead=6
        )
        assert len(profile.struggles) >= 2
        # Should include the universal early struggle
        assert any("first two weeks" in s.lower() or "hardest" in s.lower() for s in profile.struggles)
        # Should include email-specific struggle
        assert any("guilt" in s.lower() or "responding" in s.lower() for s in profile.struggles)

    def test_not_all_positive(self):
        """Profile should include struggles, not just utopian projection."""
        states = _day_of_states()
        patterns = _sample_patterns()
        goals = load_goals()
        profile = build_future_self_from_data(
            states, patterns, goals, "stop browsing after 9pm", months_ahead=6
        )
        assert len(profile.struggles) >= 2
        assert len(profile.achievements) >= 1

    def test_months_ahead_affects_duration(self):
        states = _day_of_states()
        profile = build_future_self_from_data(
            states, [], load_goals(), "code from 8-10am", months_ahead=3
        )
        assert "3 months" in profile.duration_description

    def test_empty_states_still_works(self):
        profile = build_future_self_from_data(
            [], [], load_goals(), "code from 8-10am", months_ahead=6
        )
        assert isinstance(profile, FutureSelfProfile)
        assert profile.baseline_score == 0.0

    def test_pattern_shifts_included(self):
        states = _day_of_states()
        patterns = _sample_patterns()
        goals = load_goals()
        profile = build_future_self_from_data(
            states, patterns, goals, "limit browsing to 1hr", months_ahead=6
        )
        assert len(profile.projected_patterns) >= 1


# ---------------------------------------------------------------------------
# System prompt tests
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt:
    def test_includes_intervention(self):
        profile = _sample_profile()
        prompt = build_future_self_system_prompt(profile)
        assert "Code 8-10am before email" in prompt

    def test_includes_data_grounding(self):
        profile = _sample_profile()
        prompt = build_future_self_system_prompt(profile)
        # Should contain actual numbers
        assert "52%" in prompt or "62%" in prompt
        assert "goal_alignment" in prompt

    def test_includes_anti_hallucination(self):
        profile = _sample_profile()
        prompt = build_future_self_system_prompt(profile)
        assert "Do not invent" in prompt or "not invent" in prompt.lower()

    def test_speaks_from_experience_not_advice(self):
        profile = _sample_profile()
        prompt = build_future_self_system_prompt(profile)
        assert "personal experience" in prompt.lower() or "I did" in prompt

    def test_includes_struggles(self):
        profile = _sample_profile()
        prompt = build_future_self_system_prompt(profile)
        assert "Struggles" in prompt
        assert "first two weeks" in prompt.lower()

    def test_includes_achievements(self):
        profile = _sample_profile()
        prompt = build_future_self_system_prompt(profile)
        assert "Achievements" in prompt
        assert "focus time" in prompt.lower() or "Focus time" in prompt

    def test_includes_personality(self):
        profile = _sample_profile()
        prompt = build_future_self_system_prompt(profile)
        assert "focused" in prompt.lower()

    def test_includes_voice_instruction(self):
        profile = _sample_profile()
        prompt = build_future_self_system_prompt(profile)
        assert profile.voice_style in prompt


# ---------------------------------------------------------------------------
# Conversation prompt tests
# ---------------------------------------------------------------------------


class TestBuildConversationPrompt:
    def test_includes_user_message(self):
        profile = _sample_profile()
        prompt = build_conversation_prompt(profile, "What was the hardest part?", [])
        assert "What was the hardest part?" in prompt

    def test_maintains_history(self):
        profile = _sample_profile()
        history = [
            ("user", "How did it start?"),
            ("assistant", "It was rough at first."),
        ]
        prompt = build_conversation_prompt(profile, "Tell me more", history)
        assert "How did it start?" in prompt
        assert "It was rough at first." in prompt
        assert "Tell me more" in prompt

    def test_empty_history_works(self):
        profile = _sample_profile()
        prompt = build_conversation_prompt(profile, "Hello future me!", [])
        assert "Hello future me!" in prompt
        assert "Previous conversation" not in prompt

    def test_labels_roles(self):
        profile = _sample_profile()
        history = [
            ("user", "Question?"),
            ("assistant", "Answer."),
        ]
        prompt = build_conversation_prompt(profile, "Follow up", history)
        assert "Past You" in prompt
        assert "Future You" in prompt


# ---------------------------------------------------------------------------
# Opening message tests
# ---------------------------------------------------------------------------


class TestBuildOpeningMessage:
    def test_opening_mentions_intervention(self):
        profile = _sample_profile()
        msg = build_opening_message(profile)
        assert "6 months" in msg

    def test_opening_includes_score_change(self):
        profile = _sample_profile()
        msg = build_opening_message(profile)
        assert "52%" in msg or "62%" in msg

    def test_opening_includes_achievement(self):
        profile = _sample_profile()
        msg = build_opening_message(profile)
        assert "Focus time" in msg or profile.achievements[0] in msg

    def test_opening_includes_struggle(self):
        profile = _sample_profile()
        msg = build_opening_message(profile)
        assert "smooth" in msg.lower() or "hardest" in msg.lower() or "habits" in msg.lower()


# ---------------------------------------------------------------------------
# Projection tests (achievements, struggles, pattern shifts)
# ---------------------------------------------------------------------------


class TestProjections:
    def test_achievements_include_numbers(self):
        states = _day_of_states()
        goals = load_goals()
        achievements = _project_achievements(
            states, goals, 0.4, 0.6, "code from 8-10am", 6
        )
        # At least one achievement should have numeric content
        has_number = any(
            any(c.isdigit() for c in a) for a in achievements
        )
        assert has_number

    def test_struggles_always_present(self):
        states = _day_of_states()
        struggles = _project_struggles(states, "code from 8-10am", 6)
        assert len(struggles) >= 2

    def test_struggles_include_universal(self):
        states = _day_of_states()
        struggles = _project_struggles(states, "anything", 1)
        assert any("first two weeks" in s.lower() for s in struggles)

    def test_email_struggle_for_email_intervention(self):
        states = _day_of_states()
        struggles = _project_struggles(states, "code before email", 6)
        assert any("guilt" in s.lower() or "responding" in s.lower() for s in struggles)

    def test_exercise_struggle_for_exercise_intervention(self):
        states = _day_of_states()
        struggles = _project_struggles(states, "add 30min exercise at 7am", 6)
        assert any("exercise" in s.lower() or "skipped" in s.lower() for s in struggles)

    def test_month3_struggle_for_long_projection(self):
        states = _day_of_states()
        struggles = _project_struggles(states, "code from 8-10am", 6)
        assert any("month 3" in s for s in struggles)

    def test_no_month3_for_short_projection(self):
        states = _day_of_states()
        struggles = _project_struggles(states, "code from 8-10am", 2)
        assert not any("month 3" in s for s in struggles)

    def test_pattern_shifts_with_time_sink(self):
        patterns = _sample_patterns()
        shifts = _project_pattern_shifts(patterns, "limit browsing to 1hr", 6)
        # Should mention browsing reduction or pattern shifts
        assert len(shifts) >= 1

    def test_pattern_shifts_with_rhythm(self):
        patterns = _sample_patterns()
        shifts = _project_pattern_shifts(patterns, "code from 8-10am", 6)
        assert any("focus" in s.lower() or "peak" in s.lower() for s in shifts)

    def test_pattern_shifts_empty_patterns(self):
        shifts = _project_pattern_shifts([], "code from 8-10am", 6)
        assert len(shifts) >= 1  # should still return a default message


# ---------------------------------------------------------------------------
# LLM fallback tests
# ---------------------------------------------------------------------------


class TestLLMFallback:
    def test_no_llm_returns_message(self):
        """Without LLM configured, generate_future_self_response returns fallback."""
        profile = _sample_profile()
        # Use a bare settings-like object without proper attributes
        response = generate_future_self_response(
            profile, "Hello?", [], settings=object()
        )
        assert "LLM not configured" in response

    def test_no_llm_with_none_settings(self):
        profile = _sample_profile()
        response = generate_future_self_response(
            profile, "Hello?", [], settings=None
        )
        assert "LLM not configured" in response

    @patch("life_world_model.simulation.future_self.shutil.which", return_value=None)
    def test_gemini_no_key_no_cli_returns_fallback(self, mock_which):
        """Gemini provider without API key or CLI returns fallback."""
        from life_world_model.config import Settings

        settings = Settings(llm_provider="gemini", gemini_api_key=None)
        profile = _sample_profile()
        response = generate_future_self_response(
            profile, "Hello?", [], settings=settings
        )
        assert "LLM not configured" in response


# ---------------------------------------------------------------------------
# Format tests
# ---------------------------------------------------------------------------


class TestFormatConversationHeader:
    def test_header_includes_intervention(self):
        profile = _sample_profile()
        header = format_conversation_header(profile)
        assert "Code 8-10am before email" in header

    def test_header_includes_scores(self):
        profile = _sample_profile()
        header = format_conversation_header(profile)
        assert "52%" in header
        assert "62%" in header

    def test_header_includes_duration(self):
        profile = _sample_profile()
        header = format_conversation_header(profile)
        assert "6 months" in header
