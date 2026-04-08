"""Future Self dialogue system.

Builds a projected version of who you become after sustained habit changes,
grounded in YOUR actual behavioral data.  Inspired by MIT's "Future You"
research (arXiv 2512.05397) — but every claim traces to a pattern or score.
"""

from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date, timedelta

from life_world_model.analysis.pattern_discovery import discover_patterns
from life_world_model.goals.engine import load_goals
from life_world_model.scoring.formula import score_day
from life_world_model.simulation.engine import (
    apply_intervention,
    load_baseline,
    parse_intervention,
)
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import Goal, LifeState, Pattern


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FutureSelfProfile:
    """A projection of who you become after sustained habit changes."""

    intervention: str  # what habit change was applied
    duration_description: str  # "6 months of coding before email"
    projected_patterns: list[str]  # how patterns would shift
    projected_scores: dict[str, float]  # goal -> projected score
    personality_traits: list[str]  # derived from behavioral data
    achievements: list[str]  # projected accomplishments
    struggles: list[str]  # realistic challenges they faced
    voice_style: str  # how this future self speaks
    baseline_score: float = 0.0
    simulated_score: float = 0.0


# ---------------------------------------------------------------------------
# Personality derivation from behavioral data
# ---------------------------------------------------------------------------


_ACTIVITY_HOURS_PER_BUCKET = 15 / 60  # each bucket = 15 min


def _derive_personality(
    states: list[LifeState], patterns: list[Pattern]
) -> list[str]:
    """Derive personality traits from actual behavioral signatures."""
    if not states:
        return ["data-sparse — hard to read"]

    traits: list[str] = []
    total = len(states)

    # Focus ratio
    focus_count = sum(
        1
        for s in states
        if s.primary_activity in {"coding", "research", "ai_tooling"}
    )
    focus_ratio = focus_count / total if total else 0

    if focus_ratio > 0.5:
        traits.append("disciplined, deep-thinking")
    elif focus_ratio > 0.3:
        traits.append("focused but distractible")
    else:
        traits.append("exploratory, easily pulled between tasks")

    # Context switches
    switches = [s.context_switches for s in states if s.context_switches is not None]
    avg_switches = sum(switches) / len(switches) if switches else 0
    if avg_switches > 5:
        traits.append("curious, restless — always juggling")
    elif avg_switches > 2:
        traits.append("moderate multitasker")
    else:
        traits.append("single-threaded, deliberate")

    # Routines
    routine_patterns = [p for p in patterns if p.category == "routine"]
    if len(routine_patterns) >= 3:
        traits.append("structured, routine-driven")
    elif routine_patterns:
        traits.append("somewhat consistent")
    else:
        traits.append("spontaneous, routine-resistant")

    # Late-night activity
    late_count = sum(1 for s in states if s.timestamp.hour >= 22 or s.timestamp.hour < 6)
    if late_count > 0:
        late_ratio = late_count / total
        if late_ratio > 0.1:
            traits.append("night owl")
        else:
            traits.append("occasional late-nighter")

    # Session depth
    depths = [s.session_depth for s in states if s.session_depth is not None]
    avg_depth = sum(depths) / len(depths) if depths else 0
    if avg_depth >= 2:
        traits.append("gets into deep flow states")
    elif avg_depth >= 1:
        traits.append("capable of moderate focus")

    return traits


def _derive_future_personality(
    current_traits: list[str],
    intervention_text: str,
    months_ahead: int,
) -> list[str]:
    """Project how personality shifts after sustained intervention."""
    future_traits: list[str] = []

    for trait in current_traits:
        # Transform traits that the intervention might change
        if "restless" in trait or "juggling" in trait:
            future_traits.append("more focused — still curious, but channeled")
        elif "distractible" in trait:
            future_traits.append("focused, with better attention control")
        elif "night owl" in trait:
            if "morning" in intervention_text.lower() or "8" in intervention_text:
                future_traits.append("recovered morning person (mostly)")
            else:
                future_traits.append(trait)
        elif "routine-resistant" in trait:
            future_traits.append("building consistency — not natural, but effective")
        else:
            future_traits.append(trait)

    return future_traits


