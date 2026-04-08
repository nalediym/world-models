"""Recent Files collector — uses macOS Spotlight (mdfind) to find recently modified files."""

from __future__ import annotations

import logging
import shutil
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from life_world_model.collectors.base import BaseCollector, register_collector
from life_world_model.types import RawEvent

logger = logging.getLogger(__name__)

# Only report files under these directories (relative to home).
_INTERESTING_DIRS = ("Projects", "Documents", "Desktop", "Downloads")

# Skip files whose paths contain any of these substrings.
_SKIP_PATTERNS = ("/.", "/Library/", "/node_modules/", "/__pycache__/", "/.git/")


def _is_interesting(path: str, home: str) -> bool:
    """Return True if *path* is under one of the interesting directories."""
    for d in _INTERESTING_DIRS:
        prefix = f"{home}/{d}"
        if path.startswith(prefix):
            # Also reject hidden/library paths within interesting dirs.
            relative = path[len(prefix):]
            if not any(skip in relative for skip in _SKIP_PATTERNS):
                return True
    return False


@register_collector
class RecentFilesCollector(BaseCollector):
    """Uses ``mdfind`` (Spotlight) to find files modified on a given date."""

    source_name = "files"

    def __init__(self, scan_paths: list[Path] | None = None) -> None:
        # scan_paths is kept for consistency but mdfind searches system-wide;
        # we filter results to interesting directories in post-processing.
        self._scan_paths = scan_paths

    def is_available(self) -> bool:
        return shutil.which("mdfind") is not None

    def collect_for_date(self, target_date: date) -> list[RawEvent]:
        if not self.is_available():
            return []

        # Build date strings for the mdfind query (UTC day boundaries).
        start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
        start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)
        end_str = end.strftime("%Y-%m-%dT%H:%M:%SZ")

        query = (
            f"kMDItemFSContentChangeDate >= $time.iso({start_str})"
            f" && kMDItemFSContentChangeDate <= $time.iso({end_str})"
        )

        try:
            result = subprocess.run(
                ["mdfind", query],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            logger.warning("mdfind failed: %s", exc)
            return []

        if result.returncode != 0:
            logger.warning("mdfind returned non-zero: %s", result.stderr.strip())
            return []

        home = str(Path.home())
        events: list[RawEvent] = []

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            if not _is_interesting(line, home):
                continue

            file_path = Path(line)
            try:
                mtime = file_path.stat().st_mtime
                timestamp = datetime.fromtimestamp(mtime, tz=timezone.utc)
            except OSError:
                # File may have been deleted between mdfind and stat.
                continue

            # Only include if the modification is actually on the target date.
            if timestamp.date() != target_date:
                continue

            # Parent directory as domain (e.g. "Projects/my-repo/src").
            parent = str(file_path.parent)
            if parent.startswith(home):
                parent = "~" + parent[len(home):]

            events.append(
                RawEvent(
                    timestamp=timestamp,
                    source="files",
                    title=file_path.name,
                    domain=parent,
                )
            )

        # Sort by timestamp ascending.
        events.sort(key=lambda e: e.timestamp)
        return events
