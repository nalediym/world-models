from __future__ import annotations

from datetime import date
from pathlib import Path

from life_world_model.types import LifeState


def build_timeline_lines(states: list[LifeState]) -> list[str]:
    lines: list[str] = []
    for state in states:
        detail = state.secondary_activity or state.domain or "unknown"
        lines.append(
            f"- {state.timestamp.strftime('%H:%M')} {state.primary_activity} {detail} events={state.event_count} confidence={state.confidence:.2f}"
        )
    return lines


def build_prompt(states: list[LifeState]) -> str:
    timeline = "\n".join(build_timeline_lines(states))
    return (
        "You are writing a Tolkien-esque narrative of a real day.\n\n"
        "Use the timeline below as ground truth.\n"
        "Do not invent major activities that are not supported by the data.\n"
        "If the data is sparse, stay vague instead of hallucinating specifics.\n\n"
        "Timeline:\n"
        f"{timeline}\n"
    )


SYSTEM_PROMPT = (
    "You are a narrator writing in the style of J.R.R. Tolkien. "
    "You transform mundane computer activity logs into rich, grounded fantasy prose. "
    "Stay faithful to the timeline — do not invent activities not present in the data. "
    "If a period is idle or sparse, describe it with atmospheric brevity rather than fabricating detail. "
    "Write in past tense. Produce a single cohesive narrative of 200-400 words. "
    "Output ONLY the narrative prose — no headings, no bullet points, no meta-commentary."
)


def generate_with_gemini(
    states: list[LifeState],
    target_date: date,
    model_name: str,
    api_key: str,
) -> str:
    """Generate a prose narrative using the Gemini API."""
    from google import genai

    client = genai.Client(api_key=api_key)

    user_msg = (
        f"Write a Tolkien-esque narrative for {target_date.isoformat()}.\n\n"
        + build_prompt(states)
    )

    response = client.models.generate_content(
        model=model_name,
        contents=user_msg,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
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
) -> str:
    """Generate a prose narrative using a local MLX model."""
    from mlx_lm import generate, load

    model, tokenizer = load(model_name)

    user_msg = (
        f"/no_think\n"
        f"Write a Tolkien-esque narrative for {target_date.isoformat()}.\n\n"
        + build_prompt(states)
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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
) -> str:
    """Generate prose by piping the prompt to a CLI tool (gemini, claude, etc.).

    Uses the CLI's own authentication — no API key needed.
    Supported commands: 'gemini', 'claude'.
    """
    import shutil
    import subprocess

    binary = shutil.which(cli_command)
    if not binary:
        raise FileNotFoundError(f"{cli_command} CLI not found in PATH")

    user_msg = (
        f"Write a Tolkien-esque narrative for {target_date.isoformat()}.\n\n"
        + build_prompt(states)
    )
    full_prompt = f"{SYSTEM_PROMPT}\n\n{user_msg}"

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
