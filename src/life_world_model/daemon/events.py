"""Typed event dataclasses for the daemon event bus.

Each event represents something that happened. Handlers subscribe by type.
Inspired by Elixir Phoenix.PubSub + Rust typed channels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from life_world_model.types import Experiment, Pattern, Suggestion


@dataclass
class DataCollected:
    """Emitted after each collection cycle."""
    collected_date: date
    event_count: int


@dataclass
class PatternsUpdated:
    """Emitted after pattern discovery runs."""
    patterns: list[Pattern]
    new_patterns: list[Pattern] = field(default_factory=list)


@dataclass
class ScoreChanged:
    """Emitted when today's score is recomputed."""
    scored_date: date
    old_score: float
    new_score: float
    grade: str


@dataclass
class ExperimentCompleted:
    """Emitted when an active experiment finishes its duration."""
    experiment: Experiment


@dataclass
class SuggestionsReady:
    """Emitted after suggestions are regenerated from updated patterns."""
    suggestions: list[Suggestion]


@dataclass
class PatternDecayed:
    """Emitted after pattern confidence decay is applied."""
    pruned_count: int
    remaining_count: int
