# Quickstart

This repo is safe to try in two modes:

1. `demo` mode - no personal data needed
2. `local` mode - reads your Chrome history on your machine

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Fastest Way To Try It

Run the bundled demo:

```bash
lwm run --date 2026-03-21 --demo
```

Then open:

`data/processed/rollouts/2026-03-21_narrative.md`

## Use Your Own Data

Run the local Chrome-history flow:

```bash
lwm run --date 2026-03-21
```

If Chrome lives somewhere custom on your machine:

```bash
export LWM_CHROME_HISTORY_PATH="/path/to/Chrome/History"
lwm run --date 2026-03-21
```

## Useful Commands

```bash
lwm collect --date 2026-03-21
lwm generate --date 2026-03-21
lwm collect --date 2026-03-21 --demo
lwm run --date 2026-03-21 --demo
```

## Privacy

- your local event database is ignored by git
- generated rollouts are ignored by git
- Chrome history files are ignored by git
- `.claude/` local assistant settings are ignored by git

## What You Should Expect

Today this is still an MVP scaffold.

- it collects one day's events
- it buckets them into simple 15-minute states
- it writes a grounded markdown narrative draft

It is not yet a full LLM-powered fantasy narrator.
