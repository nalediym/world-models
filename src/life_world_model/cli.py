from __future__ import annotations

import argparse
from datetime import date, timedelta
from typing import Sequence

from life_world_model.config import Settings, load_settings
from life_world_model.demo_data import build_demo_events
from life_world_model.pipeline.bucketizer import build_life_states
from life_world_model.pipeline.generator import (
    generate_with_cli,
    generate_with_gemini,
    generate_with_mlx,
    render_fallback_markdown,
    render_narrative_markdown,
    write_rollout,
)
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.analysis.pattern_discovery import discover_patterns
from life_world_model.analysis.suggestions import generate_suggestions
from life_world_model.analysis.narrator import narrate_patterns
from life_world_model.daemon.collector import run_daemon
from life_world_model.goals.engine import load_goals
from life_world_model.notifications.briefing import morning_briefing
from life_world_model.scoring.formula import format_score_report, score_day
from life_world_model.simulation.engine import simulate


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
        name = collector.source_name
        if not collector.is_available():
            print(f"  {name:12s} ✗ unavailable (check lwm sources for details)")
            continue
        try:
            events = collector.collect_for_date(target_date)
            store.save_raw_events(events)
            if events:
                print(f"  {name:12s} {len(events)} events")
            else:
                print(f"  {name:12s} 0 events (no activity on {target_date})")
            total += len(events)
        except PermissionError:
            print(f"  {name:12s} ✗ permission denied (grant Full Disk Access in System Settings)")
        except Exception as e:
            print(f"  {name:12s} ✗ error — {e}")

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

    if settings.llm_provider in ("gemini-cli", "claude-cli"):
        cli_cmd = settings.llm_provider.replace("-cli", "")
        try:
            print(f"Generating narrative with {cli_cmd} CLI ...")
            prose = generate_with_cli(states, target_date, cli_cmd)
            return render_narrative_markdown(target_date, states, prose)
        except FileNotFoundError:
            print(f"{cli_cmd} CLI not found in PATH — falling back to timeline output.")
            return render_fallback_markdown(target_date, states)
        except Exception as e:
            print(f"{cli_cmd} CLI error: {e} — falling back to timeline output.")
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


def run_patterns(
    start_date: str | None = None,
    end_date: str | None = None,
    show_only: bool = False,
) -> int:
    settings = load_settings()
    store = SQLiteStore(settings.database_path)

    if show_only:
        # Load events for full range and display discovered patterns
        end = date.today()
        start = end - timedelta(days=30)
        events = store.load_raw_events_for_range(start, end + timedelta(days=1))
        if not events:
            print("No data found. Run 'lwm collect' first.")
            return 0
        multi_day_states: dict[date, list] = {}
        from collections import defaultdict

        day_events: dict[date, list] = defaultdict(list)
        for event in events:
            day_events[event.timestamp.date()].append(event)
        for day, day_evts in sorted(day_events.items()):
            states = build_life_states(day_evts, bucket_minutes=settings.bucket_minutes)
            if states:
                multi_day_states[day] = states
        patterns = discover_patterns(multi_day_states)
        if not patterns:
            print("No patterns found in the data.")
            return 0
        text = narrate_patterns(patterns)
        print(text)
        return 0

    end = parse_date(end_date) if end_date else date.today()
    start = parse_date(start_date) if start_date else end - timedelta(days=30)

    multi_day_states = {}
    current = start
    while current <= end:
        events = store.load_raw_events_for_date(current)
        if events:
            states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
            if states:
                multi_day_states[current] = states
        current += timedelta(days=1)

    if not multi_day_states:
        print(f"No data found for {start} to {end}. Run 'lwm collect' first.")
        return 0

    patterns = discover_patterns(multi_day_states)

    if not patterns:
        print(f"No patterns discovered from {len(multi_day_states)} days of data.")
        return 0

    for p in patterns:
        print(f"  [{p.category}] {p.name} (confidence: {p.confidence:.0%}, {p.days_observed} days)")
        print(f"    {p.description}")

    print(f"\nDiscovered {len(patterns)} patterns from {len(multi_day_states)} days of data.")
    return 0


def run_goals(subcmd: str = "list") -> int:
    """Show goals or score today's progress against them."""
    if subcmd == "list":
        goals = load_goals()
        print("Current goals:")
        for g in goals:
            print(f"  {g.name:20s} weight={g.weight:.0%}  metric={g.metric}")
            print(f"    {g.description}")
        return 0

    if subcmd == "progress":
        settings = load_settings()
        store = SQLiteStore(settings.database_path)
        today = date.today()
        events = store.load_raw_events_for_date(today)
        states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
        goals = load_goals()
        result = score_day(states, goals)
        print(format_score_report(result, today))
        return 0

    print(f"Unknown goals subcommand: {subcmd}. Use 'list' or 'progress'.")
    return 2


def run_simulate(text: str, baseline_date: str | None = None) -> int:
    """Run a what-if simulation against baseline data."""
    settings = load_settings()
    store = SQLiteStore(settings.database_path)

    bl_date = parse_date(baseline_date) if baseline_date else None
    result = simulate(store, settings, text, baseline_date=bl_date)
    print(result.summary)
    return 0


