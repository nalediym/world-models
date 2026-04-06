from __future__ import annotations

import argparse
from datetime import date, timedelta
from typing import Sequence

from life_world_model.config import Settings, load_settings
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


def _import_collectors() -> None:
    """Import all collector modules to trigger @register_collector decorators."""
    import importlib

    for mod_name in (
        "chrome_history",
        "knowledgec",
        "shell_history",
        "git_activity",
        "calendar",
    ):
        try:
            importlib.import_module(f"life_world_model.collectors.{mod_name}")
        except ImportError:
            pass


def _build_collectors(settings: Settings, source_filter: str | None = None) -> list:
    """Instantiate collectors from settings, optionally filtering to one source."""
    from life_world_model.collectors.chrome_history import ChromeHistoryCollector

    # Map source names to constructor calls
    factory: dict[str, object] = {
        "chrome": lambda: ChromeHistoryCollector(settings.chrome_history_path),
    }

    # Add other collectors if their modules loaded
    try:
        from life_world_model.collectors.knowledgec import KnowledgeCCollector

        factory["knowledgec"] = lambda: KnowledgeCCollector(settings.knowledgec_path)
    except ImportError:
        pass
    try:
        from life_world_model.collectors.shell_history import ShellHistoryCollector

        factory["shell"] = lambda: ShellHistoryCollector(settings.zsh_history_path)
    except ImportError:
        pass
    try:
        from life_world_model.collectors.git_activity import GitActivityCollector

        factory["git"] = lambda: GitActivityCollector(settings.git_scan_paths or [])
    except ImportError:
        pass
    try:
        from life_world_model.collectors.calendar import CalendarCollector

        factory["calendar"] = lambda: CalendarCollector(settings.calendar_path)
    except ImportError:
        pass

    if source_filter:
        if source_filter not in factory:
            print(f"Unknown source: {source_filter}. Available: {', '.join(factory)}")
            return []
        return [factory[source_filter]()]
    return [f() for f in factory.values()]


def run_collect(
    date_value: str,
    *,
    use_demo: bool = False,
    source: str | None = None,
) -> int:
    settings = load_settings()
    target_date = parse_date(date_value)
    store = SQLiteStore(settings.database_path)

    if use_demo:
        events = build_demo_events(target_date)
        store.save_raw_events(events)
        print(f"Collected {len(events)} demo events into {settings.database_path}")
        return 0

    # Import all collector modules to trigger registration
    _import_collectors()

    collectors = _build_collectors(settings, source)
    total = 0
    for collector in collectors:
        if not collector.is_available():
            continue
        try:
            events = collector.collect_for_date(target_date)
            store.save_raw_events(events)
            print(f"  {collector.source_name}: {len(events)} events")
            total += len(events)
        except Exception as e:
            print(f"  {collector.source_name}: error — {e}")

    print(f"Collected {total} events into {settings.database_path}")
    return 0


def run_backfill(*, source: str | None = None) -> int:
    """Collect backwards from today, stopping after 7 consecutive zero-event days."""
    settings = load_settings()
    store = SQLiteStore(settings.database_path)

    _import_collectors()

    current_date = date.today()
    consecutive_empty = 0

    while consecutive_empty < 7:
        date_str = current_date.isoformat()
        print(f"\n--- {date_str} ---")

        collectors = _build_collectors(settings, source)
        day_total = 0
        for collector in collectors:
            if not collector.is_available():
                continue
            try:
                events = collector.collect_for_date(current_date)
                store.save_raw_events(events)
                print(f"  {collector.source_name}: {len(events)} events")
                day_total += len(events)
            except Exception as e:
                print(f"  {collector.source_name}: error — {e}")

        print(f"  total: {day_total} events")

        if day_total == 0:
            consecutive_empty += 1
        else:
            consecutive_empty = 0

        current_date -= timedelta(days=1)

    print(f"\nBackfill complete — stopped after {consecutive_empty} consecutive empty days.")
    return 0