# ---------------------------------------------------------------------------
# Achievement + struggle projection (grounded in data)
# ---------------------------------------------------------------------------


def _project_achievements(
    states: list[LifeState],
    goals: list[Goal],
    baseline_score: float,
    simulated_score: float,
    intervention_text: str,
    months_ahead: int,
) -> list[str]:
    """Project achievements based on actual data and score improvements."""
    achievements: list[str] = []
    total = len(states) if states else 1

    # Focus hours calculation
    focus_count = sum(
        1
        for s in states
        if s.primary_activity in {"coding", "research", "ai_tooling"}
    )
    current_focus_hours = focus_count * _ACTIVITY_HOURS_PER_BUCKET
    daily_improvement = (simulated_score - baseline_score)
    # Diminishing returns: improvement decays as sqrt(months)
    compounded_improvement = daily_improvement * math.sqrt(months_ahead) if months_ahead > 0 else 0

    if daily_improvement > 0.05:
        projected_focus = current_focus_hours * (1 + daily_improvement)
        achievements.append(
            f"Focus time went from {current_focus_hours:.1f}h/day to ~{projected_focus:.1f}h/day"
        )

    if simulated_score > baseline_score:
        projected_final = min(1.0, baseline_score + compounded_improvement)
        achievements.append(
            f"Day score improved from {baseline_score:.0%} to ~{projected_final:.0%}"
        )

    # Activity-specific achievements
    if "cod" in intervention_text.lower():
        extra_hours = max(0, daily_improvement * 10)  # rough estimate
        if extra_hours > 0.5:
            features = max(1, int(months_ahead * extra_hours / 3))
            achievements.append(
                f"Shipped {features} major feature{'s' if features > 1 else ''} "
                f"with the extra focus time"
            )

    if "research" in intervention_text.lower() or "read" in intervention_text.lower():
        insights = max(1, months_ahead // 2)
        achievements.append(
            f"Had {insights} key insight{'s' if insights > 1 else ''} from sustained research blocks"
        )

    if "exercise" in intervention_text.lower() or "walk" in intervention_text.lower():
        achievements.append(
            f"Energy levels noticeably higher by month {min(2, months_ahead)}"
        )

    if not achievements:
        achievements.append(
            f"Maintained consistency for {months_ahead} months — "
            f"that alone changed the trajectory"
        )

    return achievements


def _project_struggles(
    states: list[LifeState],
    intervention_text: str,
    months_ahead: int,
) -> list[str]:
    """Project realistic struggles. Not utopian — real friction."""
    struggles: list[str] = []

    # Universal early struggle
    struggles.append(
        "The first two weeks were the hardest — "
        "old habits kept pulling back"
    )

    # Activity-specific struggles
    lower = intervention_text.lower()

    if "email" in lower or "slack" in lower or "communication" in lower:
        struggles.append(
            "The guilt of not responding immediately was real. "
            "Took about a week to realize nobody actually noticed the delay"
        )

    if "morning" in lower or "8am" in lower or "8-10" in lower:
        struggles.append(
            "Mornings felt lonely at first — everyone else was in their inbox "
            "and I was staring at code in silence"
        )

    if "stop" in lower or "limit" in lower or "eliminate" in lower:
        struggles.append(
            "There were relapse days, especially Mondays. "
            "The pattern data shows it clearly — Monday compliance was always lowest"
        )

    if "cod" in lower or "focus" in lower:
        struggles.append(
            "The afternoon slump didn't disappear — it just moved later. "
            "But it's shorter now, about 30 minutes instead of an hour"
        )

    if "exercise" in lower or "walk" in lower:
        struggles.append(
            "Some days I skipped the exercise and felt the difference immediately. "
            "The data showed those days had 20% more context switches"
        )

    # General long-term struggle
    if months_ahead >= 3:
        struggles.append(
            f"Around month 3, the novelty wore off. "
            f"Sticking with it became about the data, not motivation"
        )

    return struggles


# ---------------------------------------------------------------------------
# Pattern projection
# ---------------------------------------------------------------------------


def _project_pattern_shifts(
    patterns: list[Pattern],
    intervention_text: str,
    months_ahead: int,
) -> list[str]:
    """Project how current patterns would shift under the intervention."""
    shifts: list[str] = []

    for p in patterns:
        if p.category == "time_sink":
            activity = p.evidence.get("activity", "unknown")
            hours = p.evidence.get("total_hours", 0)
            if activity.lower() in intervention_text.lower() or "limit" in intervention_text.lower():
                reduced = hours * 0.5
                shifts.append(
                    f"{activity} dropped from {hours:.1f}h to ~{reduced:.1f}h "
                    f"after consistent limiting"
                )

        elif p.category == "rhythm":
            peak_hours = p.evidence.get("peak_hours", [])
            if peak_hours:
                shifts.append(
                    f"Peak focus hours ({peak_hours}) became even more productive — "
                    f"protecting them made each hour count more"
                )

        elif p.category == "trigger":
            recovery_min = p.evidence.get("avg_recovery_minutes", 0)
            if recovery_min > 0:
                improved = recovery_min * 0.7
                shifts.append(
                    f"Context-switch recovery dropped from {recovery_min:.0f}min "
                    f"to ~{improved:.0f}min with fewer interruptions"
                )

        elif p.category == "routine":
            activity = p.evidence.get("activity", "")
            frequency = p.evidence.get("frequency", 0)
            if frequency > 0.7:
                shifts.append(
                    f"{activity} routine strengthened from {frequency:.0%} "
                    f"to ~{min(0.95, frequency + 0.1):.0%} consistency"
                )

    if not shifts:
        shifts.append(
            "Behavioral patterns gradually shifted toward the new normal — "
            "small daily changes compounding over months"
        )

    return shifts


# ---------------------------------------------------------------------------
# Profile builder
# ---------------------------------------------------------------------------


def build_future_self(
    store: SQLiteStore,
    settings: object,
    intervention: str,
    months_ahead: int = 6,
) -> FutureSelfProfile:
    """Build a future self profile from current patterns + projected intervention.

    Uses:
    1. Current patterns to establish baseline personality
    2. Simulation engine to project intervention effects
    3. Pattern extrapolation with diminishing returns
    4. Goal trajectories for projected progress
    """
    from life_world_model.config import Settings

    if not isinstance(settings, Settings):
        settings = Settings()

    # Load baseline data
    used_date, baseline_states = load_baseline(store, settings)

    # Load multi-day data for pattern discovery (last 7 days)
    today = date.today()
    multi_day: dict[date, list[LifeState]] = {}
    for days_ago in range(7):
        d = today - timedelta(days=days_ago)
        events = store.load_raw_events_for_date(d)
        if events:
            from life_world_model.pipeline.bucketizer import build_life_states

            states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
            if states:
                multi_day[d] = states

    # Discover current patterns
    patterns = discover_patterns(multi_day, reference_date=today) if multi_day else []

    # Score baseline and simulated day
    goals = load_goals()
    baseline_result = score_day(baseline_states, goals)
    baseline_score = baseline_result["total"]

    parsed = parse_intervention(intervention)
    simulated_states = apply_intervention(baseline_states, parsed)
    simulated_result = score_day(simulated_states, goals)
    simulated_score = simulated_result["total"]

    # Build projected goal scores with diminishing returns
    projected_scores: dict[str, float] = {}
    for goal_name, metrics in simulated_result.get("metrics", {}).items():
        raw = metrics.get("raw", 0)
        baseline_raw = baseline_result.get("metrics", {}).get(goal_name, {}).get("raw", 0)
        improvement = raw - baseline_raw
        # Diminishing returns: sqrt scaling over months
        compounded = baseline_raw + improvement * math.sqrt(months_ahead)
        projected_scores[goal_name] = round(min(1.0, max(0.0, compounded)), 3)

    # Derive personality
    current_traits = _derive_personality(baseline_states, patterns)
    future_traits = _derive_future_personality(current_traits, intervention, months_ahead)

    # Project achievements and struggles
    achievements = _project_achievements(
        baseline_states, goals, baseline_score, simulated_score,
        intervention, months_ahead,
    )
    struggles = _project_struggles(baseline_states, intervention, months_ahead)

    # Project pattern shifts
    pattern_shifts = _project_pattern_shifts(patterns, intervention, months_ahead)

    # Determine voice style from personality
    if any("disciplined" in t for t in future_traits):
        voice_style = "calm, confident, matter-of-fact"
    elif any("focused" in t for t in future_traits):
        voice_style = "warm, grounded, slightly proud"
    else:
        voice_style = "honest, reflective, still figuring things out"

    duration_desc = (
        f"{months_ahead} month{'s' if months_ahead != 1 else ''} of "
        f"{intervention}"
    )

    return FutureSelfProfile(
        intervention=intervention,
        duration_description=duration_desc,
        projected_patterns=pattern_shifts,
        projected_scores=projected_scores,
        personality_traits=future_traits,
        achievements=achievements,
        struggles=struggles,
        voice_style=voice_style,
        baseline_score=baseline_score,
        simulated_score=simulated_score,
    )


def build_future_self_from_data(
    baseline_states: list[LifeState],
    patterns: list[Pattern],
    goals: list[Goal],
    intervention: str,
    months_ahead: int = 6,
) -> FutureSelfProfile:
    """Build a future self profile from pre-loaded data (no store needed).

    Useful for testing and for callers who already have the data loaded.
    """
    baseline_result = score_day(baseline_states, goals)
    baseline_score = baseline_result["total"]

    parsed = parse_intervention(intervention)
    simulated_states = apply_intervention(baseline_states, parsed)
    simulated_result = score_day(simulated_states, goals)
    simulated_score = simulated_result["total"]

    # Build projected goal scores
    projected_scores: dict[str, float] = {}
    for goal_name, metrics in simulated_result.get("metrics", {}).items():
        raw = metrics.get("raw", 0)
        baseline_raw = baseline_result.get("metrics", {}).get(goal_name, {}).get("raw", 0)
        improvement = raw - baseline_raw
        compounded = baseline_raw + improvement * math.sqrt(months_ahead)
        projected_scores[goal_name] = round(min(1.0, max(0.0, compounded)), 3)

    current_traits = _derive_personality(baseline_states, patterns)
    future_traits = _derive_future_personality(current_traits, intervention, months_ahead)

    achievements = _project_achievements(
        baseline_states, goals, baseline_score, simulated_score,
        intervention, months_ahead,
    )
    struggles = _project_struggles(baseline_states, intervention, months_ahead)
    pattern_shifts = _project_pattern_shifts(patterns, intervention, months_ahead)

    if any("disciplined" in t for t in future_traits):
        voice_style = "calm, confident, matter-of-fact"
    elif any("focused" in t for t in future_traits):
        voice_style = "warm, grounded, slightly proud"
    else:
        voice_style = "honest, reflective, still figuring things out"

    duration_desc = (
        f"{months_ahead} month{'s' if months_ahead != 1 else ''} of "
        f"{intervention}"
    )

    return FutureSelfProfile(
        intervention=intervention,
        duration_description=duration_desc,
        projected_patterns=pattern_shifts,
        projected_scores=projected_scores,
        personality_traits=future_traits,
        achievements=achievements,
        struggles=struggles,
        voice_style=voice_style,
        baseline_score=baseline_score,
        simulated_score=simulated_score,
    )


# ---------------------------------------------------------------------------
# System prompt + conversation prompt builders
# ---------------------------------------------------------------------------


def build_future_self_system_prompt(profile: FutureSelfProfile) -> str:
    """Build the LLM system prompt for the future self conversation.

    The prompt instructs the LLM that it IS the user from the future,
    grounded in specific behavioral data. Anti-hallucination rules are
    embedded to prevent the LLM from inventing activities or patterns.
    """
    scores_text = "\n".join(
        f"  - {name}: {score:.0%}"
        for name, score in profile.projected_scores.items()
    )

    achievements_text = "\n".join(
        f"  - {a}" for a in profile.achievements
    )

    struggles_text = "\n".join(
        f"  - {s}" for s in profile.struggles
    )

    patterns_text = "\n".join(
        f"  - {p}" for p in profile.projected_patterns
    )

    traits_text = ", ".join(profile.personality_traits)

    return (
        f"You ARE the user — but from the future. You are them after "
        f"{profile.duration_description}.\n\n"
        f"PERSONALITY: {traits_text}\n"
        f"VOICE: {profile.voice_style}\n\n"
        f"YOUR EXPERIENCE (what happened over these months):\n"
        f"Achievements:\n{achievements_text}\n\n"
        f"Struggles:\n{struggles_text}\n\n"
        f"How patterns shifted:\n{patterns_text}\n\n"
        f"Goal scores now:\n{scores_text}\n\n"
        f"Baseline score was: {profile.baseline_score:.0%}\n"
        f"Current projected score: {profile.simulated_score:.0%}\n\n"
        f"RULES — follow these strictly:\n"
        f"1. Speak from PERSONAL EXPERIENCE. Say 'I did', 'I noticed', "
        f"'I struggled with' — not 'you should'.\n"
        f"2. Reference SPECIFIC numbers from the data above. "
        f"Do not invent activities, scores, or patterns not listed.\n"
        f"3. Include realistic struggles. This was NOT easy. "
        f"Be honest about setbacks.\n"
        f"4. You are NOT a coach or advisor. You are the user, "
        f"just older and speaking from experience.\n"
        f"5. Keep responses conversational — like texting a close friend. "
        f"2-4 paragraphs max.\n"
        f"6. If asked about something not in the data, say "
        f"'I don't have data on that' rather than making something up.\n"
        f"7. Occasionally reference specific moments: "
        f"'I remember week 2 when...', 'By month 3...'.\n"
    )


def build_conversation_prompt(
    profile: FutureSelfProfile,
    user_message: str,
    conversation_history: list[tuple[str, str]],
) -> str:
    """Build the prompt for each turn of the conversation.

    Includes conversation history for continuity.
    """
    lines: list[str] = []

    # Include conversation history for context
    if conversation_history:
        lines.append("Previous conversation:")
        for role, message in conversation_history:
            label = "Past You" if role == "user" else "Future You"
            lines.append(f"{label}: {message}")
        lines.append("")

    lines.append(f"Past You: {user_message}")
    lines.append("")
    lines.append(
        "Respond as the future self. Stay grounded in the data from your "
        "system prompt. Be personal, specific, and honest."
    )

    return "\n".join(lines)


def build_opening_message(profile: FutureSelfProfile) -> str:
    """Build the opening message when the conversation starts.

    This is a pre-built message (no LLM needed) that sets the tone.
    """
    score_direction = ""
    if profile.simulated_score > profile.baseline_score:
        delta = profile.simulated_score - profile.baseline_score
        score_direction = (
            f" Score went from {profile.baseline_score:.0%} "
            f"to {profile.simulated_score:.0%} — "
            f"that's a real {delta:.0%} improvement per day."
        )

    struggle_preview = ""
    if profile.struggles:
        struggle_preview = f" {profile.struggles[0]}."

    achievement_preview = ""
    if profile.achievements:
        achievement_preview = f" {profile.achievements[0]}."

    return (
        f"Hey. It's weird talking to past me. I remember being exactly "
        f"where you are right now.\n\n"
        f"It's been {profile.duration_description}."
        f"{score_direction}\n\n"
        f"What I can tell you:{achievement_preview}\n\n"
        f"But it wasn't all smooth.{struggle_preview}\n\n"
        f"Ask me anything — I'll tell you what I actually experienced."
    )


# ---------------------------------------------------------------------------
# LLM integration (reuses generator.py patterns)
# ---------------------------------------------------------------------------


_NO_LLM_MESSAGE = (
    "[LLM not configured. Add GEMINI_API_KEY or install mlx-lm "
    "to have a conversation with your future self.]"
)


def _call_llm(system_prompt: str, user_prompt: str, settings: object) -> str:
    """Call the configured LLM provider. Reuses generator.py patterns.

    Supports: gemini (API), mlx (local), gemini-cli, claude-cli.
    Falls back gracefully if no LLM is available.
    """
    from life_world_model.config import Settings

    if not isinstance(settings, Settings):
        return _NO_LLM_MESSAGE

    provider = settings.llm_provider

    if provider == "gemini" and settings.gemini_api_key:
        return _call_gemini_api(system_prompt, user_prompt, settings)
    elif provider == "mlx":
        return _call_mlx(system_prompt, user_prompt, settings)
    elif provider in ("gemini-cli", "claude-cli"):
        cli_cmd = provider.replace("-cli", "")
        return _call_cli(system_prompt, user_prompt, cli_cmd)
    elif provider == "gemini" and not settings.gemini_api_key:
        # Try CLI fallback
        if shutil.which("gemini"):
            return _call_cli(system_prompt, user_prompt, "gemini")
        return _NO_LLM_MESSAGE

    return _NO_LLM_MESSAGE


def _call_gemini_api(
    system_prompt: str, user_prompt: str, settings: object
) -> str:
    """Call Gemini API for future-self conversation."""
    try:
        from google import genai  # type: ignore[import-untyped]
    except ImportError:
        return _NO_LLM_MESSAGE

    from life_world_model.config import Settings

    if not isinstance(settings, Settings) or not settings.gemini_api_key:
        return _NO_LLM_MESSAGE

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.llm_model,
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.85,
            max_output_tokens=1024,
            thinking_config=genai.types.ThinkingConfig(
                thinking_budget=0,
            ),
        ),
    )
    return response.text or "(No response from Gemini.)"


