"""Collector that parses zsh extended history for timestamped terminal commands."""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

from life_world_model.collectors.base import BaseCollector, register_collector
from life_world_model.types import RawEvent

# zsh extended_history format: `: EPOCH:DURATION;command`
_ZSH_LINE_RE = re.compile(r"^: (\d+):(\d+);(.+)$")


@register_collector
class ShellHistoryCollector(BaseCollector):
    """Parse ``~/.zsh_history`` for timestamped terminal commands."""

    source_name = "shell"

    def __init__(self, history_path: Path) -> None:
        self._path = history_path

    def is_available(self) -> bool:
        return self._path.exists()

    def collect_for_date(self, target_date: date) -> list[RawEvent]:
        if not self.is_available():
            return []

        try:
            text = self._path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []

        events: list[RawEvent] = []
        for line in text.splitlines():
            match = _ZSH_LINE_RE.match(line)
            if match is None:
                continue

            epoch_str, _duration_str, command = match.groups()
            ts = datetime.fromtimestamp(int(epoch_str), tz=timezone.utc)

            if ts.date() != target_date:
                continue

            events.append(
                RawEvent(
                    timestamp=ts,
                    source="shell",
                    title=command,
                    domain="terminal",
                )
            )

        return events