def run_suggest(detail: bool = False) -> int:
    """Generate suggestions from discovered patterns."""
    settings = load_settings()
    store = SQLiteStore(settings.database_path)

    end = date.today()
    start = end - timedelta(days=30)

    multi_day_states: dict[date, list] = {}
    current = start
    while current <= end:
        events = store.load_raw_events_for_date(current)
        if events:
            states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
            if states:
                multi_day_states[current] = states
        current += timedelta(days=1)

    if not multi_day_states:
        print("No data found. Run 'lwm collect' first.")
        return 0

    patterns = discover_patterns(multi_day_states)
    if not patterns:
        print("No patterns found — cannot generate suggestions yet.")
        return 0

    suggestions = generate_suggestions(patterns)
    if not suggestions:
        print("No actionable suggestions from current patterns.")
        return 0

    for i, s in enumerate(suggestions, 1):
        print(f"{i}. [{s.predicted_impact.upper()}] {s.title}")
        print(f"   {s.rationale}")
        if detail:
            print(f"   Type: {s.intervention_type} | Delta: {s.score_delta:+.1%}")
            print(f"   Based on: {', '.join(s.source_patterns)}")
        print()

    return 0


def run_watch(interval: int = 60) -> int:
    """Run the daemon loop (foreground)."""
    run_daemon(interval_minutes=interval)
    return 0


def run_briefing() -> int:
    """Send the morning briefing notification."""
    text = morning_briefing()
    print(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Personal life world model MVP CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="Collect one day of activity from all sources")
    collect_parser.add_argument("--date", default=date.today().isoformat(), dest="date_value", help="Date in YYYY-MM-DD format (default: today)")
    collect_parser.add_argument("--demo", action="store_true", help="Use bundled demo data instead of real sources")
    collect_parser.add_argument("--source", default=None, help="Collect from a single source (e.g. chrome, shell, git)")
    collect_parser.add_argument(
        "--backfill",
        action="store_true",
        help="Collect backwards from today, stopping after 7 consecutive empty days",
    )

    generate_parser = subparsers.add_parser("generate", help="Generate one day narrative")
    generate_parser.add_argument("--date", default=date.today().isoformat(), dest="date_value", help="Date in YYYY-MM-DD format (default: today)")

    run_parser = subparsers.add_parser("run", help="Collect then generate")
    run_parser.add_argument("--date", default=date.today().isoformat(), dest="date_value", help="Date in YYYY-MM-DD format (default: today)")
    run_parser.add_argument("--demo", action="store_true", help="Use bundled demo data instead of real sources")
    run_parser.add_argument("--source", default=None, help="Collect from a single source (e.g. chrome, shell, git)")

    subparsers.add_parser("sources", help="List all collectors, their availability, and data paths")

    patterns_parser = subparsers.add_parser(
        "patterns", help="Discover behavioral patterns from collected data"
    )
    patterns_parser.add_argument(
        "--range",
        nargs=2,
        metavar=("START", "END"),
        dest="date_range",
        default=None,
        help="Date range in YYYY-MM-DD format (default: last 30 days)",
    )
    patterns_parser.add_argument(
        "--show",
        action="store_true",
        dest="show_only",
        help="Display patterns with narrative summary",
    )

    goals_parser = subparsers.add_parser("goals", help="View goals or score today's progress")
    goals_parser.add_argument(
        "goals_subcmd",
        nargs="?",
        default="list",
        choices=["list", "progress"],
        help="Subcommand: list (default) or progress",
    )

    simulate_parser = subparsers.add_parser(
        "simulate", help="Run a what-if simulation"
    )
    simulate_parser.add_argument(
        "scenario", help="Natural language scenario (e.g. 'code from 8-10am')"
    )
    simulate_parser.add_argument(
        "--baseline",
        default=None,
        dest="baseline_date",
        help="Baseline date in YYYY-MM-DD format (default: best of last 7 days)",
    )

    suggest_parser = subparsers.add_parser(
        "suggest", help="Generate actionable suggestions from patterns"
    )
    suggest_parser.add_argument(
        "--detail",
        action="store_true",
        help="Show intervention type, score delta, and source patterns",
    )

    watch_parser = subparsers.add_parser(
        "watch", help="Run the collection daemon (foreground)"
    )
    watch_parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Collection interval in minutes (default: 60)",
    )

    subparsers.add_parser("briefing", help="Send the morning briefing notification")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "collect":
        if getattr(args, "backfill", False):
            return run_backfill(source=getattr(args, "source", None))
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
    if args.command == "patterns":
        date_range = getattr(args, "date_range", None)
        start = date_range[0] if date_range else None
        end = date_range[1] if date_range else None
        return run_patterns(
            start_date=start,
            end_date=end,
            show_only=getattr(args, "show_only", False),
        )
    if args.command == "goals":
        return run_goals(getattr(args, "goals_subcmd", "list"))
    if args.command == "simulate":
        return run_simulate(
            args.scenario,
            baseline_date=getattr(args, "baseline_date", None),
        )
    if args.command == "suggest":
        return run_suggest(detail=getattr(args, "detail", False))
    if args.command == "watch":
        return run_watch(interval=getattr(args, "interval", 60))
    if args.command == "briefing":
        return run_briefing()

    parser.error(f"Unknown command: {args.command}")
    return 2


def collect_entrypoint() -> int:
    parser = argparse.ArgumentParser(description="Collect one day of activity from all sources")
    parser.add_argument("--date", default=date.today().isoformat(), dest="date_value", help="Date in YYYY-MM-DD format (default: today)")
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
    return run_collect(args.date_value, use_demo=args.demo, source=args.source)


def generate_entrypoint() -> int:
    parser = argparse.ArgumentParser(description="Generate one day narrative")
    parser.add_argument("--date", default=date.today().isoformat(), dest="date_value", help="Date in YYYY-MM-DD format (default: today)")
    args = parser.parse_args()
    return run_generate(args.date_value)


def run_entrypoint() -> int:
    parser = argparse.ArgumentParser(description="Collect then generate one day narrative")
    parser.add_argument("--date", default=date.today().isoformat(), dest="date_value", help="Date in YYYY-MM-DD format (default: today)")
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