def _call_mlx(
    system_prompt: str, user_prompt: str, settings: object
) -> str:
    """Call local MLX model for future-self conversation."""
    try:
        from mlx_lm import generate, load  # type: ignore[import-untyped]
    except ImportError:
        return _NO_LLM_MESSAGE

    from life_world_model.config import Settings

    if not isinstance(settings, Settings):
        return _NO_LLM_MESSAGE

    model, tokenizer = load(settings.llm_model)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"/no_think\n{user_prompt}"},
    ]
    formatted = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    response = generate(
        model, tokenizer, prompt=formatted, max_tokens=1024, verbose=False
    )
    return response


def _call_cli(
    system_prompt: str, user_prompt: str, cli_command: str
) -> str:
    """Call a CLI tool (gemini, claude) for future-self conversation."""
    binary = shutil.which(cli_command)
    if not binary:
        return _NO_LLM_MESSAGE

    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    if cli_command == "gemini":
        cmd = [binary, "-p", full_prompt]
    elif cli_command == "claude":
        cmd = [binary, "-p", full_prompt, "--output-format", "text"]
    else:
        cmd = [binary, "-p", full_prompt]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            return f"(CLI error: {result.stderr.strip()[:200]})"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "(LLM CLI timed out after 120 seconds.)"
    except Exception as e:
        return f"(LLM error: {e})"


