"""Centralized timestamp epoch conversions for all collectors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Chrome/Chromium: microseconds since 1601-01-01 00:00:00 UTC
CHROME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)

# macOS Core Data (knowledgeC, Calendar): seconds since 2001-01-01 00:00:00 UTC
MAC_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


def chrome_time_to_datetime(microseconds: int) -> datetime:
    """Convert Chrome/Chromium FILETIME timestamp to datetime."""
    return CHROME_EPOCH + timedelta(microseconds=microseconds)


def mac_epoch_to_datetime(seconds: float) -> datetime:
    """Convert macOS Core Data timestamp to datetime."""
    return MAC_EPOCH + timedelta(seconds=seconds)


def mac_epoch_from_datetime(dt: datetime) -> float:
    """Convert datetime to macOS Core Data timestamp (seconds)."""
    return (dt - MAC_EPOCH).total_seconds()
