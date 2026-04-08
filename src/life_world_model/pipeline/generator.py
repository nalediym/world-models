from __future__ import annotations

from datetime import date
from pathlib import Path

from life_world_model.pipeline.voices import Voice, get_voice
from life_world_model.types import LifeState


def build_timeline_lines(states: list[LifeState]) -> list[str]:
    lines: list[str] = []
    for state in states:
        detail = state.secondary_activity or state.domain or "unknown"
        lines.append(
            f"- {state.timestamp.strftime('%H:%M')} {state.primary_activity} {detail} events={state.event_count} confidence={state.confidence:.2f}"
        )
    return lines


def build_prompt(states: list[LifeState], voice: Voice | None = None) -> str:
    """Build the user-facing prompt for narrative generation.

    Parameters
    ----------
    states:
        The bucketed LifeState timeline for the day.
    voice:
        Optional narrative voice. Falls back to 'tolkien' when *None*.
    """
    if voice is None:
        voice = get_voice("tolkien")
    timeline = "\n".join(build_timeline_lines(states))
    return (
        f"You are writing a narrative in the '{voice.name}' voice.\n\n"
        "Use the timeline below as ground truth.\n"
        "Do not invent major activities that are not supported by the data.\n"
        "If the data is sparse, stay vague instead of hallucinating specifics.\n\n"
        "Timeline:\n"
        f"{timeline}\n"
    )


def build_system_prompt(voice: Voice | None = None) -> str:
    """Build the system prompt from a Voice definition.

    Parameters
    ----------
    voice:
        Optional narrative voice. Falls back to 'tolkien' when *None*.
    """
    if voice is None:
        voice = get_voice("tolkien")
    lo, hi = voice.word_range
    return (
        f"{voice.system_prompt} "
        f"{voice.style_instructions} "
        f"Produce a single cohesive narrative of {lo}-{hi} words."
    )


# Kept for backward-compatibility — existing code that references SYSTEM_PROMPT
# still works, pointing at the default tolkien voice.
SYSTEM_PROMPT = build_system_prompt()


def generate_with_gemini(
    states: list[LifeState],
    target_date: date,
    model_name: str,
    api_key: str,
    voice: Voice | None = None,
) -> str:
    """Generate a prose narrative using the Gemini API."""
    from google import genai

    if voice is None:
        voice = get_voice("tolkien")

    client = genai.Client(api_key=api_key)

    user_msg = (
        f"Write a narrative for {target_date.isoformat()} in the '{voice.name}' voice.\n\n"
        + build_prompt(states, voice)
    )

    system = build_system_prompt(voice)

    response = client.models.generate_content(
        model=model_name,
        contents=user_msg,
        config=genai.types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.8,
            max_output_tokens=4096,
            thinking_config=genai.types.ThinkingConfig(
                thinking_budget=0,
            ),
        ),
    )

    return response.text


def generate_with_mlx(
    states: list[LifeState],
    target_date: date,
    model_name: str,
    voice: Voice | None = None,
) -> str:
    """Generate a prose narrative using a local MLX model."""
    from mlx_lm import generate, load

    if voice is None:
        voice = get_voice("tolkien")

    model, tokenizer = load(model_name)

    user_msg = (
        f"/no_think\n"
        f"Write a narrative for {target_date.isoformat()} in the '{voice.name}' voice.\n\n"
        + build_prompt(states, voice)
    )

    system = build_system_prompt(voice)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
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


def generate_with_cli(
    states: list[LifeState],
    target_date: date,
    cli_command: str,
    voice: Voice | None = None,
) -> str:
    """Generate prose by piping the prompt to a CLI tool (gemini, claude, etc.).

    Uses the CLI's own authentication — no API key needed.
    Supported commands: 'gemini', 'claude'.
    """
    import shutil
    import subprocess

    if voice is None:
        voice = get_voice("tolkien")

    binary = shutil.which(cli_command)
    if not binary:
        raise FileNotFoundError(f"{cli_command} CLI not found in PATH")

    user_msg = (
        f"Write a narrative for {target_date.isoformat()} in the '{voice.name}' voice.\n\n"
        + build_prompt(states, voice)
    )
    system = build_system_prompt(voice)
    full_prompt = f"{system}\n\n{user_msg}"

    if cli_command == "gemini":
        cmd = [binary, "-p", full_prompt]
    elif cli_command == "claude":
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
        raise RuntimeError(f"{cli_command} CLI failed: {result.stderr.strip()}")

    return result.stdout.strip()


def render_narrative_markdown(
    target_date: date, states: list[LifeState], prose: str
) -> str:
    lines = [f"# Narrative for {target_date.isoformat()}", ""]
    lines.append(prose.strip())
    lines.extend(["", "---", "", "## Timeline", ""])
    for timeline_line in build_timeline_lines(states):
        lines.append(timeline_line)
    return "\n".join(lines) + "\n"


def render_fallback_markdown(target_date: date, states: list[LifeState]) -> str:
    lines = [f"# Narrative for {target_date.isoformat()}", "", "## Timeline", ""]
    for timeline_line in build_timeline_lines(states):
        lines.append(timeline_line)
    lines.extend(
        [
            "",
            "## Narrative Draft",
            "",
            "This fallback draft is grounded in the collected timeline and exists so the MVP stays runnable before an API-backed prose generator is wired in.",
        ]
    )
    return "\n".join(lines) + "\n"


def output_path_for_date(output_dir: Path, target_date: date) -> Path:
    return output_dir / f"{target_date.isoformat()}_narrative.md"


def write_rollout(output_dir: Path, target_date: date, content: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_path_for_date(output_dir, target_date)
    output_path.write_text(content, encoding="utf-8")
    return output_path
