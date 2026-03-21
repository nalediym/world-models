from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from life_world_model.pipeline.generator import build_prompt, output_path_for_date
from life_world_model.types import LifeState


def test_build_prompt_preserves_timeline_order() -> None:
    states = [
        LifeState(datetime.fromisoformat("2026-03-21T09:00:00"), "research", "github.com", "github.com", 2, 0.8),
        LifeState(datetime.fromisoformat("2026-03-21T09:15:00"), "idle", None, None, 0, 0.2),
    ]

    prompt = build_prompt(states)

    assert prompt.index("09:00") < prompt.index("09:15")


def test_build_prompt_warns_against_hallucination() -> None:
    prompt = build_prompt(
        [LifeState(datetime.fromisoformat("2026-03-21T09:00:00"), "research", "github.com", "github.com", 1, 0.8)]
    )

    assert "Do not invent major activities" in prompt


def test_output_path_for_date_matches_expected_filename() -> None:
    output_path = output_path_for_date(Path("data/processed/rollouts"), date.fromisoformat("2026-03-21"))

    assert output_path.as_posix().endswith("data/processed/rollouts/2026-03-21_narrative.md")
