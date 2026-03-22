from __future__ import annotations

from datetime import date, datetime

from life_world_model.types import RawEvent


def build_demo_events(target_date: date) -> list[RawEvent]:
    iso_day = target_date.isoformat()
    return [
        RawEvent(
            timestamp=datetime.fromisoformat(f"{iso_day}T08:05:00"),
            source="demo",
            title="Morning notes in docs",
            domain="docs.example",
            url="https://docs.example/morning-notes",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat(f"{iso_day}T08:12:00"),
            source="demo",
            title="World models search",
            domain="google.com",
            url="https://google.com/search?q=world+models",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat(f"{iso_day}T08:34:00"),
            source="demo",
            title="GitHub issue triage",
            domain="github.com",
            url="https://github.com/example/world-models/issues",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat(f"{iso_day}T09:02:00"),
            source="demo",
            title="ArXiv paper on world models",
            domain="arxiv.org",
            url="https://arxiv.org/abs/1234.5678",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat(f"{iso_day}T09:18:00"),
            source="demo",
            title="Gmail follow-up",
            domain="mail.google.com",
            url="https://mail.google.com/mail/u/0/#inbox",
        ),
        RawEvent(
            timestamp=datetime.fromisoformat(f"{iso_day}T09:47:00"),
            source="demo",
            title="Project README",
            domain="github.com",
            url="https://github.com/example/world-models",
        ),
    ]
