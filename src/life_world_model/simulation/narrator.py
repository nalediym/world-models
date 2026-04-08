"""Side-by-side narrative generation for simulation results.

Connects the simulation engine to the narrative generator, producing two
parallel prose narratives: one for the real day and one for the alternate
(simulated) day.
"""

from __future__ import annotations

from datetime import date

from life_world_model.config import Settings
from life_world_model.pipeline.generator import build_timeline_lines
from life_world_model.pipeline.voices import Voice, get_voice
from life_world_model.scoring.formula import _grade
from life_world_model.simulation.types import SimulationNarrative
from life_world_model.types import LifeState


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def build_baseline_prompt(
    states: list[LifeState],
    target_date: date,
    voice: Voice,
) -> str:
    """Build the prompt for the baseline (real day) narrative."""
    timeline = "\n".join(build_timeline_lines(states))
    return (
        f"You are writing a narrative in the '{voice.name}' voice.\n\n"
        "This is the day as it actually happened.\n"
        "Use the timeline below as ground truth.\n"
        "Do not invent major activities that are not supported by the data.\n"
        "If the data is sparse, stay vague instead of hallucinating specifics.\n\n"
        f"Date: {target_date.isoformat()}\n\n"
        "Timeline:\n"
        f"{timeline}\n"
    )


def build_alternate_prompt(
    states: list[LifeState],
    target_date: date,
    voice: Voice,
    intervention_text: str,
    baseline_summary: str,
) -> str:
    """Build the prompt for the alternate (simulated) day narrative.

    The prompt tells the LLM about the intervention and asks it to narrate
    the alternate day, highlighting where it diverges from the real day.
    """
    timeline = "\n".join(build_timeline_lines(states))
    return (
        f"You are writing a narrative in the '{voice.name}' voice.\n\n"
        "This is an ALTERNATE version of the day — a 'what if' scenario.\n"
        f'The intervention applied: "{intervention_text}"\n\n'
        "The real day looked like this (summary):\n"
        f"{baseline_summary}\n\n"
        "In this alternate version, the timeline changed as shown below.\n"
        "Narrate this alternate day, highlighting the moments where it diverges "
        "from the real day. Use language like 'In this version of the day...' or "
        "'But in this world...' to mark the key divergence points.\n\n"
        "Use the timeline below as ground truth.\n"
        "Do not invent major activities that are not supported by the data.\n"
        "If the data is sparse, stay vague instead of hallucinating specifics.\n\n"
        f"Date: {target_date.isoformat()}\n\n"
        "Alternate Timeline:\n"
        f"{timeline}\n"
    )


def build_comparison_prompt(
    intervention_text: str,
    baseline_score: float,
    simulated_score: float,
    score_delta: float,
    voice: Voice,
) -> str:
    """Build a prompt for a brief LLM-generated comparison of the two days."""
    direction = "higher" if score_delta >= 0 else "lower"
    return (
        f"You are writing in the '{voice.name}' voice.\n\n"
        f'A simulation was run with the intervention: "{intervention_text}"\n'
        f"The real day scored {baseline_score:.1%} and the alternate day "
        f"scored {simulated_score:.1%} (delta: {score_delta:+.1%}).\n\n"
        f"The alternate world scores {direction} than the real day.\n"
        "Write 1-2 sentences explaining why the alternate day scores "
        f"{direction}, based on the intervention. Be specific and grounded. "
        "Do not hallucinate reasons that are not directly related to the "
        "intervention described."
    )


# ---------------------------------------------------------------------------
# LLM generation helpers (reuse existing patterns from generator.py)
# ---------------------------------------------------------------------------


def _generate_prose(
    prompt: str,
    system_prompt: str,
    settings: Settings,
) -> str | None:
    """Attempt to generate prose using the configured LLM provider.

    Returns None if no provider is available or if generation fails.
    """
    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            return None
        try:
            from google import genai

            client = genai.Client(api_key=settings.gemini_api_key)
            response = client.models.generate_content(
                model=settings.llm_model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.8,
                    max_output_tokens=4096,
                    thinking_config=genai.types.ThinkingConfig(
                        thinking_budget=0,
                    ),
                ),
            )
            return response.text
        except (ImportError, Exception):
            return None

    if settings.llm_provider == "mlx":
        try:
            from mlx_lm import generate, load

            model, tokenizer = load(settings.llm_model)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"/no_think\n{prompt}"},
            ]
            formatted = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            response = generate(
                model,
                tokenizer,
                prompt=formatted,
                max_tokens=1024,
                verbose=False,
            )
            return response
        except (ImportError, Exception):
            return None

    if settings.llm_provider in ("gemini-cli", "claude-cli"):
        import shutil
        import subprocess

        cli_cmd = settings.llm_provider.replace("-cli", "")
        binary = shutil.which(cli_cmd)
        if not binary:
            return None
        try:
            full_prompt = f"{system_prompt}\n\n{prompt}"
            if cli_cmd == "gemini":
                cmd = [binary, "-p", full_prompt]
            elif cli_cmd == "claude":
                cmd = [binary, "-p", full_prompt, "--output-format", "text"]
            else:
                cmd = [binary, "-p", full_prompt]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                return None
            return result.stdout.strip()
        except Exception:
            return None

    return None