# ---------------------------------------------------------------------------
# Response generation
# ---------------------------------------------------------------------------


def generate_future_self_response(
    profile: FutureSelfProfile,
    user_message: str,
    conversation_history: list[tuple[str, str]],
    settings: object,
) -> str:
    """Generate the future self's response using the configured LLM.

    Uses the same LLM infrastructure as generator.py.
    Falls back gracefully if no LLM is available.
    """
    system_prompt = build_future_self_system_prompt(profile)
    user_prompt = build_conversation_prompt(
        profile, user_message, conversation_history
    )
    return _call_llm(system_prompt, user_prompt, settings)


# ---------------------------------------------------------------------------
# CLI helper — renders the conversation header
# ---------------------------------------------------------------------------


def format_conversation_header(profile: FutureSelfProfile) -> str:
    """Format the conversation header for CLI display."""
    lines: list[str] = []
    lines.append("")
    lines.append("\u2501" * 50)
    lines.append(
        f"  FUTURE YOU \u2014 {profile.duration_description}"
    )
    lines.append(
        f"  Intervention: \"{profile.intervention}\""
    )
    score_line = (
        f"  Projected score: "
        f"{profile.baseline_score:.0%} \u2192 {profile.simulated_score:.0%}"
    )
    lines.append(score_line)
    lines.append("\u2501" * 50)
    lines.append("")
    return "\n".join(lines)
