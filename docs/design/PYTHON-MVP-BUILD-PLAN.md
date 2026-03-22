# Python MVP Build Plan

This is the concrete build plan for the ruthless-cut MVP.

The goal is not to build the whole vision.

The goal is to ship one working local loop:

`collect activity -> normalize into states -> generate one day narrative`

## Stack

- language: Python 3.11+
- storage: SQLite or newline-delimited JSON
- interface: CLI only
- model: API-based LLM
- output: markdown file

## Folder Structure

Create only this:

```text
src/
  life_world_model/
    __init__.py
    cli.py
    config.py
    types.py
    collectors/
      __init__.py
      chrome_history.py
    storage/
      __init__.py
      sqlite_store.py
    pipeline/
      __init__.py
      bucketizer.py
      generator.py

data/
  raw/
  processed/
    rollouts/

tests/
  test_bucketizer.py
  test_generator_prompt.py
```

Do not add memory managers, multiple collectors, embeddings, or UI folders yet.

## First 5 Files To Create

If you want the smallest possible start, create these first:

1. `src/life_world_model/types.py`
2. `src/life_world_model/collectors/chrome_history.py`
3. `src/life_world_model/pipeline/bucketizer.py`
4. `src/life_world_model/pipeline/generator.py`
5. `src/life_world_model/cli.py`

Everything else can follow after the loop works.

## Minimum Types

Use plain dataclasses or Pydantic models. Keep them tiny.

### RawEvent

```python
timestamp: datetime
source: str
title: str | None
domain: str | None
url: str | None
```

### LifeState

```python
timestamp: datetime
primary_activity: str
secondary_activity: str | None
domain: str | None
event_count: int
confidence: float
```

### NarrativeFrame

```python
timestamp: datetime
narrative: str
```

That is enough for v0.

## CLI Shape

Keep the CLI boring.

### Option A: two commands

```bash
lwm-collect --date 2026-03-21
lwm-generate --date 2026-03-21
```

### Option B: one command wrapper

```bash
lwm-run --date 2026-03-21
```

Recommendation: implement both, but only after the two-command flow works.

## Command Responsibilities

### `lwm-collect`

- read Chrome history for one requested date
- convert rows into `RawEvent`
- write them to local storage
- print count and output location

### `lwm-generate`

- load raw events for that date
- bucket them into 15-minute windows
- convert windows to `LifeState`
- generate markdown narrative
- write `data/processed/rollouts/YYYY-MM-DD_narrative.md`

### `lwm-run`

- run collect then generate
- useful only after the two commands already work

## Storage Decision

Start with **SQLite** if you want one honest local source of truth.

Use **JSONL** if you want absolute simplicity.

My recommendation: SQLite, but with only one table at first.

### Smallest SQLite Schema

```sql
CREATE TABLE raw_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  source TEXT NOT NULL,
  title TEXT,
  domain TEXT,
  url TEXT
);
```

Do not add life state and narrative tables until the raw ingestion path is real.

## Chrome Collector Plan

`chrome_history.py` should do only this:

1. locate Chrome history DB
2. copy it to a temp file because Chrome locks it
3. query visits for a single date range
4. map rows into `RawEvent`
5. return a list

Do not try to infer meaning inside the collector.

Collector output should stay dumb.

## Bucketizer Plan

`bucketizer.py` is where the first useful product logic lives.

Responsibilities:

1. group raw events into 15-minute windows
2. count events per bucket
3. infer a simple `primary_activity`
4. keep one or two strongest signals as `secondary_activity`

Start with lightweight heuristics only:

- GitHub, docs, papers, search -> `research`
- Cursor, VS Code, repo docs -> `coding`
- Gmail, Slack, Messages -> `communication`
- low signal / mixed browsing -> `browsing`

If a bucket has no events:

- mark it `idle`
- do not invent detail

## Generator Plan

`generator.py` should be thin.

Responsibilities:

1. take ordered `LifeState` items
2. build one simple prompt
3. ask the LLM for a day narrative in markdown
4. save output

Do not generate 96 separate frames at first unless you have to.

My recommendation: first ask the model for **one full narrative document** from the ordered states.

That is much simpler than a full autoregressive engine and still proves the core idea.

## Prompt Shape

Use a prompt with only these sections:

```text
You are writing a Tolkien-esque narrative of a real day.

Use the timeline below as ground truth.
Do not invent major activities that are not supported by the data.
If the data is sparse, stay vague instead of hallucinating specifics.

Timeline:
- 09:00 research github.com world-models
- 09:15 coding github.com world-models
- 09:30 idle
...
```

The anti-hallucination instruction matters more than fancy style instructions.

## Minimum Milestone Sequence

### Milestone 1: raw extraction works

Done when:

- you can read one day's Chrome history
- you can print or store 20 to 200 real events

### Milestone 2: timeline exists

Done when:

- those events become 15-minute buckets
- each bucket gets a simple activity label

### Milestone 3: narrative generation works

Done when:

- the timeline becomes one markdown narrative
- the output file exists for one real day

### Milestone 4: useful enough to rerun

Done when:

- the founder reads the output and says it roughly matches reality
- obvious hallucinations are reduced
- it feels worth running again tomorrow

## First Test Coverage

Write only these tests first:

### `test_bucketizer.py`

- groups events into correct 15-minute windows
- labels a GitHub-heavy bucket as `research` or `coding`
- marks empty buckets as `idle`

### `test_generator_prompt.py`

- prompt includes timeline entries in order
- prompt tells model not to invent unsupported activity
- markdown output path is correct

Do not start with broad integration test scaffolding.

## First Runnable Demo

The first demo should look like this:

```bash
python -m life_world_model.cli collect --date 2026-03-21
python -m life_world_model.cli generate --date 2026-03-21
```

And the result should be:

```text
data/processed/rollouts/2026-03-21_narrative.md
```

## Pitfalls To Avoid

### Do not over-model the world

You do not need:

- physical context
- Bayesian beliefs
- conflict graphs
- agent memory tiers

You need one believable timeline.

### Do not over-split modules

If a file is under 100 lines and coherent, keep it together.

### Do not promise prediction yet

This first version reconstructs or lightly summarizes a real observed day.

Prediction is a later product question.

## Recommended Build Order By Day

### Day 1

- create package skeleton
- implement Chrome collector
- dump one day of raw events

### Day 2

- implement bucketizer
- inspect output manually
- tune simple heuristics

### Day 3

- implement generator
- create first markdown narrative
- tighten prompt to reduce hallucination

### Day 4

- add small tests
- clean CLI
- rerun on another day

## What Comes After This

Only after this works, choose one:

1. second data source
2. better continuity between timeline segments
3. simple what-if experiment

Pick one. Not three.
