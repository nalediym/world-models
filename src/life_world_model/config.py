from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    database_path: Path = Path("data/raw/life_world_model.sqlite3")
    output_dir: Path = Path("data/processed/rollouts")
    chrome_history_path: Path = Path.home() / "Library/Application Support/Google/Chrome/Default/History"
    knowledgec_path: Path = Path.home() / "Library/Application Support/Knowledge/knowledgeC.db"
    zsh_history_path: Path = Path.home() / ".zsh_history"
    git_scan_paths: list[Path] | None = None
    calendar_path: Path = Path.home() / "Library/Calendars"
    safari_history_path: Path = Path.home() / "Library/Safari/History.db"
    bucket_minutes: int = 15
    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.5-flash"
    gemini_api_key: str | None = None
    default_style: str = "plain"
    # Narrative voice/persona. Valid: tolkien, clinical, casual, poetic, coach, data
    voice: str = "tolkien"


def _load_dotenv() -> None:
    """Load .env file into os.environ if it exists. No external deps."""
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key not in os.environ:
            os.environ[key] = value


def load_settings() -> Settings:
    _load_dotenv()
    database_path = Path(os.getenv("LWM_DATABASE_PATH", "data/raw/life_world_model.sqlite3"))
    output_dir = Path(os.getenv("LWM_OUTPUT_DIR", "data/processed/rollouts"))
    chrome_history_path = Path(
        os.getenv(
            "LWM_CHROME_HISTORY_PATH",
            str(Path.home() / "Library/Application Support/Google/Chrome/Default/History"),
        )
    )

    knowledgec_path = Path(
        os.getenv(
            "LWM_KNOWLEDGEC_PATH",
            str(Path.home() / "Library/Application Support/Knowledge/knowledgeC.db"),
        )
    )
    zsh_history_path = Path(os.getenv("LWM_ZSH_HISTORY_PATH", str(Path.home() / ".zsh_history")))
    git_scan_raw = os.getenv("LWM_GIT_SCAN_PATHS", str(Path.home() / "Projects"))
    git_scan_paths = [Path(p.strip()) for p in git_scan_raw.split(":") if p.strip()]
    calendar_path = Path(
        os.getenv("LWM_CALENDAR_PATH", str(Path.home() / "Library/Calendars"))
    )
    safari_history_path = Path(
        os.getenv("LWM_SAFARI_HISTORY_PATH", str(Path.home() / "Library/Safari/History.db"))
    )

    bucket_minutes = int(os.getenv("LWM_BUCKET_MINUTES", "15"))
    llm_provider = os.getenv("LWM_LLM_PROVIDER", "gemini")
    llm_model = os.getenv("LWM_LLM_MODEL", "gemini-2.5-flash")
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    default_style = os.getenv("LWM_DEFAULT_STYLE", "plain")
    voice = os.getenv("LWM_VOICE", "tolkien")

    return Settings(
        database_path=database_path,
        output_dir=output_dir,
        chrome_history_path=chrome_history_path,
        knowledgec_path=knowledgec_path,
        zsh_history_path=zsh_history_path,
        git_scan_paths=git_scan_paths,
        calendar_path=calendar_path,
        bucket_minutes=bucket_minutes,
        llm_provider=llm_provider,
        llm_model=llm_model,
        gemini_api_key=gemini_api_key,
        default_style=default_style,
        voice=voice,
        safari_history_path=safari_history_path,
    )
