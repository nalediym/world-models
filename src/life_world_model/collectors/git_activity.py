"""Collect commit history from local git repos."""

from __future__ import annotations

import logging
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

from life_world_model.collectors.base import BaseCollector, register_collector
from life_world_model.types import RawEvent

logger = logging.getLogger(__name__)


def _find_repos(scan_paths: list[Path]) -> list[Path]:
    """Return repo root directories one level below each scan path."""
    repos: list[Path] = []
    for scan_path in scan_paths:
        if not scan_path.is_dir():
            continue
        for child in sorted(scan_path.iterdir()):
            if child.is_dir() and (child / ".git" / "HEAD").exists():
                repos.append(child)
    return repos


def _repo_name(repo_path: Path) -> str:
    """Derive a human-readable repo name from its directory."""
    return repo_path.name


def _parse_log_line(line: str) -> tuple[str, datetime, str] | None:
    """Parse a single git log line in ``hash|iso_date|message`` format.

    Only split on the first two ``|`` characters so that pipe characters
    inside the commit message are preserved.
    """
    parts = line.split("|", 2)
    if len(parts) < 3:
        return None
    commit_hash, iso_date, message = parts
    try:
        ts = datetime.fromisoformat(iso_date)
    except ValueError:
        return None
    return commit_hash.strip(), ts, message.strip()


@register_collector
class GitActivityCollector(BaseCollector):
    """Scan local git repos for commit activity on a given date."""

    source_name = "git"

    def __init__(self, scan_paths: list[Path]) -> None:
        self.scan_paths = scan_paths

    def is_available(self) -> bool:
        """True when at least one configured scan path exists on disk."""
        return any(p.is_dir() for p in self.scan_paths)

    def collect_for_date(self, target_date: date) -> list[RawEvent]:
        repos = _find_repos(self.scan_paths)
        events: list[RawEvent] = []

        # git log --after is exclusive, --before is exclusive, so we bracket
        # the full calendar day.
        after = target_date.isoformat()
        before = (target_date + timedelta(days=1)).isoformat()

        for repo in repos:
            try:
                result = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo),
                        "log",
                        "--all",
                        "--format=%H|%aI|%s",
                        f"--after={after}",
                        f"--before={before}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except subprocess.TimeoutExpired:
                logger.warning("git log timed out for %s — skipping", repo)
                continue
            except OSError as exc:
                logger.warning("Failed to run git log for %s: %s", repo, exc)
                continue

            if result.returncode != 0:
                logger.warning(
                    "git log returned %d for %s: %s",
                    result.returncode,
                    repo,
                    result.stderr.strip(),
                )
                continue

            name = _repo_name(repo)
            for line in result.stdout.strip().splitlines():
                if not line.strip():
                    continue
                parsed = _parse_log_line(line)
                if parsed is None:
                    logger.debug("Skipping unparseable git log line: %s", line)
                    continue
                commit_hash, ts, message = parsed
                events.append(
                    RawEvent(
                        timestamp=ts,
                        source="git",
                        title=message,
                        domain=name,
                        url=commit_hash,
                    )
                )

        return events
