# Personal Life World Model

> A local-first experiment to turn your desktop activity into a Tolkien-esque day narrative.

**Status:** early Python scaffold for the cut MVP; not a complete MVP yet.

This repo now contains the narrowed build plan, a Python package skeleton for the first local prototype, and a demo mode so someone else can try it without using private browsing data.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Try the privacy-safe demo first:

```bash
lwm run --date 2026-03-21 --demo
```

That writes a markdown file to `data/processed/rollouts/2026-03-21_narrative.md`.

To use your own local Chrome history instead:

```bash
lwm run --date 2026-03-21
```

For a friend-friendly setup guide, see `QUICKSTART.md`.

## What This Project Is

The long-term idea is a personal "world model" that learns from your digital life and generates rich narrative rollouts of your day.

The ruthless-cut MVP is much smaller:

- ingest one local activity stream
- convert it into a simple timeline of states
- generate one markdown narrative for a single real day
- keep everything local

## Ruthless-Cut MVP

The first shippable version is **not** a predictive multiverse engine.

It is:

1. one data source: Chrome history or active app usage
2. one normalized state schema for 15-minute blocks
3. one prompt template that turns those states into prose
4. one output file: `data/processed/rollouts/YYYY-MM-DD_narrative.md`

Success for v0 is simple:

- it runs locally on one machine
- it produces a believable narrative for one observed day
- the output is useful enough that you want to run it again

See `docs/design/RUTHLESS-MVP.md` for the narrowed plan and `docs/design/PYTHON-MVP-BUILD-PLAN.md` for the concrete Python implementation order.

## Repo Structure

```
src/life_world_model/       # package: collectors, pipeline, storage, CLI
tests/                      # unit tests
docs/
  design/                   # architecture blueprints and build plans
  research/                 # landscape surveys and paper investigations
data/                       # local-only runtime data (gitignored)
```

## What Is Not Built Yet

- evaluation loop over real outputs
- second data source
- prediction or what-if rollouts

## Privacy Notes

- raw data and generated outputs under `data/` are ignored by git
- SQLite databases and Chrome history files are ignored by git
- local assistant config under `.claude/` is ignored by git
- use `--demo` when you want to share or test the tool without touching personal browsing history

## Build Order

1. choose one data source
2. define one `LifeState` schema
3. persist raw events locally
4. map events to 15-minute states
5. generate one day narrative from those states
6. evaluate output quality before adding more scope

## Recommended First Milestone

"Generate a Tolkien-style markdown narrative for one real day using one local data source."

If that does not work well, do not add:

- live narration
- what-if rollouts
- Bayesian inference
- multi-day prediction
- fine-tuning

## Near-Term Goal

Build the smallest local prototype that proves this loop:

`activity data -> structured state -> narrative output`

Once that loop is real, then decide whether this should become:

- a narrative journal
- a day reconstruction tool
- a predictive planner
- a true world-model research project
