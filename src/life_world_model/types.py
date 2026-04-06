from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class RawEvent:
    timestamp: datetime
    source: str
    title: str | None = None
    domain: str | None = None
    url: str | None = None
    duration_seconds: float | None = None
    metadata: dict[str, str] | None = None


@dataclass
class LifeState:
    timestamp: datetime
    primary_activity: str
    secondary_activity: str | None
    domain: str | None
    event_count: int
    confidence: float
    sources: list[str] | None = None
    dwell_seconds: float | None = None
    context_switches: int | None = None
    session_depth: int | None = None


@dataclass
class NarrativeFrame:
    timestamp: datetime
    narrative: str


@dataclass
class Pattern:
    name: str
    category: str  # "routine" | "correlation" | "rhythm" | "trigger" | "time_sink"
    description: str
    evidence: dict
    confidence: float
    days_observed: int
    first_seen: date | None = None
    last_seen: date | None = None


@dataclass
class Goal:
    name: str
    description: str
    metric: str
    weight: float
    target: float | None = None


@dataclass
class Suggestion:
    title: str
    rationale: str
    intervention_type: str  # "reorder" | "eliminate" | "add" | "limit" | "time_block"
    source_patterns: list[str] = field(default_factory=list)
    predicted_impact: str = "medium"
    score_delta: float = 0.0
