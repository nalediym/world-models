from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    database_path: Path = Path("data/raw/life_world_model.sqlite3")
    output_dir: Path = Path("data/processed/rollouts")
    chrome_history_path: Path = Path.home() / "Library/Application Support/Google/Chrome/Default/History"
    bucket_minutes: int = 15
    llm_provider: str | None = None
    llm_model: str | None = None


def load_settings() -> Settings:
    database_path = Path(os.getenv("LWM_DATABASE_PATH", "data/raw/life_world_model.sqlite3"))
    output_dir = Path(os.getenv("LWM_OUTPUT_DIR", "data/processed/rollouts"))
    chrome_history_path = Path(
        os.getenv(
            "LWM_CHROME_HISTORY_PATH",
            str(Path.home() / "Library/Application Support/Google/Chrome/Default/History"),
        )
    )

    bucket_minutes = int(os.getenv("LWM_BUCKET_MINUTES", "15"))
    llm_provider = os.getenv("LWM_LLM_PROVIDER")
    llm_model = os.getenv("LWM_LLM_MODEL")

    return Settings(
        database_path=database_path,
        output_dir=output_dir,
        chrome_history_path=chrome_history_path,
        bucket_minutes=bucket_minutes,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )
