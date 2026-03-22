from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawEvent:
    timestamp: datetime
    source: str
    title: str | None = None
    domain: str | None = None
    url: str | None = None


@dataclass
class LifeState:
    timestamp: datetime
    primary_activity: str
    secondary_activity: str | None
    domain: str | None
    event_count: int
    confidence: float


@dataclass
class NarrativeFrame:
    timestamp: datetime
    narrative: str
