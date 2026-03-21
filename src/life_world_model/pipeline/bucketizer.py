from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from life_world_model.types import LifeState, RawEvent


def floor_to_bucket(timestamp: datetime, bucket_minutes: int) -> datetime:
    floored_minute = (timestamp.minute // bucket_minutes) * bucket_minutes
    return timestamp.replace(minute=floored_minute, second=0, microsecond=0)


def infer_activity(events: list[RawEvent]) -> tuple[str, str | None, float]:
    if not events:
        return "idle", None, 0.2

    domains = Counter(event.domain or "" for event in events)
    titles = " ".join((event.title or "") for event in events).lower()
    domain_text = " ".join(domains.keys()).lower()
    combined = f"{titles} {domain_text}"

    if any(token in combined for token in ["github", "arxiv", "paper", "docs", "search"]):
        top_domain = domains.most_common(1)[0][0] or None
        return "research", top_domain, 0.8

    if any(token in combined for token in ["cursor", "vscode", "code", "pull request", "commit"]):
        top_domain = domains.most_common(1)[0][0] or None
        return "coding", top_domain, 0.75

    if any(token in combined for token in ["mail", "gmail", "slack", "message", "chat"]):
        top_domain = domains.most_common(1)[0][0] or None
        return "communication", top_domain, 0.75

    top_domain = domains.most_common(1)[0][0] or None
    return "browsing", top_domain, 0.55


def build_life_states(events: list[RawEvent], bucket_minutes: int = 15) -> list[LifeState]:
    if not events:
        return []

    buckets: dict[datetime, list[RawEvent]] = defaultdict(list)
    for event in events:
        buckets[floor_to_bucket(event.timestamp, bucket_minutes)].append(event)

    states: list[LifeState] = []
    start = floor_to_bucket(events[0].timestamp, bucket_minutes)
    end = floor_to_bucket(events[-1].timestamp, bucket_minutes)
    step = timedelta(minutes=bucket_minutes)
    current = start

    while current <= end:
        bucket_events = buckets.get(current, [])
        primary_activity, secondary_activity, confidence = infer_activity(bucket_events)
        states.append(
            LifeState(
                timestamp=current,
                primary_activity=primary_activity,
                secondary_activity=secondary_activity,
                domain=secondary_activity,
                event_count=len(bucket_events),
                confidence=confidence,
            )
        )
        current += step

    return states
