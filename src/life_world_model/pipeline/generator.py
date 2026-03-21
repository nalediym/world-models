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
