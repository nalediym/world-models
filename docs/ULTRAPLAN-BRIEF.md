# Life World Model: Full Planning Context & Implementation Brief

> This document captures the COMPLETE context from a deep planning session. It includes the user interview, data source discovery, existing codebase analysis, the full 6-phase implementation plan, TikTok recommendation system analysis, and open questions. Use this as the single source of truth for any planning or implementation session.

---

## Table of Contents

1. [Project Vision](#1-project-vision)
2. [User Interview Transcript](#2-user-interview-transcript)
3. [What Exists Today — Current MVP](#3-what-exists-today--current-mvp)
4. [Data Source Discovery — What's On This Mac](#4-data-source-discovery--whats-on-this-mac)
5. [macOS Local Data APIs — Technical Feasibility Research](#5-macos-local-data-apis--technical-feasibility-research)
6. [TikTok Recommendation System Analysis](#6-tiktok-recommendation-system-analysis)
7. [Implementation Plan — All 6 Phases](#7-implementation-plan--all-6-phases)
8. [File Summary — New and Modified Files](#8-file-summary--new-and-modified-files)
9. [Existing Codebase Reference](#9-existing-codebase-reference)
10. [Open Questions for Interview](#10-open-questions-for-interview)

---

## 1. Project Vision

A **hyperlocal personal behavior model** that runs entirely on the user's Mac. It collects everything they touch digitally, discovers behavioral patterns with TikTok-level personalization depth, simulates habit changes ("what if I coded before email?"), and generates actionable suggestions to improve their day.

### Core Principles

- **Hyperlocal**: All data collection from local files and databases on the Mac. No cloud APIs for data. Data never leaves the machine for storage.
- **LLM can be cloud**: Sending prompts to Gemini/Claude for generation is OK, as long as raw personal data stays local.
- **Automate everything**: The user will grant whatever macOS permissions are needed. Zero manual export steps.
- **Pattern-based prediction from OWN data**: Learn from the USER's historical behavior, not generic sleep science or productivity research.
- **TikTok-level personalization**: Attention prediction, behavioral feedback loops, deep personal modeling — the model should know the user so well it can predict their day.
- **All habit types**: Time blocking, elimination/limits, adding new activities — mix and match freely.
- **CLI-first, web UI later**: Start with terminal commands, add a visual layer once the engine works.
- **Success = actionable suggestions**: The system should analyze patterns and recommend specific changes with predicted impact that actually change daily behavior.
- **As much history as possible**: Mine all available historical data from every source.

---

## 2. User Interview Transcript

### Round 1: Data Sources

**Q: What data from your laptop do you most want to feed into your world model?**

A: ALL of them — Chrome/browser history, calendar & schedule, Screen Time / app usage, health & sleep data. Plus: "My whole filesystem... everything that I touch... I want everything."

### Round 2: Habit Types

**Q: When you say 'play around with different habits', what kind of changes do you want to explore?**

A: All of the above — time blocking (rearranging when you do things), elimination/limits (removing or capping activities), AND adding new activities. Mix and match freely.

### Round 3: Interface

**Q: How do you want to interact with the simulation results?**

A: Both — CLI first to prove the simulation works, then add a visual layer (local web UI) later.

### Round 4: Success Criteria

**Q: What does a winning outcome look like for you?**

A: Get actionable suggestions — the model analyzes patterns and recommends specific habit changes with predicted impact. Not just "here's your day" but "here's what you should change and why."

### Round 5: Filesystem Signals

**Q: For 'everything I touch' — which filesystem signals matter most?**

A: ALL of them — files opened/modified, git activity, app launches & switches, terminal commands. Plus: "Anything else that was used previously in other projects that exist out there... also look at recommendation systems and what they use / track... specifically TikTok... they are the best."

### Round 6: Data Access

**Q: For health & calendar data, how do you currently access it?**

A: Mix of sources (Google Calendar + Apple Calendar + Apple Health + wearable). "Everything should be hyperlocal... do not make stuff up. If you don't know what I mean, ask."

### Round 7: Prediction Model

**Q: For the simulation engine — how should it predict 'what-if' outcomes?**

A: Pattern-based (learn from YOUR data) — "when you code in morning, you tend to be more productive in afternoon" — from the user's own history. Not generic research.

### Round 8: History Depth

**Q: How much historical data do you want to start with?**

A: As much as possible — mine all available history from Chrome, git, shell, etc.

### Round 9: TikTok Reference

**Q: The TikTok reference — what aspect of their approach resonates?**

A: ALL of these — attention prediction, behavioral feedback loops (what leads to what), AND deep personalization. The full stack.

### Round 10: Hyperlocal Definition

**Q: Is hyperlocal = fully local including LLM inference?**

A: Data local, LLM can be cloud — data never leaves the machine for storage, but it's OK to send prompts to Gemini/Claude for generation.

### Round 11: Priority

**Q: What's your priority for the first buildable milestone?**

A: Multi-source collection — get ALL data sources flowing in first, then worry about simulation.

### Round 12: Wearable

**Q: I found no wearable app data on your Mac. Do you use one?**

A: No wearable currently — skip biometric data for now, focus on digital activity signals.

### Round 13: Journaling

**Q: I found Daylio (mood/journaling) in your iCloud. Do you use it?**

A: Used to, stopped — maybe the world model could help restart the habit.

### Round 14: Effort Level

**Q: What's your energy level for data collection setup?**

A: Automate everything — build collectors that grab all data automatically. Will grant whatever permissions are needed.

---

## 3. What Exists Today — Current MVP

### Project Overview

**Personal Life World Model**: a local-first tool that turns desktop activity (Chrome history) into Tolkien-esque day narratives. The project lives at `/Users/naledi/Projects/world-models`.

**Status (as of 2026-03-22):** MVP scaffold is functional. The collect→bucket→output pipeline works end-to-end with tests passing. LLM narrative generation is wired up with Gemini and MLX.

**Tech stack:** Python 3.11+, SQLite, uv package manager, CLI-only, markdown output.

**Codebase:** ~470 lines across 8 files. Clean, minimal, tested. 8 tests all passing.

### Project Structure

```
/Users/naledi/Projects/world-models/
├── src/life_world_model/                    # Main package
│   ├── __init__.py
│   ├── types.py                             # Core dataclasses (RawEvent, LifeState, NarrativeFrame)
│   ├── config.py                            # Configuration & env loader
│   ├── cli.py                               # CLI entrypoint (3 commands)
│   ├── demo_data.py                         # Bundled demo events for testing
│   ├── collectors/
│   │   ├── __init__.py
│   │   └── chrome_history.py                # Chrome history collector (ONLY current data source)
│   ├── storage/
│   │   ├── __init__.py
│   │   └── sqlite_store.py                  # SQLite persistence for raw events
│   └── pipeline/
│       ├── __init__.py
│       ├── bucketizer.py                    # Temporal bucketing (15-min windows) + activity inference
│       └── generator.py                     # LLM generation (Gemini or MLX) + markdown output
├── tests/
│   ├── conftest.py                          # Pytest configuration
│   ├── test_bucketizer.py                   # 3 tests for bucketing logic
│   ├── test_demo_mode.py                    # 2 tests for demo data
│   └── test_generator_prompt.py             # 3 tests for prompt building
├── docs/
│   ├── design/
│   │   ├── RUTHLESS-MVP.md                  # Philosophy & ruthless scope definition
│   │   ├── PYTHON-MVP-BUILD-PLAN.md         # Concrete Python implementation roadmap
│   │   └── MVP-IMPLEMENTATION-BLUEPRINT.md  # Comprehensive 2000-line blueprint with research grounding
│   └── research/
│       ├── world-models-landscape.md        # Landscape survey of world model research
│       └── RHODA_DVA_INVESTIGATION.md       # Research investigation validating text-based world models
├── data/
│   ├── raw/                                 # (gitignored) SQLite database for collected events
│   └── processed/
│       └── rollouts/                        # Generated markdown narratives (2 samples present)
├── pyproject.toml                           # Package config, dependencies, CLI entrypoints
├── pyrightconfig.json                       # Python type checking config
├── .env.example                             # Template for GEMINI_API_KEY
├── .env                                     # (gitignored) actual API key
├── README.md                                # User-facing overview
├── QUICKSTART.md                            # Setup & usage instructions
├── .gitignore                               # Excludes data/, .env, .claude/
└── uv.lock                                  # Dependency lock file
```

### Pipeline Architecture

The system flows through three stages:

#### Stage 1: Collection (`collect` command)
```
Chrome History (on disk at ~/Library/Application Support/Google/Chrome/Default/History)
    ↓ [ChromeHistoryCollector — copies DB to temp, queries visits table]
    ↓ [Chrome timestamps use Windows FILETIME epoch: 1601-01-01, microseconds]
RawEvent objects (timestamp, source="chrome", title, domain, url)
    ↓ [SQLiteStore.save_raw_events()]
SQLite table: raw_events (id, timestamp TEXT, source TEXT, title, domain, url)
```

#### Stage 2: Bucketing (`generate` command)
```
Raw events loaded from SQLite for target date
    ↓ [bucketizer.build_life_states()]
    ↓ floor each event timestamp to nearest 15-min boundary
    ↓ group events by bucket
    ↓ infer_activity() — keyword matching on domains & titles:
    ↓   "github/arxiv/paper/docs/search" → research (0.80 confidence)
    ↓   "cursor/vscode/code/pull request/commit" → coding (0.75)
    ↓   "mail/gmail/slack/message/chat" → communication (0.75)
    ↓   fallback → browsing (0.55)
    ↓   empty bucket → idle (0.20)
    ↓ fill gaps between first and last event with idle states
LifeState objects (timestamp, primary_activity, secondary_activity, domain, event_count, confidence)
```

#### Stage 3: Narrative Generation
```
LifeState timeline
    ↓ [build_prompt() — system instruction + timeline + anti-hallucination warning]
    ↓ System: "Narrator in J.R.R. Tolkien's style. Transform computer activity logs 
    ↓          into rich, grounded fantasy prose. Stay faithful to timeline. 
    ↓          No invented activities. 200-400 words. Past tense. No headings/bullets."
    ↓ User: Timeline of 15-min states (one per line)
    ↓ Anti-hallucination: "Do not invent major activities not supported by data."
    ↓ [generate_with_gemini() or generate_with_mlx() — cloud or local inference]
    ↓ [render_narrative_markdown() or render_fallback_markdown()]
Markdown file at data/processed/rollouts/YYYY-MM-DD_narrative.md
```

### Core Data Types

```python
# src/life_world_model/types.py

@dataclass
class RawEvent:
    timestamp: datetime
    source: str                           # "chrome" or "demo"
    title: str | None = None              # Page title
    domain: str | None = None             # Extracted domain
    url: str | None = None                # Full URL

@dataclass
class LifeState:
    timestamp: datetime                   # Bucket start time (15-min aligned)
    primary_activity: str                 # "research", "coding", "communication", "browsing", "idle"
    secondary_activity: str | None        # Domain or detail
    domain: str | None                    # Top domain in bucket
    event_count: int                      # Num events in bucket
    confidence: float                     # 0.0-1.0 activity confidence

@dataclass
class NarrativeFrame:
    timestamp: datetime
    narrative: str                        # Prose sentence(s)
```

### Configuration

```python
# src/life_world_model/config.py

@dataclass
class Settings:
    database_path: Path = Path("data/raw/life_world_model.sqlite3")
    output_dir: Path = Path("data/processed/rollouts")
    chrome_history_path: Path = Path.home() / "Library/Application Support/Google/Chrome/Default/History"
    bucket_minutes: int = 15
    llm_provider: str = "gemini"          # or "mlx"
    llm_model: str = "gemini-2.5-flash"
    gemini_api_key: str | None = None
```

Environment variables: `LWM_DATABASE_PATH`, `LWM_OUTPUT_DIR`, `LWM_CHROME_HISTORY_PATH`, `LWM_BUCKET_MINUTES`, `LWM_LLM_PROVIDER`, `LWM_LLM_MODEL`, `GEMINI_API_KEY`. Loaded from `.env` file via custom parser (no external deps).

### CLI Interface

```bash
lwm collect --date 2026-03-21 [--demo]   # Collect one day of Chrome history (or demo data)
lwm generate --date 2026-03-21           # Generate narrative from collected events
lwm run --date 2026-03-21 [--demo]       # Collect then generate in one command
```

Entry points defined in `pyproject.toml`: `lwm`, `lwm-collect`, `lwm-generate`, `lwm-run`.

### Storage Schema

```sql
-- src/life_world_model/storage/sqlite_store.py
CREATE TABLE IF NOT EXISTS raw_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,       -- ISO format datetime
  source TEXT NOT NULL,          -- "chrome" or "demo"
  title TEXT,
  domain TEXT,
  url TEXT
)
```

Single table. Timestamps as ISO strings. Schema auto-created on first save. Date range queries filter by ISO string comparison. Pure SQLite, no ORM.

### LLM Generation

**Primary: Gemini** — `google.genai` SDK, model `gemini-2.5-flash`, temperature 0.8, max 4096 tokens. Optional dependency: `pip install 'life-world-model[gemini]'`.

**Secondary: MLX** — `mlx_lm` SDK, runs on-device (Apple Silicon). Optional dependency: `pip install 'life-world-model[mlx]'`.

**Fallback**: If no API key or imports fail, generates a simple timeline markdown.

### Existing Tests (8 total, all passing)

- `test_bucketizer.py` (3): Window grouping, idle gap filling, GitHub activity labeling
- `test_demo_mode.py` (2): Demo data generation, demo data bucketization
- `test_generator_prompt.py` (3): Timeline ordering, anti-hallucination instruction, output path formatting

### Sample Output

```markdown
# Narrative for 2026-03-21

The sun, a pale eye in the heavens, had but newly risen on the twenty-first 
day of March when a quiet stirring began. As the hour struck eight, a mind 
turned its gaze to ancient scrolls and chronicles of example events...

---

## Timeline

- 08:00 research docs.example events=28 confidence=0.80
- 08:15 idle unknown events=0 confidence=0.20
- 08:30 research github.com events=14 confidence=0.80
...
```

### Design Philosophy

1. **Ruthless scope**: v0 reconstructs one observed day. Not predictive, not multiverse.
2. **Local-first**: Everything on disk. Chrome history and outputs gitignored. Privacy by design.
3. **Minimal dependencies**: Core package has zero deps. LLM providers are optional extras.
4. **15-minute bucketing**: Good default granularity. Configurable via `LWM_BUCKET_MINUTES`.
5. **Text-based world model**: Predicts narrative prose, not video. Grounded in UI-Simulator research.
6. **Heuristic activity inference**: Simple keyword matching. Fast, interpretable, debuggable.
7. **Grounded generation**: System prompt + anti-hallucination instruction keeps narrative faithful.

### Research Context

The project has extensive research docs:
- **RUTHLESS-MVP.md** (98 lines): Enforces scope discipline. In scope: one machine, one user, one data source, one day, one markdown output.
- **PYTHON-MVP-BUILD-PLAN.md** (359 lines): Implementation roadmap with concrete milestones.
- **MVP-IMPLEMENTATION-BLUEPRINT.md** (1991 lines): Research-grounded blueprint synthesizing Genie 3, Dreamer 4, World Labs, VERSES AI, UI-Simulator. Full system architecture with 4 layers, memory management, training paradigms, implementation phases v0-v3.
- **RHODA_DVA_INVESTIGATION.md**: Validates text-based world models. Architectural patterns: context amortization, inverse dynamics separation, long-context memory, leapfrog inference.
- **world-models-landscape.md**: Landscape survey of world model research.

---

## 4. Data Source Discovery — What's On This Mac

A thorough scan of the user's Mac found the following data sources:

### Accessible & Rich Data Sources

#### 1. Browser History (RICH — already implemented)
- **Path**: `/Users/naledi/Library/Application Support/Google/Chrome/Default/`
- **Files**:
  - `History` (38 MB) — Complete browsing history with timestamps
  - `History-journal` — Transaction log
  - `HistoryEmbeddings` (29 KB) — Embeddings of visited pages
  - `Cookies` (3.6 MB) — Session tracking
  - `Preferences` (509 KB) — Browser settings and behavior
  - `Web Data` (197 KB) — Form data
  - `Top Sites` (20 KB) — Frequently visited sites
  - `Bookmarks` (154 KB) — Long-term interests
  - `Sessions/` — Session history
  - `DownloadMetadata` — Download records
  - `Network Persistent State` (133 KB) — Tracking information

#### 2. Shell History (GOOD)
- **Path**: `~/.zsh_history` (96 KB) — Timestamped command history
- **Path**: `~/.bash_history` (2 KB) — Legacy bash history
- **Format**: `: EPOCH:0;command` (zsh extended history format)
- Shows technical patterns, projects, and workflows

#### 3. Application Usage Logs
- **VS Code sessions**: `/Users/naledi/Library/Application Support/Code/`
  - `User/` directory (user preferences and settings)
  - `logs/` directory
  - `WebStorage/` and `Local Storage/` (app state)
- **Claude AI sessions**: `/Users/naledi/Library/Application Support/Claude/`
  - `claude-code-sessions/` directory with session UUIDs
  - `config.json` (3.8 KB)

#### 4. Git Repository Activity (GOOD)
- **Path**: `/Users/naledi/Projects/` — 150+ project folders
- Git logs accessible via `git log` showing:
  - Commit timestamps
  - Commit messages (work pattern context)
  - Branch switching (project context switches)
- Recent commits show work on `world-models` project itself

#### 5. iCloud Synced Data (MODERATE)
- **Path**: `/Users/naledi/Library/Mobile Documents/`
- **iPhone app cloud backups** present for:
  - `iCloud~com~apple~iBooks` — Books being read
  - `iCloud~net~daylio~Daylio` — Mood/journaling app (empty/archived — user confirms they used to use it but stopped)
  - `iCloud~wtf~riedel~journaling` — Journaling app (empty/archived)
  - `iCloud~com~apple~notes` — Apple Notes
  - `iCloud~com~apple~reminders` — Reminders/tasks
  - Multiple messaging apps (WhatsApp, Telegram, Facebook Messenger, Slack)
  - Reading apps (LinkedIn, Reddit, Instagram)
  - Productivity apps (Asana, Trello, Notion)

#### 6. Spotlight Metadata (LIMITED)
- **Path**: `/Users/naledi/Library/Application Support/com.apple.spotlight/`
- `appList.dat` (369 KB) — App usage tracking
- `Resources.update_V3/` and `Resources_V3/` — Search index

### Restricted/Inaccessible Data (Permission Denied — user will grant permissions)

- **`~/Library/Biome/`** — macOS system intelligence data (protected, newer evolution of knowledgeC)
- **`~/Library/Calendars/`** — Calendar events (protected, needs Full Disk Access)
- **`~/Library/Application Support/Knowledge/knowledgeC.db`** — The GOLDMINE (see research section below)

### Not Found

- **Apple Health exports** — No direct health app exports on Mac (iOS only)
- **Wearable app data** (Oura, Whoop, Garmin, Fitbit) — No apps installed. **User confirmed: no wearable currently.**
- **Screen Time data** — Lives inside knowledgeC.db, not a separate source
- **Google Calendar exports** (.ics files) — No exports found

---

## 5. macOS Local Data APIs — Technical Feasibility Research

### 1. knowledgeC.db — App Usage & Screen Time (HIGHEST VALUE)

**Location**: `~/Library/Application Support/Knowledge/knowledgeC.db`

**What it tracks**:
- App focus/in-focus status (`/app/inFocus`) — which app was in the foreground and for how long
- Safari browsing history URLs (`/safari/history`)
- Device unlock events (`/device/unlocked`)
- Application usage patterns at precise timestamps
- Approximately **4 weeks of historical data**

**Database Structure**:
- Main table: `ZOBJECT` with thousands of entries
- Uses **Mac Epoch** (2001-01-01 00:00:00 UTC) for timestamps, stored as seconds in `ZCREATIONDATE`
- `ZSTREAMNAME` column identifies data type (e.g., `/app/inFocus`, `/safari/history`)
- `ZVALUESTRING` contains app bundle IDs or URLs
- Duration calculable from `ZENDDATE - ZCREATIONDATE`

**Python Access**:
- Directly query with `sqlite3` (stdlib — no deps needed)
- Must copy to temp file first (may be locked by the OS)
- **APOLLO** (Apple Pattern of Life Lazy Output'er) — Python utility with pre-built queries
- **ScreenTime2CSV** — Python script specifically for Screen Time export

**Timestamp conversion**: `datetime(2001, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=ZCREATIONDATE)`

**For This Project**: This is the single RICHEST local data source for behavioral signals. It tells you which app was in the foreground at every moment, with duration.

### 2. macOS Biome Data — Newer Evolution of knowledgeC

**Location**: `~/Library/Application Support/Biome/` (permission denied — user will grant)

**What it is**:
- Apple's newer system (macOS 13+) for collecting behavioral data
- Uses SEGB files (modular blobs) instead of monolithic SQLite
- Same purpose as knowledgeC but more modular and privacy-focused

**Data Types**: `/app/inFocus`, `/device/unlocked`, `/safari/history`, AppInstalls, AppLaunch, AppIntents

**Challenges**: Newer format, less documented, binary SEGB format requires parsing

**For This Project**: Future direction. Worth monitoring but knowledgeC.db is more accessible today.

### 3. Apple Calendar Data

**Options**:
- **SQLite Direct Access** (preferred for hyperlocal):
  - Calendar data stored in: `~/Library/Calendars/`
  - Database table: `ZCALENDARITEM`
  - Timestamps use Mac epoch (2001-01-01)
  - Can query with sqlite3 directly from Python
  - Needs Full Disk Access permission
- **EventKit Framework** (alternative):
  - Official Apple API for calendar access
  - Requires Objective-C/Swift bridge (pyobjc)

**For This Project**: Provides temporal structure and planned activities — valuable for comparing intention vs. actual behavior ("you had a meeting at 2pm but were browsing Twitter").

### 4. Apple HealthKit Data

**Limitation**: iOS only, NOT native macOS. The Mac doesn't have HealthKit locally — only iPhone does.

**How to get it on Mac**: Export from iPhone Health app → Share as XML → Parse on Mac.

**Python Parsing**: `apple-health-parser` (PyPI), `apple-health-exporter` (GitHub), or `xml.etree.ElementTree` into pandas.

**For This Project**: User has no wearable currently. Skip for now, add later if they get an Apple Watch.

### 5. File Access Patterns — FSEvents + Spotlight Metadata

**FSEvents** — Real-time file system events (create, delete, modify, rename):
- **Python library**: `MacFSEvents` (PyPI) — thread-safe directory observation with callbacks
- Provides: which files you edit, create, delete throughout the day
- Shows project context switches, cleanup behavior, time in directories

**Spotlight Metadata** — File creation date, modification date, size, kind, tags:
- **Python library**: `osxmetadata` (PyPI) — read/write Spotlight metadata and extended attributes
- **Python library**: `macos_mditem_metadata` (GitHub) — access all Spotlight metadata keys

**For This Project**: Excellent proxy for "what was I working on" without requiring explicit logging. Disambiguates app usage (coding vs. browsing in same app).

### 6. Shell History

**Location**: `~/.zsh_history` (96KB)
**Format**: `: EPOCH:0;command` (zsh extended history with timestamps)

**For This Project**: Shows terminal workflows, project switches, technical patterns. Zero-permission, zero-dependency collection.

### Feasibility Summary

| Data Source | Feasibility | Python Ease | Signal Quality | Role |
|-------------|-------------|------------|----------------|------|
| **knowledgeC.db** | Easy | Direct SQLite | Excellent | PRIMARY — app usage |
| **Chrome History** | Easy | Direct SQLite | Good | Already implemented |
| **Shell History** | Easy | Text parsing | Good | Technical workflow |
| **Git Repos** | Easy | subprocess | Good | Work patterns |
| **Apple Calendar** | Easy (needs perm) | Direct SQLite | Good | Planning layer |
| **FSEvents** | Easy | PyPI lib | Good | Real-time context |
| **Spotlight Metadata** | Easy | PyPI lib | Moderate | File context |
| **Biome** | Hard | Undocumented | Excellent | Future |
| **HealthKit** | iOS only | PyPI lib | Good | Skipped for now |

---

## 6. TikTok Recommendation System Analysis

The user specifically referenced TikTok as the gold standard for personalization. Here's the detailed mapping between TikTok's engineering and our plan.

### What TikTok Tracks (Behavioral Signals)

| Signal | How TikTok Uses It | Our Equivalent | Our Coverage |
|--------|-------------------|----------------|-------------|
| **Dwell time** | How long you watch each video — strongest positive signal | App focus duration from knowledgeC `ZENDDATE - ZCREATIONDATE` | Phase 2b |
| **Skip speed** | How fast you swipe away — strong negative signal | App switch-away speed (quick switch = disengagement) | Phase 2b |
| **Completion rate** | Did you watch the whole video? | Did the git commit happen? Did the file get saved? | Phase 2b |
| **Replay rate** | Rewatching = very strong interest | Same app/site reopened in same session | Phase 2b |
| **Session depth** | How long you stay in one content type | Consecutive same-activity buckets (deep work indicator) | Phase 2b |
| **Explicit feedback** | Likes, saves, comments | `lwm suggest --accept` tracks acceptance | Phase 5b |
| **Time-of-day** | When you engage with what content | Circadian rhythm detection from multi-day patterns | Phase 3b |
| **Hesitation** | Pausing before scrolling = mild interest | **NOT CAPTURED** — can't see in-app mouse/scroll behavior | Gap |
| **Scroll velocity** | Fast = browsing, slow = engaged | **NOT CAPTURED** — app-level, not pixel-level | Gap |
| **Content features** | Video content, audio, hashtags for cold start | File types, domains, commit messages for bootstrapping | Phase 2a |

### TikTok Engineering Pillars vs. Our Plan

#### Pillar 1: Signal Collection — OUR COVERAGE: 70%

**What we capture**: Dwell time, context switches (skip analog), session depth, completion signals, repeated access, time-of-day patterns, explicit feedback.

**What we miss**: In-app granularity. We see which app is focused, not what you're doing inside it. TikTok has pixel-level engagement data inside their app. We have OS-level app focus data. We're working at a coarser grain — more like "Netflix knows you watched this show for 2 hours" than "TikTok knows you paused at 0:03."

#### Pillar 2: Real-Time Model Updating — OUR COVERAGE: 20%

**TikTok**: Updates the model within ~100 interactions. New users get personalized feeds within 30 minutes. Online learning — adapts in near-real-time.

**Our plan**: Batch analysis. Patterns update when you run `lwm patterns`. No daemon that watches activity and refines patterns live. No feedback loop from suggestions — TikTok adjusts immediately when you skip, but our plan only tracks `--accept` without automatically re-weighting.

**To close this gap**: Add `lwm watch` daemon (Phase 6), feedback table (suggestion shown -> accepted/rejected -> did user actually change behavior?), pattern confidence decay over time.

#### Pillar 3: Sequence Modeling (A → B chains) — OUR COVERAGE: 80%

**TikTok**: Models "users who watched A then B tend to watch C."

**Our plan**: Phase 3b covers 2-bucket sequences (`activity_A at time_T → deep_work at time_T+1`), context-switching cost (how many buckets until recovery), and ripple effects in simulation. This IS sequence modeling at 15-minute granularity. This is the strongest TikTok-analogous part of the plan.

#### Pillar 4: Exploration vs. Exploitation — OUR COVERAGE: 30%

**TikTok**: Deliberately shows ~10-20% content outside your comfort zone to discover new interests. Actively tests hypotheses.

**Our plan**: Phase 5 suggests opportunities, Phase 4 simulates changes. But the system is passive — it waits for you to ask "what if?"

**A TikTok-level system would proactively say**: "I notice you've never tried coding before 9am. Based on your focus patterns, there's a 73% chance mornings would work better. Want to try it tomorrow and I'll measure the result?"

**To close this gap**: Add proactive experiment proposals ("try this for 3 days, I'll measure"), before/after comparison (detect behavior changes and measure outcomes), A/B testing against yourself.

#### Pillar 5: Cold Start — OUR COVERAGE: 100%

**TikTok**: Must learn new users from scratch using content features and demographics.

**Our advantage**: We skip cold start entirely. We have 4+ weeks of knowledgeC history, months/years of Chrome and git history, sitting on disk from day one.

#### Pillar 6: Multi-Objective Optimization — OUR COVERAGE: 20%

**TikTok**: Optimizes for multiple goals simultaneously — watch time, shares, follows, diverse content, creator ecosystem health.

**Our plan**: Phase 5 ranks suggestions by "predicted impact" but uses a single dimension.

**What's missing**: User-defined goals ("optimize for deep work", "limit social media", "break every 90 minutes"), multi-dimensional scoring of suggestions against all active goals, Pareto-optimal ranking.

**To close this gap**: Add `lwm goals set "maximize deep work" "limit social media to 1hr"`, score each suggestion against all active goals.

### Overall TikTok Coverage Score: ~50%

| Pillar | Coverage | Gap Severity |
|--------|----------|-------------|
| Signal Collection | 70% | Medium — limited by OS-level vs. in-app granularity |
| Real-Time Updating | 20% | High — batch vs. continuous learning |
| Sequence Modeling | 80% | Low — well covered |
| Explore/Exploit | 30% | Medium — passive vs. proactive |
| Cold Start | 100% | None — advantage |
| Multi-Objective | 20% | Medium — needs user goals |

### Three Highest-Impact Additions to Close the Gap

1. **User goals system** (easy, Phase 5 enhancement) — let user define what they're optimizing for
2. **Proactive experiment tracking** (medium, new Phase 5.5) — "try X for 3 days, I'll measure"
3. **Continuous learning daemon** (hard, Phase 6 upgrade) — `lwm watch` with live pattern refinement

---

## 7. Implementation Plan — All 6 Phases

### Phase 1: Multi-Source Collection (BUILD FIRST — user's explicit priority)

**Goal:** Get all local data sources flowing into the existing pipeline. The current bucketizer and generator work unchanged with richer input.

#### 1a. Collector base class + registry

**File:** `src/life_world_model/collectors/base.py` (new)

```python
from abc import ABC, abstractmethod
from datetime import date
from life_world_model.types import RawEvent

class BaseCollector(ABC):
    @abstractmethod
    def collect_for_date(self, target_date: date) -> list[RawEvent]: ...
    
    @abstractmethod
    def is_available(self) -> bool: ...
    
    @property
    @abstractmethod
    def source_name(self) -> str: ...

COLLECTOR_REGISTRY: dict[str, type[BaseCollector]] = {}

def register_collector(cls):
    COLLECTOR_REGISTRY[cls.source_name.fget(cls)] = cls  # or use a class-level attribute
    return cls
```

- Retrofit `ChromeHistoryCollector` to extend `BaseCollector`
- Each collector returns `RawEvent` objects (the existing type works for all sources)
- `is_available()` checks if the data source exists on this Mac (e.g., does knowledgeC.db exist?)
- Registry enables auto-discovery: iterate all registered collectors, skip unavailable ones

#### 1b. knowledgeC.db collector (HIGHEST VALUE — build this first within Phase 1)

**File:** `src/life_world_model/collectors/knowledgec.py` (new)

**Data source:** `~/Library/Application Support/Knowledge/knowledgeC.db`

**Implementation details:**
- Copy DB to temp file (like Chrome collector) since macOS may lock it
- Query `ZOBJECT` table for `/app/inFocus` entries in target date range
- Convert Mac epoch timestamps: `datetime(2001, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=ZCREATIONDATE)`
- Calculate dwell time from `ZENDDATE - ZCREATIONDATE` for each focus event
- Map bundle IDs to human-readable app names (maintain a lookup dict, e.g. `com.apple.Safari` → `Safari`, `com.microsoft.VSCode` → `VS Code`)
- Store as `RawEvent(source="knowledgec", title=app_name, domain=bundle_id, duration_seconds=dwell_time)`
- Also query `/safari/history` for Safari URL data (complements Chrome collector)
- Also query `/device/unlocked` for wake/sleep events

**Key SQL query:**
```sql
SELECT ZCREATIONDATE, ZENDDATE, ZSTREAMNAME, ZVALUESTRING
FROM ZOBJECT
WHERE ZSTREAMNAME = '/app/inFocus'
  AND ZCREATIONDATE >= ?  -- mac epoch start of day
  AND ZCREATIONDATE < ?   -- mac epoch start of next day
ORDER BY ZCREATIONDATE ASC
```

#### 1c. Shell history collector

**File:** `src/life_world_model/collectors/shell_history.py` (new)

**Data source:** `~/.zsh_history` (96KB on this Mac)

**Implementation details:**
- Read file line by line
- Parse zsh extended history format: `: EPOCH:DURATION;command`
- Convert Unix epoch to datetime
- Filter to target date
- Map to `RawEvent(source="shell", title=command_text, domain="terminal")`
- Handle multi-line commands (continuation lines don't start with `:`)

#### 1d. Git activity collector

**File:** `src/life_world_model/collectors/git_activity.py` (new)

**Data source:** `~/Projects/` (150+ repos on this Mac)

**Implementation details:**
- Configurable list of repo paths to scan (default: discover all `.git` dirs under `~/Projects/`)
- For each repo, run: `git log --all --format='%H|%aI|%s' --after=DATE --before=DATE`
- Parse commit hash, ISO timestamp, commit message
- Derive repo name from directory path
- Map to `RawEvent(source="git", title=commit_message, domain=repo_name, url=commit_hash)`
- Use `subprocess.run()` with timeout to avoid hanging on large repos

#### 1e. Apple Calendar collector

**File:** `src/life_world_model/collectors/calendar.py` (new)

**Data source:** `~/Library/Calendars/` (local CalendarAgent SQLite)

**Implementation details:**
- Find the Calendar.sqlitedb file (may be in subdirectory)
- Copy to temp (same pattern as Chrome/knowledgeC)
- Query `ZCALENDARITEM` table for events in date range
- Convert Mac epoch timestamps (2001-01-01)
- Extract event title, start/end times, calendar name
- Map to `RawEvent(source="calendar", title=event_title, domain=calendar_name, duration_seconds=event_duration)`
- Needs Full Disk Access permission (user confirmed they'll grant)

#### 1f. Extend RawEvent with optional metadata

**File:** `src/life_world_model/types.py` (modify)

Add two optional fields to `RawEvent`:
```python
@dataclass
class RawEvent:
    timestamp: datetime
    source: str
    title: str | None = None
    domain: str | None = None
    url: str | None = None
    duration_seconds: float | None = None  # NEW: dwell time from knowledgeC, event duration from calendar
    metadata: dict[str, str] | None = None  # NEW: source-specific extras (bundle_id, repo_path, etc.)
```

These are backwards-compatible (all optional with defaults).

#### 1g. Update storage for new fields

**File:** `src/life_world_model/storage/sqlite_store.py` (modify)

- Add `duration_seconds REAL` and `metadata TEXT` (JSON) columns to `raw_events` table
- Add a simple migration: check if columns exist with `PRAGMA table_info(raw_events)`, `ALTER TABLE ADD COLUMN` if missing
- Add `load_raw_events_for_range(start_date: date, end_date: date) -> list[RawEvent]` for multi-day queries
- Add deduplication: on save, skip events with same `(timestamp, source, title)` tuple (prevents double-counting on re-collection)

#### 1h. Update CLI for multi-source collection

**File:** `src/life_world_model/cli.py` (modify)

- `lwm collect --date 2026-04-06` now runs ALL available collectors via registry (not just Chrome)
- `lwm collect --date 2026-04-06 --source chrome` for single source
- `lwm collect --date 2026-04-06 --backfill` collects all available history (iterates days backwards from target date, stops when no events found for 7 consecutive days)
- `lwm sources` new subcommand: lists all registered collectors, their `is_available()` status, and the data path
- Per-source event count output: `Collected: 847 knowledgec, 234 chrome, 56 shell, 12 git, 8 calendar`

#### 1i. Update config for new data paths

**File:** `src/life_world_model/config.py` (modify)

Add paths:
```python
knowledgec_path: Path = Path.home() / "Library/Application Support/Knowledge/knowledgeC.db"
zsh_history_path: Path = Path.home() / ".zsh_history"
git_scan_paths: list[Path] = [Path.home() / "Projects"]
calendar_path: Path = Path.home() / "Library/Calendars"
```

With corresponding `LWM_KNOWLEDGEC_PATH`, `LWM_ZSH_HISTORY_PATH`, `LWM_GIT_SCAN_PATHS`, `LWM_CALENDAR_PATH` env vars.

#### 1j. Tests for new collectors

**New test files:**
- `tests/test_knowledgec.py` — Mac epoch timestamp conversion, ZOBJECT query parsing, bundle ID → app name mapping, `is_available()` when DB doesn't exist
- `tests/test_shell_history.py` — zsh history line parsing, multi-line command handling, date filtering
- `tests/test_git_activity.py` — git log output parsing, ISO timestamp handling, repo name extraction
- `tests/test_calendar.py` — Mac epoch conversion, event duration calculation, permission handling
- `tests/test_collector_registry.py` — registry auto-discovery, `is_available()` filtering

Use fixture data (not real user data) for all tests.

#### Phase 1 Verification
```bash
lwm sources                              # lists all collectors and availability status
lwm collect --date 2026-04-06            # collects from all available sources
lwm collect --date 2026-04-06 --backfill # mines all available history
lwm generate --date 2026-04-06           # generates narrative from multi-source data
pytest tests/ -v                         # all tests pass (old + new)
```

---

### Phase 2: Enhanced Bucketing + Behavioral Signals

**Goal:** Replace simple keyword matching with multi-source-aware activity inference. Add TikTok-style behavioral signals to each bucket.

#### 2a. Multi-source activity classifier

**File:** `src/life_world_model/pipeline/bucketizer.py` (modify `infer_activity`)

Replace the current keyword-matching with a priority cascade that uses the strongest signal available:

1. **Calendar event active?** → activity = meeting/event title (highest priority — user intended to be here)
2. **knowledgeC app focused?** → map bundle ID to activity category using a lookup table:
   - `com.microsoft.VSCode`, `com.todesktop.runtime.cursor` → "coding"
   - `com.apple.Safari`, `com.google.Chrome` → "browsing" (further disambiguated by URL)
   - `com.tinyspeck.slackmacgap`, `com.apple.MobileSMS` → "communication"
   - `com.apple.finder` → "file_management"
   - `com.apple.Terminal`, `com.googlecode.iterm2` → "terminal"
3. **Chrome/Safari URL?** → categorize by domain (current keyword matching, enhanced)
4. **Git commit in this bucket?** → "coding" with high confidence
5. **Shell command?** → "coding" or "system_admin" depending on command
6. **None of the above?** → "idle"

Each signal contributes a confidence score. When multiple signals agree, confidence increases. When they conflict, the higher-priority signal wins.

#### 2b. Behavioral signal extraction

**File:** `src/life_world_model/pipeline/signals.py` (new)

Extract per-bucket signals:

- **Dwell time** (`dwell_seconds`): Sum of `duration_seconds` from knowledgeC events in bucket. Direct measure of focused attention.
- **Context switch rate** (`context_switches`): Count distinct app transitions in bucket. Calculated from consecutive knowledgeC `/app/inFocus` events with different `ZVALUESTRING`. High value = distraction (TikTok skip analog).
- **Session depth** (`session_depth`): Count of consecutive buckets with the same `primary_activity`. Calculated after initial bucketing pass. Deep work = session_depth > 4 (1+ hours continuous).
- **Repeated access** (`repeat_count`): Number of times the same app/domain appears after a gap. High value = strong interest (TikTok replay analog).
- **Time-of-day deviation** (`tod_deviation`): How unusual this activity is for this time of day, based on historical averages. Requires multi-day data (Phase 3 provides baselines).
- **Completion signal** (`completed`): Boolean. True if a git commit, file save, or message send occurred. Indicates task completion (TikTok watch-through analog).

#### 2c. Extend LifeState with signals

**File:** `src/life_world_model/types.py` (modify)

```python
@dataclass
class LifeState:
    timestamp: datetime
    primary_activity: str
    secondary_activity: str | None
    domain: str | None
    event_count: int
    confidence: float
    # NEW fields (all optional for backwards compat):
    sources: list[str] | None = None           # which collectors contributed to this bucket
    dwell_seconds: float | None = None         # total focused time in bucket
    context_switches: int | None = None        # app transitions in bucket
    session_depth: int | None = None           # consecutive same-activity buckets
    repeat_count: int | None = None            # same app/domain revisits after gap
    completed: bool | None = None              # task completion signal
```

#### Phase 2 Verification
```bash
lwm run --date 2026-04-06                # narrative reflects multi-source signals
pytest tests/test_bucketizer.py -v       # updated + new tests pass
```

---

### Phase 3: Pattern Discovery Engine

**Goal:** Analyze multi-day historical data to find behavioral patterns. Statistics discover the patterns, LLM translates them to natural language.

#### 3a. New data types

**File:** `src/life_world_model/types.py` (add)

```python
@dataclass
class Pattern:
    name: str                    # "morning_research_routine"
    category: str                # "routine" | "correlation" | "rhythm" | "trigger" | "time_sink"
    description: str             # human-readable summary
    evidence: dict               # statistical backing (counts, percentages, p-values)
    confidence: float            # 0-1 based on consistency across observed days
    days_observed: int           # how many days this pattern held
    first_seen: date             # when pattern first appeared
    last_seen: date              # most recent observation

@dataclass  
class Suggestion:
    title: str                   # "Start coding before email"
    rationale: str               # why this might help, grounded in data
    intervention_type: str       # "reorder" | "eliminate" | "add" | "limit" | "time_block"
    source_patterns: list[str]   # pattern names that motivate this suggestion
    predicted_impact: str        # "high" | "medium" | "low"
    impact_evidence: str         # specific numbers: "40% fewer context switches when..."
```

#### 3b. Statistical pattern discovery

**File:** `src/life_world_model/analysis/pattern_discovery.py` (new)

Five pattern detectors, all using Python stdlib (no ML, no numpy required):

**1. Routine Detector**
- Input: Multi-day LifeState timelines
- Method: Group activities by (hour_of_day, day_of_week). Count frequency of each activity at each time slot.
- Output: `Pattern(category="routine")` for activities that appear in the same time slot on >60% of observed days.
- Example: "You research on GitHub/ArXiv between 8:00-9:00 on 78% of weekdays"

**2. Productivity Correlation Detector**
- Input: Multi-day LifeState timelines with behavioral signals
- Method: For each activity type, look at the NEXT bucket's signals. Build transition matrix: `P(deep_work_next | activity_current)`. Identify positive correlates (what precedes deep work) and negative correlates (what precedes scattered behavior).
- Output: `Pattern(category="correlation")` for statistically significant transitions.
- Example: "After morning coding sessions, your afternoon has 40% fewer context switches"

**3. Circadian Rhythm Detector**
- Input: Multi-day LifeState timelines with `context_switches` and `dwell_seconds`
- Method: Average `context_switches` and `dwell_seconds` by hour across all observed days. Find peaks (high focus) and valleys (scattered).
- Output: `Pattern(category="rhythm")` for focus peaks and valleys.
- Example: "Your peak focus window is 9:00-11:30. Context switching spikes at 14:00-15:00."

**4. Context-Switching Cost Detector**
- Input: Multi-day LifeState timelines with `context_switches` and `session_depth`
- Method: After buckets with high context_switches (>5), count how many buckets until the next session_depth > 2 (recovery to focused work).
- Output: `Pattern(category="trigger")` for recovery time measurements.
- Example: "After high-distraction periods, it takes you ~45 minutes to return to deep work"

**5. Time Sink Detector**
- Input: Multi-day LifeState timelines with `dwell_seconds` and `context_switches`
- Method: Rank activities by total hours. Flag activities with high total time + low average dwell per visit + high context switches (scrolling/browsing pattern — high time invested with fragmented attention).
- Output: `Pattern(category="time_sink")` for potential optimization targets.
- Example: "You spend 2.3 hours/day in Safari with an average session of 4 minutes and 12 context switches — classic scrolling pattern"

#### 3c. LLM pattern narration

**File:** `src/life_world_model/analysis/narrator.py` (new)

- Takes discovered `Pattern` objects with their statistical evidence
- Sends to LLM with a focused prompt: "Translate these behavioral patterns into clear, actionable insights. Include the specific numbers. Do not add patterns not supported by the data."
- LLM provides human interpretation and frames the patterns in an encouraging, actionable way
- LLM does NOT discover patterns (that's the statistics' job — keeps it grounded and debuggable)

#### 3d. Pattern storage

**File:** `src/life_world_model/storage/sqlite_store.py` (modify)

Add tables:
```sql
CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    days_observed INTEGER NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    discovered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    total_events INTEGER,
    focus_hours REAL,
    total_context_switches INTEGER,
    top_activity TEXT,
    deep_work_buckets INTEGER,
    pattern_ids_json TEXT
);
```

#### 3e. CLI: patterns command

```bash
lwm patterns --date 2026-04-06              # discover patterns from all collected data up to this date
lwm patterns --range 2026-03-01 2026-04-06  # analyze a specific date range
lwm patterns --show                          # display all stored patterns with evidence
lwm patterns --show --category routine       # filter by category
```

#### Phase 3 Verification
```bash
lwm collect --date 2026-04-06 --backfill     # ensure multi-week history is collected
lwm patterns --range 2026-03-07 2026-04-06   # discover patterns from 30 days
lwm patterns --show                           # verify patterns are sensible and grounded
pytest tests/test_pattern_discovery.py -v     # all tests pass
```

---

### Phase 4: Simulation Engine (What-If)

**Goal:** Let the user describe a habit change in natural language, then see a predicted day with that change applied, including ripple effects based on discovered patterns.

#### 4a. Intervention model

**File:** `src/life_world_model/simulation/types.py` (new)

```python
@dataclass
class Intervention:
    type: str           # "reorder" | "eliminate" | "add" | "limit" | "time_block"
    activity: str       # target activity (e.g., "coding", "browsing", "communication")
    params: dict        # type-specific parameters:
                        #   reorder: {"from_time": "14:00", "to_time": "08:00"}
                        #   eliminate: {"after_time": "21:00"} or {} for full removal
                        #   add: {"activity": "walking", "time": "12:00", "duration_minutes": 30}
                        #   limit: {"max_minutes": 60}
                        #   time_block: {"start": "08:00", "end": "10:00"}
    description: str    # natural language: "Code from 8-10am before checking email"

@dataclass
class SimulationResult:
    baseline_day: list[LifeState]      # actual or typical day
    simulated_day: list[LifeState]     # modified day after intervention
    intervention: Intervention
    ripple_effects: list[str]          # predicted second-order changes
    confidence: float                   # how confident based on pattern evidence
    narrative: str                      # LLM-generated comparison narrative
```

#### 4b. Schedule manipulation engine

**File:** `src/life_world_model/simulation/engine.py` (new)

**How what-if works — 5 steps:**

1. **Load baseline**: The user's typical day (averaged from all collected days), or a specific date if `--baseline DATE` is provided. The typical day is built from Phase 3's daily summaries and pattern data.

2. **Parse intervention**: Natural language → `Intervention` struct. Uses LLM to parse: "Code from 8-10am before checking email" → `Intervention(type="time_block", activity="coding", params={"start": "08:00", "end": "10:00"}, description="...")`.

3. **Mechanical application**: Modify the LifeState timeline deterministically:
   - `reorder`: Move activity buckets from one time range to another. Shift displaced activities to fill the gap.
   - `eliminate`: Remove all buckets of the target activity (optionally after a time). Fill with idle or expand adjacent activities proportionally.
   - `add`: Insert new activity at specified time for specified duration. Compress surrounding activities proportionally to make room.
   - `limit`: Cap target activity at max_minutes total per day. When limit is hit, remaining time goes to the activity that typically follows (from pattern correlations).
   - `time_block`: Reserve a time range for the target activity. Move existing activities out of that window, placing them in the nearest available gap.

4. **Predict ripple effects**: Use Phase 3 patterns to predict second-order changes:
   - Look up correlations: "when you code in the morning, afternoon context_switches decrease by 40%"
   - Apply correlation-based adjustments to the simulated day's behavioral signals
   - These predictions are GROUNDED in the user's own historical patterns, not invented
   - If no relevant pattern exists, state "insufficient data to predict ripple effects"

5. **Generate comparison**: Send both timelines + ripple effects to LLM:
   - Prompt: "Compare this actual day with this simulated day. Narrate the predicted differences. Use these specific patterns as evidence for your predictions. Do not invent effects not supported by the pattern data."
   - Output: side-by-side markdown with timeline comparison + narrated impact prediction

#### 4c. CLI: simulate command

```bash
lwm simulate "What if I coded from 8-10am before checking email?"
lwm simulate "What if I stopped browsing Twitter after 9pm?"
lwm simulate "What if I added a 30-minute walk at lunch?"
lwm simulate --baseline 2026-04-06 "What if I limited Slack to 30 minutes total?"
```

Output: markdown file with:
- Baseline timeline
- Simulated timeline
- Intervention description
- Predicted ripple effects with pattern evidence
- Confidence score
- LLM-narrated comparison

#### Phase 4 Verification
```bash
lwm simulate "Code from 8-10am before email"                    # produces comparison markdown
lwm simulate --baseline 2026-04-06 "Add 30min walk at lunch"    # against specific day
lwm simulate "Stop browsing after 9pm"                           # elimination scenario
pytest tests/test_simulation.py -v                               # all tests pass
```

---

### Phase 5: Suggestion Engine

**Goal:** Automatically generate actionable habit-change recommendations ranked by predicted impact, grounded in the user's own data.

#### 5a. Suggestion generator

**File:** `src/life_world_model/analysis/suggestions.py` (new)

**How suggestions are generated:**

1. Load all discovered patterns from storage
2. For each pattern category, apply opportunity detection rules:

   - **Time sinks** (from time_sink patterns): Suggest limiting or eliminating. "You spend 2.3 hrs/day in fragmented browsing. Limiting to 1hr could free 1.3hrs for deep work."
   - **Context-switching hotspots** (from trigger patterns): Suggest batching or blocking. "Your 14:00-15:00 slot has 12 avg context switches. Time-blocking this for a single activity could save 45min of recovery time."
   - **Productivity correlations** (from correlation patterns): Suggest reordering. "Coding in the morning correlates with 40% fewer afternoon switches. Move your coding block from 14:00 to 08:00."
   - **Missing recovery** (from rhythm patterns): Suggest adding breaks. "You have no idle/break buckets between 09:00-13:00. A 15-min break at 11:00 could improve afternoon focus."
   - **Deep work extension** (from routine patterns): Suggest protecting. "Your 09:00-11:30 focus window is your most productive. Block this time and disable notifications."

3. For each opportunity, create a `Suggestion` with:
   - Specific intervention (what to change)
   - Rationale grounded in pattern evidence (why)
   - Predicted impact ranking (how much it would matter)

4. Rank suggestions by: `pattern_confidence * hours_affected * impact_multiplier`
   - Time sinks and context-switch costs get higher multipliers (more hours recoverable)
   - Routine protection gets lower multiplier (defensive, not additive)

#### 5b. Suggestion feedback tracking

**File:** `src/life_world_model/storage/sqlite_store.py` (modify)

Add table:
```sql
CREATE TABLE IF NOT EXISTS suggestion_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    suggestion_title TEXT NOT NULL,
    intervention_type TEXT NOT NULL,
    shown_at TEXT NOT NULL,
    accepted BOOLEAN,
    accepted_at TEXT,
    notes TEXT
);
```

#### 5c. CLI: suggest command

```bash
lwm suggest                              # top 5 suggestions based on all data
lwm suggest --detail                     # full rationale with pattern evidence for each
lwm suggest --accept 1                   # mark suggestion #1 as accepted
lwm suggest --reject 2 --reason "not practical"  # reject with reason
lwm suggest --history                    # show past accepted/rejected suggestions
```

#### Phase 5 Verification
```bash
lwm suggest                              # generates ranked suggestions
lwm suggest --detail                     # shows evidence-backed rationale
lwm suggest --accept 1                   # tracks acceptance
```

---

### Phase 6: Stretch Goals (Future)

#### 6a. FSEvents Real-Time Monitoring

**File:** `src/life_world_model/collectors/fsevents.py` (new)

- Use `MacFSEvents` PyPI package for real-time file system monitoring
- `lwm watch` daemon mode: collect events continuously in background
- Track file modifications, directory changes
- Feeds into the same RawEvent pipeline

#### 6b. User-Defined Goals System

```bash
lwm goals set "maximize deep work hours"
lwm goals set "limit social media to 1 hour per day"
lwm goals set "take a break every 90 minutes"
lwm goals list
lwm goals progress                       # how you're doing against your goals
```

Each suggestion scored against all active goals. Multi-objective Pareto ranking.

#### 6c. Proactive Experiment Tracking

```bash
lwm experiment start "Code before email for 3 days"
lwm experiment status                    # shows active experiments
lwm experiment results                   # before/after comparison with statistical significance
```

System detects when user changed behavior, automatically measures impact, compares against baseline period.

#### 6d. Continuous Learning Daemon

- `lwm watch` not only collects events but also runs pattern discovery incrementally
- Pattern confidence decays over time if behavior drifts
- New patterns discovered automatically as data accumulates
- Notification when a significant new pattern is found: "I noticed you've been more focused on Tuesdays for the last 3 weeks"

---

## 8. File Summary — New and Modified Files

### New Files (18)

| File | Phase | Purpose |
|------|-------|---------|
| `src/life_world_model/collectors/base.py` | 1a | BaseCollector ABC + collector registry |
| `src/life_world_model/collectors/knowledgec.py` | 1b | macOS knowledgeC.db collector (app usage, screen time) |
| `src/life_world_model/collectors/shell_history.py` | 1c | zsh_history timestamp+command collector |
| `src/life_world_model/collectors/git_activity.py` | 1d | Git commit history collector across 150+ repos |
| `src/life_world_model/collectors/calendar.py` | 1e | Apple Calendar local SQLite collector |
| `src/life_world_model/pipeline/signals.py` | 2b | TikTok-style behavioral signal extraction |
| `src/life_world_model/analysis/__init__.py` | 3 | Analysis package init |
| `src/life_world_model/analysis/pattern_discovery.py` | 3b | Statistical pattern finder (5 detectors) |
| `src/life_world_model/analysis/narrator.py` | 3c | LLM translation of patterns to natural language |
| `src/life_world_model/analysis/suggestions.py` | 5a | Suggestion generator with impact ranking |
| `src/life_world_model/simulation/__init__.py` | 4 | Simulation package init |
| `src/life_world_model/simulation/types.py` | 4a | Intervention + SimulationResult dataclasses |
| `src/life_world_model/simulation/engine.py` | 4b | What-if schedule manipulation + ripple prediction |
| `tests/test_knowledgec.py` | 1j | knowledgeC collector tests |
| `tests/test_shell_history.py` | 1j | Shell history collector tests |
| `tests/test_git_activity.py` | 1j | Git activity collector tests |
| `tests/test_pattern_discovery.py` | 3 | Pattern discovery tests |
| `tests/test_simulation.py` | 4 | Simulation engine tests |

### Modified Files (7)

| File | Phase | Changes |
|------|-------|---------|
| `src/life_world_model/types.py` | 1g, 2c, 3a | Add `duration_seconds`+`metadata` to RawEvent, signals to LifeState, add Pattern+Suggestion types |
| `src/life_world_model/collectors/chrome_history.py` | 1a | Retrofit to extend BaseCollector |
| `src/life_world_model/storage/sqlite_store.py` | 1h, 3d, 5b | Migration system, new columns, new tables (patterns, daily_summaries, suggestion_feedback) |
| `src/life_world_model/pipeline/bucketizer.py` | 2a | Multi-source priority cascade activity classifier |
| `src/life_world_model/cli.py` | 1h, 3e, 4c, 5c | New subcommands: sources, patterns, simulate, suggest |
| `src/life_world_model/config.py` | 1i | Add paths for knowledgeC, zsh_history, git repos, calendar |
| `pyproject.toml` | 1 | New CLI entrypoints, optional dependencies |

---

## 9. Existing Codebase Reference

### Key Source Files (current state)

**`src/life_world_model/types.py`** — 30 lines. Three dataclasses: `RawEvent(timestamp, source, title, domain, url)`, `LifeState(timestamp, primary_activity, secondary_activity, domain, event_count, confidence)`, `NarrativeFrame(timestamp, narrative)`.

**`src/life_world_model/collectors/chrome_history.py`** — 72 lines. `ChromeHistoryCollector` with `collect_for_date(target_date) -> list[RawEvent]`. Copies Chrome DB to temp, queries visits table, converts Windows FILETIME epoch (1601), extracts domains. This is the pattern all new collectors follow.

**`src/life_world_model/storage/sqlite_store.py`** — 70 lines. `SQLiteStore` with `initialize()`, `save_raw_events(events)`, `load_raw_events_for_date(target_date)`. Single `raw_events` table with auto-create. ISO string timestamps.

**`src/life_world_model/pipeline/bucketizer.py`** — 69 lines. `build_life_states(events, bucket_minutes=15) -> list[LifeState]`. Floors timestamps to bucket boundaries, groups events, calls `infer_activity()` (keyword matching on domains/titles), fills gaps with idle.

**`src/life_world_model/pipeline/generator.py`** — Contains `build_prompt(states)`, `generate_with_gemini()`, `generate_with_mlx()`, `render_narrative_markdown()`, `render_fallback_markdown()`, `write_rollout()`.

**`src/life_world_model/cli.py`** — 152 lines. argparse with subcommands: collect, generate, run. `run_collect()` creates collector + store, `run_generate()` loads events + bucketizes + generates, `_generate_content()` dispatches to Gemini/MLX/fallback.

**`src/life_world_model/config.py`** — 60 lines. `Settings` dataclass with defaults. `load_settings()` reads `.env` then `os.environ`. Custom dotenv parser (no external deps).

### Design Docs

- **`docs/design/RUTHLESS-MVP.md`** (98 lines): Scope philosophy. In: one machine, one user, one source, one day, one markdown. Out: multiple sources, daemon, live mode, embeddings, fine-tuning, UI, cloud sync.
- **`docs/design/PYTHON-MVP-BUILD-PLAN.md`** (359 lines): Concrete implementation roadmap with milestones.
- **`docs/design/MVP-IMPLEMENTATION-BLUEPRINT.md`** (1991 lines): Research-grounded blueprint. Synthesizes Genie 3, Dreamer 4, World Labs, VERSES AI, UI-Simulator. Full 4-layer architecture, memory management, training paradigms, phases v0-v3.
- **`docs/research/RHODA_DVA_INVESTIGATION.md`**: Validates text-based world models. Patterns: context amortization, inverse dynamics separation, long-context memory, leapfrog inference.
- **`docs/research/world-models-landscape.md`**: Landscape survey of world model research.

---

## 10. Open Questions for Interview

These questions remain unanswered and would help refine the plan:

### Priority & Scope

1. **Close the TikTok gaps now or later?** Should we add user goals (Phase 6b), proactive experiments (Phase 6c), and continuous learning (Phase 6d) to the core plan — or build Phases 1-5 first and layer those on after?

2. **Priority within Phase 1?** Build all 5 collectors simultaneously, or ship knowledgeC first (highest value) and iterate with others?

3. **Multi-day views?** Should `lwm generate` support week/month narrative views, or stay single-day? Weekly summaries would be natural for pattern discovery.

### User Experience

4. **Narrative style?** Keep Tolkien-esque prose for everything, switch to plain English for patterns/suggestions, or make it configurable per command?

5. **How detailed should suggestions be?** Quick one-liners ("limit browsing to 1hr") or full evidence reports with charts and historical data?

6. **Notification preferences?** When the system discovers a new pattern or a suggestion changes, how should it notify? Terminal output only, or macOS notifications?

### Technical

7. **Calendar permissions?** macOS requires Full Disk Access for `~/Library/Calendars/`. Should we automate the permission prompt, provide manual instructions, or make calendar collection opt-in?

8. **knowledgeC.db access?** Same permission question — does this need Full Disk Access, or is it accessible from the user's application context?

9. **Git scanning scope?** Scan all 150+ repos in `~/Projects/`, or let the user configure a whitelist? Scanning all repos could be slow.

### Personal Goals

10. **What habits do you most want to change?** Specific goals (e.g., "less social media", "more deep work", "better sleep schedule") would help prioritize which patterns to surface first and which suggestions to generate.

11. **What does your ideal day look like?** If you could design your perfect weekday schedule, what would it be? This could serve as a north star for the suggestion engine.

12. **What's your biggest time sink right now?** If you already have a suspicion, confirming it with data would be a powerful first use case.
