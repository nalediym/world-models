from __future__ import annotations

import argparse
from datetime import date
from typing import Sequence

from life_world_model.collectors.chrome_history import ChromeHistoryCollector
from life_world_model.config import load_settings
from life_world_model.pipeline.bucketizer import build_life_states
from life_world_model.pipeline.generator import render_fallback_markdown, write_rollout
from life_world_model.storage.sqlite_store import SQLiteStore


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def run_collect(date_value: str) -> int:
    settings = load_settings()
    target_date = parse_date(date_value)
    collector = ChromeHistoryCollector(settings.chrome_history_path)
    store = SQLiteStore(settings.database_path)

    events = collector.collect_for_date(target_date)
    store.save_raw_events(events)
    print(f"Collected {len(events)} events into {settings.database_path}")
    return 0


def run_generate(date_value: str) -> int:
    settings = load_settings()
    target_date = parse_date(date_value)
    store = SQLiteStore(settings.database_path)

    events = store.load_raw_events_for_date(target_date)
    states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
    content = render_fallback_markdown(target_date, states)
    output_path = write_rollout(settings.output_dir, target_date, content)
    print(f"Generated rollout at {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Personal life world model MVP CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="Collect one day of Chrome history")
    collect_parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")

    generate_parser = subparsers.add_parser("generate", help="Generate one day narrative")
    generate_parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")

    run_parser = subparsers.add_parser("run", help="Collect then generate")
    run_parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "collect":
        return run_collect(args.date_value)
    if args.command == "generate":
        return run_generate(args.date_value)
    if args.command == "run":
        status = run_collect(args.date_value)
        if status != 0:
            return status
        return run_generate(args.date_value)

    parser.error(f"Unknown command: {args.command}")
    return 2


def collect_entrypoint() -> int:
    parser = argparse.ArgumentParser(description="Collect one day of Chrome history")
    parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")
    args = parser.parse_args()
    return run_collect(args.date_value)


def generate_entrypoint() -> int:
    parser = argparse.ArgumentParser(description="Generate one day narrative")
    parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")
    args = parser.parse_args()
    return run_generate(args.date_value)


def run_entrypoint() -> int:
    parser = argparse.ArgumentParser(description="Collect then generate one day narrative")
    parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")
    args = parser.parse_args()
    return main(["run", "--date", args.date_value])


if __name__ == "__main__":
    raise SystemExit(main())
