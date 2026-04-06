# Life World Model — Project CLAUDE.md

> TikTok-level personal behavior engine. Collects everything you touch on macOS, discovers patterns, simulates habit changes, scores days against goals, generates actionable suggestions.

## Commands

```bash
# Dev
uv run pytest tests/ -v              # run all tests
uv run python -m life_world_model.cli run --date 2026-04-06 --demo  # demo pipeline

# CLI (after install)
lwm sources                           # list available collectors + status
lwm collect --date 2026-04-06         # collect from all sources
lwm collect --backfill                # mine all available history
lwm generate --date 2026-04-06        # generate narrative
lwm run --date 2026-04-06             # collect + generate
lwm goals progress                    # score today against goals
lwm patterns --show                   # display discovered patterns
lwm simulate "Code 8-10am before email"  # what-if simulation
lwm suggest --detail                  # data-derived suggestions
lwm watch                             # start background daemon
```

## Stack

- **Language:** Python 3.11+
- **Package manager:** uv
- **Database:** SQLite (stdlib, no ORM)
- **LLM:** Gemini (cloud) or MLX (local) — optional deps
- **Dependencies:** Zero required. LLM providers are optional extras.
- **Tests:** pytest

## Architecture Rules

### Collectors
- Every collector extends `BaseCollector` from `collectors/base.py`
- Every collector implements: `collect_for_date(date) -> list[RawEvent]`, `is_available() -> bool`, `source_name -> str`
- Copy locked databases to temp before querying (Chrome, knowledgeC, Calendar all lock their DBs)
- Register in `COLLECTOR_REGISTRY` via decorator
- Each collector gets its own test file with fixture data (never real user data in tests)

### Pattern Discovery
- **Statistics discover patterns. LLM only translates them to language.**
- Never let the LLM invent patterns not supported by the data
- Anti-hallucination instruction in every LLM prompt
- Pattern evidence must include specific numbers (counts, percentages, days observed)

### Scoring Formula (TikTok Algo 101 inspired)
```
DayScore = sum(metric_value_i * goal_weight_i)
```
- Metrics are computed from LifeState signals (focus hours, context switches, goal alignment)
- Weights are user-configurable via `lwm goals`
- Temporal decay: `weight = e^(-0.693 * days_ago / half_life)`, default half_life=14 days

### Data Privacy
- All collection is hyperlocal (local files/databases only, no cloud APIs for data)
- LLM prompts can go to cloud (Gemini) but raw event data stays on disk
- `data/` directory is gitignored — never commit user activity data
- `.env` is gitignored — never commit API keys
- `--demo` flag exists for sharing/testing without personal data

### Timestamp Epochs
- **Chrome:** Windows FILETIME epoch (1601-01-01), microseconds
- **knowledgeC / Calendar:** Mac epoch (2001-01-01), seconds
- **zsh_history:** Unix epoch (1970-01-01), seconds
- **Git:** ISO 8601 strings
- Always convert to Python `datetime` with timezone before storing

### Storage
- Single SQLite database at `data/raw/life_world_model.sqlite3`
- Migrations are additive-only (ALTER TABLE ADD COLUMN, never DROP)
- Check column existence with `PRAGMA table_info()` before migrating
- Deduplication on `(timestamp, source, title)` tuple

## Key Files

```
src/life_world_model/
  types.py                  # RawEvent, LifeState, Pattern, Suggestion, Goal
  config.py                 # Settings + env loading
  cli.py                    # All CLI commands
  collectors/
    base.py                 # BaseCollector ABC + registry
    chrome_history.py       # Chrome SQLite (Windows FILETIME epoch)
    knowledgec.py           # macOS knowledgeC.db (Mac epoch)
    shell_history.py        # ~/.zsh_history parser
    git_activity.py         # git log across ~/Projects/
    calendar.py             # Apple Calendar SQLite (Mac epoch)
  pipeline/
    bucketizer.py           # 15-min bucketing + multi-source activity classifier
    signals.py              # TikTok-style behavioral signal extraction
    generator.py            # LLM narrative generation
  goals/
    engine.py               # User goals + V-weights
  scoring/
    formula.py              # Day scoring + temporal decay
  analysis/
    pattern_discovery.py    # 5 statistical detectors (no ML)
    narrator.py             # LLM pattern narration
    suggestions.py          # Data-derived suggestion generator
  simulation/
    types.py                # Intervention, SimulationResult
    engine.py               # What-if with formula scoring + LLM narration
  daemon/
    collector.py            # Background collection + hourly pattern refresh
  notifications/
    macos.py                # macOS notification system
    briefing.py             # Daily morning briefing
  storage/
    sqlite_store.py         # SQLite persistence + migrations
```

## Build Plan

See `docs/ULTRAPLAN-BRIEF.md` for full context and `.claude/plans/` for the active implementation plan.

**Parallel build via worktrees:**
- Wave 1: types/storage + all 5 collectors + goals (6 parallel agents)
- Wave 2: bucketing + signals + daemon + patterns (4 parallel agents)
- Wave 3: simulation + suggestions + notifications (3 parallel agents)
- Wave 4: CLI wiring + configurable voice

## User Context

See local planning docs (gitignored) for personal goals and preferences.
Optimization weights: alignment=0.4, energy=0.3, flow=0.3.
