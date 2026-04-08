from __future__ import annotations

from dataclasses import dataclass, field

from life_world_model.types import LifeState


@dataclass
class Intervention:
    type: str  # "time_block" | "eliminate" | "limit" | "add" | "unknown"
    activity: str
    params: dict = field(default_factory=dict)
    description: str = ""


@dataclass
class SimulationResult:
    baseline_states: list[LifeState]
    simulated_states: list[LifeState]
    intervention: Intervention
    baseline_score: float
    simulated_score: float
    score_delta: float
    summary: str


@dataclass
class SimulationNarrative:
    """Side-by-side narrative output from a simulation run."""

    intervention: str
    baseline_score: float
    simulated_score: float
    score_delta: float
    baseline_narrative: str  # prose for the real day
    simulated_narrative: str  # prose for the alternate day
    voice: str  # which voice was used
    comparison: str = ""  # optional LLM-generated comparison summary
