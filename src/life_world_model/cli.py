from __future__ import annotations

import argparse
from datetime import date
from typing import Sequence

from life_world_model.collectors.chrome_history import ChromeHistoryCollector
from life_world_model.config import load_settings
from life_world_model.demo_data import build_demo_events
from life_world_model.pipeline.bucketizer import build_life_states
from life_world_model.pipeline.generator import (
    generate_with_gemini,
    generate_with_mlx,
    render_fallback_markdown,
    render_narrative_markdown,
    write_rollout,
)
from life_world_model.storage.sqlite_store import SQLiteStore


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def run_collect(date_value: str, *, use_demo: bool = False) -> int:
    settings = load_settings()
    target_date = parse_date(date_value)
    store = SQLiteStore(settings.database_path)

    if use_demo:
        events = build_demo_events(target_date)
    else:
        collector = ChromeHistoryCollector(settings.chrome_history_path)
        events = collector.collect_for_date(target_date)

    store.save_raw_events(events)
    source_label = "demo events" if use_demo else "events"
    print(f"Collected {len(events)} {source_label} into {settings.database_path}")
    return 0


def _generate_content(settings, states, target_date):
    """Try the configured LLM provider, fall back to timeline markdown."""
    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            print("GEMINI_API_KEY not set — falling back to timeline output.")
            return render_fallback_markdown(target_date, states)
        try:
            print(f"Generating narrative with {settings.llm_model} ...")
            prose = generate_with_gemini(
                states, target_date, settings.llm_model, settings.gemini_api_key
            )
            return render_narrative_markdown(target_date, states, prose)
        except ImportError:
            print("google-genai not installed — falling back to timeline output.")
            print("Install it with: pip install 'life-world-model[gemini]'")
            return render_fallback_markdown(target_date, states)

    if settings.llm_provider == "mlx":
        try:
            print(f"Generating narrative with {settings.llm_model} ...")
            prose = generate_with_mlx(states, target_date, settings.llm_model)
            return render_narrative_markdown(target_date, states, prose)
        except ImportError:
            print("mlx-lm not installed — falling back to timeline output.")
            print("Install it with: pip install 'life-world-model[mlx]'")
            return render_fallback_markdown(target_date, states)

    return render_fallback_markdown(target_date, states)


def run_generate(date_value: str) -> int:
    settings = load_settings()
    target_date = parse_date(date_value)
    store = SQLiteStore(settings.database_path)

    events = store.load_raw_events_for_date(target_date)
    states = build_life_states(events, bucket_minutes=settings.bucket_minutes)

    content = _generate_content(settings, states, target_date)


    output_path = write_rollout(settings.output_dir, target_date, content)
    print(f"Generated rollout at {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Personal life world model MVP CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="Collect one day of Chrome history")
    collect_parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")
    collect_parser.add_argument("--demo", action="store_true", help="Use bundled demo data instead of Chrome history")

    generate_parser = subparsers.add_parser("generate", help="Generate one day narrative")
    generate_parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")

    run_parser = subparsers.add_parser("run", help="Collect then generate")
    run_parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")
    run_parser.add_argument("--demo", action="store_true", help="Use bundled demo data instead of Chrome history")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "collect":
        return run_collect(args.date_value, use_demo=args.demo)
    if args.command == "generate":
        return run_generate(args.date_value)
    if args.command == "run":
        status = run_collect(args.date_value, use_demo=args.demo)
        if status != 0:
            return status
        return run_generate(args.date_value)

    parser.error(f"Unknown command: {args.command}")
    return 2


def collect_entrypoint() -> int:
    parser = argparse.ArgumentParser(description="Collect one day of Chrome history")
    parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")
    parser.add_argument("--demo", action="store_true", help="Use bundled demo data instead of Chrome history")
    args = parser.parse_args()
    return run_collect(args.date_value, use_demo=args.demo)


def generate_entrypoint() -> int:
    parser = argparse.ArgumentParser(description="Generate one day narrative")
    parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")
    args = parser.parse_args()
    return run_generate(args.date_value)


def run_entrypoint() -> int:
    parser = argparse.ArgumentParser(description="Collect then generate one day narrative")
    parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")
    parser.add_argument("--demo", action="store_true", help="Use bundled demo data instead of Chrome history")
    args = parser.parse_args()
    argv = ["run", "--date", args.date_value]
    if args.demo:
        argv.append("--demo")
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
