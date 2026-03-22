# Ruthless-Cut MVP

This document replaces the ambitious version of the MVP with the smallest thing worth building.

## The Point

Do not try to build a full personal world model first.

Build a local prototype that proves one loop:

`desktop activity -> simple state timeline -> one day narrative`

If that loop is not compelling, nothing else matters.

## What v0 Is

v0 is a **single-day narrative generator** from real local activity.

It is not:

- a predictive engine
- a live narrator
- a branching timeline simulator
- a Bayesian system
- a personalized fine-tuned model

## User Story

"At the end of the day, I can run one local command and get a readable fantasy-style narrative of what I actually spent my time doing."

## Ruthless Scope

### In Scope

- one machine
- one user
- one data source to start
- one day at a time
- one markdown output
- one prompt-based generator using an API model
- local file storage or SQLite

### Out of Scope

- multiple data sources in v0
- continuous background daemon
- conflict detection
- memory tiers
- conditional rollouts
- live mode
- embeddings or retrieval system
- model fine-tuning
- Bayesian or active inference layer
- UI
- cloud sync

## Recommended Data Source

Start with **Chrome history**.

Why:

- easiest high-signal source for research/writing/coding context
- enough variety to make the narrative interesting
- simpler than reliable filesystem and system event tracking

Fallback choice: active app usage if Chrome history access is annoying.

## v0 Architecture

```text
Chrome History
    -> raw events JSON/SQLite
    -> 15-minute buckets
    -> simple LifeState objects
    -> prompt template
    -> markdown day narrative
```

## Minimum Data Model

```text
RawEvent
- timestamp
- source
- title
- domain
- url

LifeState
- timestamp
- primary_activity
- secondary_activity
- domain
- confidence
```

That is enough.

Do not add location inference, noise level, medium-term memory, or fact graphs yet.

## Minimum Commands

Only two commands matter for v0:

```bash
lwm-collect --date 2026-03-21
lwm-generate --date 2026-03-21
```

If even that feels heavy, collapse to one command:

```bash
lwm-run --date 2026-03-21
```

## Definition Of Done

v0 is done when all of these are true:

1. one command can ingest one day's local activity data
2. one command can generate a markdown narrative for that day
3. the output is believable enough that the founder says "yes, this roughly matches my day"

## Evaluation

Do not judge success by research elegance.

Judge it by:

- did it run locally without drama?
- did it cover the day at a useful level of detail?
- did the prose feel grounded in real activity?
- would you run it again tomorrow?

## Implementation Order

### Step 1: Ingest

- read one local data source
- write raw records locally
- verify one real day can be extracted

### Step 2: Normalize

- bucket raw events into 15-minute windows
- assign a primary activity label per window
- store as `LifeState`

### Step 3: Generate

- feed ordered states into one prompt template
- create one markdown narrative file
- keep prompt engineering simple and explicit

### Step 4: Evaluate

- compare output against your actual day
- note where the narrative is wrong, vague, or repetitive
- improve only the schema or prompt, not the scope

## Risks To Avoid

### 1. Research Cosplay

Do not spend another week expanding the world-model theory before the first narrative exists.

### 2. Premature Architecture

Do not create collectors, memory managers, and hybrid model layers before you have one working path.

### 3. False Prediction Claims

v0 reconstructs or lightly extrapolates from observed activity. It does not meaningfully predict the future yet.

### 4. Privacy Hand-Waving

If you collect browsing data, be explicit about:

- where it is stored
- how to delete it
- whether URLs are redacted
- how long it is kept

## What To Build Right After v0

Only after v0 works should you choose one next step:

1. improve fidelity with a second data source
2. add simple consistency memory for better narrative continuity
3. test one lightweight what-if rollout

Do not do all three at once.

## Founder Rule

If the smallest version is not delightful or useful, cut the idea again before adding complexity.
