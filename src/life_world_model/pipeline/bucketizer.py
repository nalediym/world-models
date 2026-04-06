from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from life_world_model.types import LifeState, RawEvent


def floor_to_bucket(timestamp: datetime, bucket_minutes: int) -> datetime:
    floored_minute = (timestamp.minute // bucket_minutes) * bucket_minutes
    return timestamp.replace(minute=floored_minute, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Bundle-ID-to-activity mapping for knowledgeC app focus signals
# ---------------------------------------------------------------------------

_CODING_BUNDLE_IDS = {
    "com.microsoft.VSCode",
    "com.todesktop.runtime.cursor",
    "com.apple.Terminal",
    "com.googlecode.iterm2",
}

_COMMUNICATION_BUNDLE_IDS = {
    "com.tinyspeck.slackmacgap",
    "com.apple.mail",
    "com.apple.MobileSMS",
}

_BROWSER_BUNDLE_IDS = {
    "com.apple.Safari",
    "com.google.Chrome",
}

_FILE_MANAGEMENT_BUNDLE_IDS = {
    "com.apple.finder",
}

_AI_TOOLING_BUNDLE_IDS = {
    "com.anthropic.claudecode",
}


def _classify_bundle_id(bundle_id: str) -> tuple[str, float]:
    """Map a knowledgeC bundle ID to an (activity, confidence) pair."""
    if bundle_id in _CODING_BUNDLE_IDS:
        return "coding", 0.85
    if bundle_id in _COMMUNICATION_BUNDLE_IDS:
        return "communication", 0.80
    if bundle_id in _BROWSER_BUNDLE_IDS:
        # Browsers need further classification by URL — handled by caller
        return "browser", 0.0
    if bundle_id in _FILE_MANAGEMENT_BUNDLE_IDS:
        return "file_management", 0.70
    if bundle_id in _AI_TOOLING_BUNDLE_IDS:
        return "ai_tooling", 0.85
    return "browsing", 0.55


# ---------------------------------------------------------------------------
# Keyword-based URL/title classification (fallback / browser refinement)
# ---------------------------------------------------------------------------

def _classify_by_keywords(events: list[RawEvent]) -> tuple[str, str | None, float]:
    """Classify events using keyword matching on domains and titles.

    This is the original heuristic — used as a fallback when no stronger
    signal (calendar, knowledgeC, git, shell) is available, and also to
    refine browser bundle IDs.
    """
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


# ---------------------------------------------------------------------------
# Multi-source priority cascade
# ---------------------------------------------------------------------------

def infer_activity(events: list[RawEvent]) -> tuple[str, str | None, float]:
    """Infer the primary activity for a bucket of events.

    Uses a priority cascade — the strongest signal available wins:
      1. Calendar event → "meeting"
      2. knowledgeC app focus → bundle-ID lookup
      3. Chrome/Safari URL → keyword matching
      4. Git commit → "coding"
      5. Shell command → "coding"
      6. No events → "idle"
    """
    if not events:
        return "idle", None, 0.2

    # --- Priority 1: Calendar events ---
    calendar_events = [e for e in events if e.source == "calendar"]
    if calendar_events:
        # Pick the calendar event with the longest duration, or the first one
        best = max(calendar_events, key=lambda e: e.duration_seconds or 0)
        return "meeting", best.title, 0.95

    # --- Priority 2: knowledgeC app focus ---
    knowledgec_events = [
        e for e in events
        if e.source == "knowledgec"
        and e.metadata
        and e.metadata.get("stream") == "/app/inFocus"
    ]
    if knowledgec_events:
        # Use the app with the longest duration_seconds in the bucket
        best_kc = max(knowledgec_events, key=lambda e: e.duration_seconds or 0)
        bundle_id = best_kc.domain or ""
        activity, confidence = _classify_bundle_id(bundle_id)

        if activity == "browser":
            # Further classify by URL using keyword matching on all
            # browser-related events in the bucket (chrome + knowledgec safari)
            browser_events = [
                e for e in events
                if e.source == "chrome"
                or (e.source == "knowledgec"
                    and e.metadata
                    and e.metadata.get("stream") == "/safari/history")
            ]
            if browser_events:
                return _classify_by_keywords(browser_events)
            # No URL events — generic browsing
            return "browsing", best_kc.title, 0.55

        return activity, best_kc.title, confidence

    # --- Priority 3: Chrome/Safari URL events ---
    url_events = [
        e for e in events
        if e.source == "chrome"
        or (e.source == "knowledgec"
            and e.metadata
            and e.metadata.get("stream") == "/safari/history")
    ]
    if url_events:
        return _classify_by_keywords(url_events)

    # --- Priority 4: Git commits ---
    git_events = [e for e in events if e.source == "git"]
    if git_events:
        best_git = git_events[0]
        return "coding", best_git.domain, 0.90

    # --- Priority 5: Shell commands ---
    shell_events = [e for e in events if e.source == "shell"]
    if shell_events:
        return "coding", None, 0.70

    # --- Priority 6: Fallback — use keyword matching on whatever we have ---
    return _classify_by_keywords(events)


def _collect_sources(events: list[RawEvent]) -> list[str]:
    """Return a deduplicated, sorted list of source names from events."""
    return sorted({e.source for e in events}) if events else []


def build_life_states(
    events: list[RawEvent], bucket_minutes: int = 15
) -> list[LifeState]:
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
        primary_activity, secondary_activity, confidence = infer_activity(
            bucket_events
        )
        states.append(
            LifeState(
                timestamp=current,
                primary_activity=primary_activity,
                secondary_activity=secondary_activity,
                domain=secondary_activity,
                event_count=len(bucket_events),
                confidence=confidence,
                sources=_collect_sources(bucket_events),
            )
        )
        current += step

    # Post-processing: compute behavioral signals
    from life_world_model.pipeline.signals import compute_signals

    states = compute_signals(states, dict(buckets), bucket_minutes)

    return states
