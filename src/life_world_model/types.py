from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


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
    id: str | None = None


class FeedbackAction(Enum):
    ACCEPT = "accept"
    REJECT = "reject"


@dataclass
class SuggestionFeedback:
    suggestion_id: str
    suggestion_title: str
    action: FeedbackAction
    timestamp: datetime = field(default_factory=datetime.now)
    notes: str | None = None


class ExperimentStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Experiment:
    id: str
    description: str
    intervention: str  # natural-language intervention text
    duration_days: int
    start_date: date
    status: ExperimentStatus = ExperimentStatus.ACTIVE
    baseline_score: float | None = None
    result_score: float | None = None
    result_summary: str | None = None


@dataclass
class ProposedExperiment:
    description: str
    duration_days: int = 3
    expected_impact: str = "medium"
    source_suggestion_id: str = ""
    predicted_score_delta: float = 0.0