def run_sources() -> int:
    """Print collector status: name, availability, and data path."""
    settings = load_settings()
    _import_collectors()

    # Build a list of (name, available, path_info) tuples
    source_info: list[tuple[str, bool, str]] = []

    from life_world_model.collectors.chrome_history import ChromeHistoryCollector

    c = ChromeHistoryCollector(settings.chrome_history_path)
    source_info.append(("chrome", c.is_available(), str(settings.chrome_history_path)))

    try:
        from life_world_model.collectors.knowledgec import KnowledgeCCollector

        c = KnowledgeCCollector(settings.knowledgec_path)
        source_info.append(("knowledgec", c.is_available(), str(settings.knowledgec_path)))
    except ImportError:
        source_info.append(("knowledgec", False, str(settings.knowledgec_path) + " (module not installed)"))

    try:
        from life_world_model.collectors.shell_history import ShellHistoryCollector

        c = ShellHistoryCollector(settings.zsh_history_path)
        source_info.append(("shell", c.is_available(), str(settings.zsh_history_path)))
    except ImportError:
        source_info.append(("shell", False, str(settings.zsh_history_path) + " (module not installed)"))

    try:
        from life_world_model.collectors.git_activity import GitActivityCollector

        paths = settings.git_scan_paths or []
        c = GitActivityCollector(paths)
        path_desc = ", ".join(str(p) for p in paths) if paths else "(none)"
        source_info.append(("git", c.is_available(), path_desc))
    except ImportError:
        path_desc = ", ".join(str(p) for p in (settings.git_scan_paths or [])) or "(none)"
        source_info.append(("git", False, path_desc + " (module not installed)"))

    try:
        from life_world_model.collectors.calendar import CalendarCollector

        c = CalendarCollector(settings.calendar_path)
        source_info.append(("calendar", c.is_available(), str(settings.calendar_path)))
    except ImportError:
        source_info.append(("calendar", False, str(settings.calendar_path) + " (module not installed)"))

    # Find the longest source name for alignment
    max_name = max(len(name) for name, _, _ in source_info) if source_info else 0

    print("Available collectors:")
    for name, available, path in source_info:
        status = "\u2713" if available else "\u2717"
        # Shorten home directory for display
        display_path = path.replace(str(__import__("pathlib").Path.home()), "~")
        print(f"  {name:<{max_name}}  {status}  {display_path}")

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

    collect_parser = subparsers.add_parser("collect", help="Collect one day of activity from all sources")
    collect_parser.add_argument("--date", default=None, dest="date_value", help="Date in YYYY-MM-DD format (required unless --backfill)")
    collect_parser.add_argument("--demo", action="store_true", help="Use bundled demo data instead of real sources")
    collect_parser.add_argument("--source", default=None, help="Collect from a single source (e.g. chrome, shell, git)")
    collect_parser.add_argument(
        "--backfill",
        action="store_true",
        help="Collect backwards from today, stopping after 7 consecutive empty days",
    )

    generate_parser = subparsers.add_parser("generate", help="Generate one day narrative")
    generate_parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")

    run_parser = subparsers.add_parser("run", help="Collect then generate")
    run_parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")
    run_parser.add_argument("--demo", action="store_true", help="Use bundled demo data instead of real sources")
    run_parser.add_argument("--source", default=None, help="Collect from a single source (e.g. chrome, shell, git)")

    subparsers.add_parser("sources", help="List all collectors, their availability, and data paths")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "collect":
        if getattr(args, "backfill", False):
            return run_backfill(source=getattr(args, "source", None))
        if not args.date_value:
            parser.error("--date is required (unless using --backfill)")
        return run_collect(args.date_value, use_demo=args.demo, source=args.source)
    if args.command == "generate":
        return run_generate(args.date_value)
    if args.command == "run":
        status = run_collect(args.date_value, use_demo=args.demo, source=getattr(args, "source", None))
        if status != 0:
            return status
        return run_generate(args.date_value)
    if args.command == "sources":
        return run_sources()

    parser.error(f"Unknown command: {args.command}")
    return 2


def collect_entrypoint() -> int:
    parser = argparse.ArgumentParser(description="Collect one day of activity from all sources")
    parser.add_argument("--date", default=None, dest="date_value", help="Date in YYYY-MM-DD format (required unless --backfill)")
    parser.add_argument("--demo", action="store_true", help="Use bundled demo data instead of real sources")
    parser.add_argument("--source", default=None, help="Collect from a single source (e.g. chrome, shell, git)")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Collect backwards from today, stopping after 7 consecutive empty days",
    )
    args = parser.parse_args()
    if args.backfill:
        return run_backfill(source=args.source)
    if not args.date_value:
        parser.error("--date is required (unless using --backfill)")
    return run_collect(args.date_value, use_demo=args.demo, source=args.source)


def generate_entrypoint() -> int:
    parser = argparse.ArgumentParser(description="Generate one day narrative")
    parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")
    args = parser.parse_args()
    return run_generate(args.date_value)


def run_entrypoint() -> int:
    parser = argparse.ArgumentParser(description="Collect then generate one day narrative")
    parser.add_argument("--date", required=True, dest="date_value", help="Date in YYYY-MM-DD format")
    parser.add_argument("--demo", action="store_true", help="Use bundled demo data instead of real sources")
    parser.add_argument("--source", default=None, help="Collect from a single source (e.g. chrome, shell, git)")
    args = parser.parse_args()
    argv = ["run", "--date", args.date_value]
    if args.demo:
        argv.append("--demo")
    if args.source:
        argv.extend(["--source", args.source])
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