def _build_system_prompt(voice: Voice) -> str:
    """Build a system prompt for simulation narratives."""
    lo, hi = voice.word_range
    return (
        f"{voice.system_prompt} "
        f"{voice.style_instructions} "
        f"Produce a single cohesive narrative of {lo}-{hi} words."
    )


def _build_baseline_summary(states: list[LifeState]) -> str:
    """Build a short text summary of the baseline timeline for context."""
    if not states:
        return "No data recorded."

    from collections import Counter

    activities = Counter(s.primary_activity for s in states)
    parts = []
    for activity, count in activities.most_common():
        minutes = count * 15
        parts.append(f"{activity}: {minutes}min")
    time_range = (
        f"{states[0].timestamp.strftime('%H:%M')}-"
        f"{states[-1].timestamp.strftime('%H:%M')}"
    )
    return f"Time range: {time_range}. Activities: {', '.join(parts)}."


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def narrate_simulation(
    baseline_states: list[LifeState],
    simulated_states: list[LifeState],
    intervention_text: str,
    target_date: date,
    settings: Settings,
    baseline_score: float,
    simulated_score: float,
    voice_name: str | None = None,
) -> SimulationNarrative:
    """Generate two parallel narratives: the real day and the alternate day.

    Falls back to timeline-based text if no LLM provider is configured.
    """
    voice = get_voice(voice_name or "tolkien")
    system_prompt = _build_system_prompt(voice)

    score_delta = simulated_score - baseline_score

    # Build prompts
    baseline_prompt = build_baseline_prompt(baseline_states, target_date, voice)
    baseline_summary = _build_baseline_summary(baseline_states)
    alternate_prompt = build_alternate_prompt(
        simulated_states, target_date, voice, intervention_text, baseline_summary
    )
    comparison_prompt = build_comparison_prompt(
        intervention_text, baseline_score, simulated_score, score_delta, voice
    )

    # Generate narratives
    baseline_narrative = _generate_prose(baseline_prompt, system_prompt, settings)
    simulated_narrative = _generate_prose(alternate_prompt, system_prompt, settings)
    comparison = _generate_prose(comparison_prompt, system_prompt, settings)

    # Fallback to timeline text when LLM is unavailable
    if baseline_narrative is None:
        baseline_narrative = _fallback_timeline(baseline_states)
    if simulated_narrative is None:
        simulated_narrative = _fallback_timeline(simulated_states)
    if comparison is None:
        comparison = _fallback_comparison(
            intervention_text, baseline_score, simulated_score, score_delta
        )

    return SimulationNarrative(
        intervention=intervention_text,
        baseline_score=baseline_score,
        simulated_score=simulated_score,
        score_delta=score_delta,
        baseline_narrative=baseline_narrative,
        simulated_narrative=simulated_narrative,
        voice=voice.name,
        comparison=comparison,
    )


def _fallback_timeline(states: list[LifeState]) -> str:
    """Render states as a readable timeline when no LLM is available."""
    if not states:
        return "(no data)"
    lines = build_timeline_lines(states)
    return "\n".join(lines)


def _fallback_comparison(
    intervention_text: str,
    baseline_score: float,
    simulated_score: float,
    score_delta: float,
) -> str:
    """Simple text comparison when no LLM is available."""
    direction = "higher" if score_delta >= 0 else "lower"
    return (
        f'Applying "{intervention_text}" results in a score that is '
        f"{abs(score_delta):.1%} {direction} than the real day."
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_side_by_side(narrative: SimulationNarrative) -> str:
    """Format the simulation narrative for terminal output.

    Uses a sequential layout with clear headers for readability.
    """
    baseline_grade = _grade(narrative.baseline_score)
    simulated_grade = _grade(narrative.simulated_score)
    delta_sign = "+" if narrative.score_delta >= 0 else ""
    delta_str = f"{delta_sign}{narrative.score_delta:.0%}"

    lines: list[str] = []

    # Header
    sep = "\u2501" * 66
    lines.append("")
    lines.append(sep)
    lines.append("  LIFE WORLD MODEL \u2014 SIMULATION")
    lines.append(f'  "{narrative.intervention}"')
    lines.append(sep)
    lines.append("")

    # Baseline section
    lines.append(
        f"\u2501\u2501\u2501 THE DAY THAT WAS \u2501\u2501\u2501 "
        f"Score: {narrative.baseline_score:.0%} ({baseline_grade}) "
        f"\u2501\u2501\u2501"
    )
    lines.append("")
    lines.append(narrative.baseline_narrative)
    lines.append("")

    # Simulated section
    lines.append(
        f"\u2501\u2501\u2501 THE DAY THAT COULD HAVE BEEN \u2501\u2501\u2501 "
        f"Score: {narrative.simulated_score:.0%} ({simulated_grade}) "
        f"[{delta_str}] \u2501\u2501\u2501"
    )
    lines.append("")
    lines.append(narrative.simulated_narrative)
    lines.append("")

    # Comparison/delta section
    lines.append(f"\u2501\u2501\u2501 DELTA: {delta_str} \u2501\u2501\u2501")
    lines.append("")
    lines.append(narrative.comparison)
    lines.append("")
    lines.append(sep)

    return "\n".join(lines)
