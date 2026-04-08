# Cross-Language Concurrency Patterns for Life World Model

> How Elixir/OTP, Go, Rust, Clojure, and Swift solve the exact problem we have:
> a single-process daemon that collects data hourly, discovers patterns, checks
> experiment completions, scores days, decays stale patterns, and sends notifications.
>
> For each concept: what the language does, what idea to STEAL, and a concrete
> Python translation for our codebase.

---

## Table of Contents

1. [GenServer — Stateful Process with Message Dispatch](#1-genserver--stateful-process-with-message-dispatch)
2. [Supervisor Trees — Fault Isolation and Restart Strategies](#2-supervisor-trees--fault-isolation-and-restart-strategies)
3. [GenStage — Producer-Consumer with Backpressure](#3-genstage--producer-consumer-with-backpressure)
4. [Phoenix.PubSub — Topic-Based Pub/Sub](#4-phoenixpubsub--topic-based-pubsub)
5. [Telemetry — Lightweight Event Emission for Metrics](#5-telemetry--lightweight-event-emission-for-metrics)
6. [Broadway — Data Processing Pipelines](#6-broadway--data-processing-pipelines)
7. [Registry — Process Discovery](#7-registry--process-discovery)
8. [Task.async/Task.await — Supervised Async Work](#8-taskasynctaskawait--supervised-async-work)
9. [Go Channels + Select — Fan-Out/Fan-In with Timer Multiplexing](#9-go-channels--select--fan-outfan-in-with-timer-multiplexing)
10. [Rust Tokio Broadcast Channels — Multi-Consumer Event Distribution](#10-rust-tokio-broadcast-channels--multi-consumer-event-distribution)
11. [Clojure add-watch on Atoms — Reactive State](#11-clojure-add-watch-on-atoms--reactive-state)
12. [Swift Combine — Publisher-Subscriber Pipelines](#12-swift-combine--publisher-subscriber-pipelines)
13. [Synthesis: The LWM Daemon Architecture](#13-synthesis-the-lwm-daemon-architecture)

---

## 1. GenServer — Stateful Process with Message Dispatch

### What Elixir Does

A GenServer (Generic Server) is a process that holds state and processes one message at
a time through a mailbox. It combines what Python separates into "object with state" and
"message queue consumer" into a single abstraction. The key: messages are processed
sequentially, so you never need locks.

Three callback types handle all communication:

- **`handle_call/3`** — synchronous: caller blocks until reply. Provides natural
  backpressure because the sender cannot fire-and-forget.
- **`handle_cast/2`** — asynchronous fire-and-forget: no reply. Used when you don't
  care about the result.
- **`handle_info/2`** — catches everything else: timer messages, monitor signals, raw
  `send/2` messages. This is how self-scheduling works.

```elixir
defmodule CollectorServer do
  use GenServer

  # --- Client API ---
  def start_link(opts) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end

  def collect_now do
    GenServer.call(__MODULE__, :collect)
  end

  def get_last_result do
    GenServer.call(__MODULE__, :get_last_result)
  end

  # --- Server Callbacks ---
  @impl true
  def init(opts) do
    # Schedule first collection in 1 second
    Process.send_after(self(), :tick, 1_000)
    {:ok, %{interval: opts[:interval] || 3_600_000, last_result: nil}}
  end

  @impl true
  def handle_call(:collect, _from, state) do
    result = do_collection()
    {:reply, result, %{state | last_result: result}}
  end

  @impl true
  def handle_call(:get_last_result, _from, state) do
    {:reply, state.last_result, state}
  end

  @impl true
  def handle_info(:tick, state) do
    result = do_collection()
    # Re-schedule: this is the self-scheduling pattern
    Process.send_after(self(), :tick, state.interval)
    {:noreply, %{state | last_result: result}}
  end

  defp do_collection do
    # ... actual collection logic ...
    {:ok, 42}
  end
end
```

The critical insight: `Process.send_after(self(), :tick, interval)` in `handle_info`
creates a self-scheduling loop that is far more resilient than `while True: sleep()`.
If `do_collection()` takes 20 minutes, the next tick is scheduled 60 minutes *after
that completes*, not 60 minutes from some fixed wall-clock time. Drift is explicit
and controllable.

### How Each Daemon Subsystem Would Be a GenServer

| Subsystem | State it holds | Messages it handles |
|-----------|---------------|-------------------|
| `CollectorServer` | last_run timestamp, event count | `:tick`, `:collect_now`, `:get_status` |
| `PatternServer` | discovered patterns, confidence scores | `:refresh`, `:decay_stale`, `:get_patterns` |
| `ScorerServer` | today's score, score history | `:score_now`, `:get_score`, `:score_changed` |
| `ExperimentServer` | active experiments, baselines | `:check_completions`, `:get_active` |
| `NotificationServer` | notification queue, last-sent timestamps | `:send`, `:score_delta`, `:briefing` |
| `SuggestionServer` | ranked suggestions, feedback history | `:regenerate`, `:get_suggestions` |

### What to STEAL for Python

1. **One message at a time** — no locks needed if each subsystem is a class with a
   message queue that processes sequentially.
2. **Self-scheduling via `handle_info`** — instead of `time.sleep()`, schedule the next
   tick as a message posted to yourself.
3. **Separation of sync calls vs async casts** — some callers need a reply (CLI asking
   for score), others don't (collector firing a "data ready" event).

### Python Translation

```python
"""
GenServer-inspired stateful handler for Python.

Each daemon subsystem is a Handler subclass with:
- state dict (replaces GenServer state)
- handle() method with pattern matching on event type (replaces handle_call/cast/info)
- self-scheduling via the event bus (replaces Process.send_after)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Event:
    topic: str
    payload: dict = field(default_factory=dict)
    reply_to: Callable | None = None  # If set, this is a "call" (sync)
    timestamp: float = field(default_factory=time.monotonic)


class Handler:
    """Base class for a GenServer-like stateful handler.

    Subclasses override handle() to process events.
    State is instance attributes -- no shared mutable state.
    """

    def __init__(self) -> None:
        self.subscriptions: list[str] = []  # Topics this handler cares about

    def handle(self, event: Event) -> Any:
        """Dispatch an event. Return value is sent to reply_to if present.

        This is the equivalent of handle_call + handle_cast + handle_info
        collapsed into one method with pattern matching on event.topic.
        """
        raise NotImplementedError

    def init(self, bus: "EventBus") -> None:
        """Called once when the handler is registered. Schedule first tick here.

        Equivalent to GenServer.init/1.
        """
        pass


class CollectorHandler(Handler):
    """GenServer equivalent for the collection subsystem."""

    def __init__(self, interval_sec: int = 3600) -> None:
        super().__init__()
        self.subscriptions = ["collector.tick", "collector.collect_now",
                              "collector.get_status"]
        self.interval_sec = interval_sec
        self.last_result: dict | None = None
        self.last_run: float | None = None

    def init(self, bus: EventBus) -> None:
        # Self-schedule first tick (like Process.send_after in init/1)
        bus.schedule("collector.tick", delay_sec=1.0)

    def handle(self, event: Event) -> Any:
        match event.topic:
            case "collector.tick":
                result = self._do_collection()
                self.last_result = result
                self.last_run = time.monotonic()
                # Re-schedule next tick (like Process.send_after in handle_info)
                event.payload.get("_bus").schedule(
                    "collector.tick", delay_sec=self.interval_sec
                )
                # Fire event for downstream consumers (patterns, scoring)
                event.payload.get("_bus").emit("data.collected", {
                    "event_count": result.get("count", 0)
                })
                return None  # cast -- no reply

            case "collector.collect_now":
                result = self._do_collection()
                self.last_result = result
                self.last_run = time.monotonic()
                return result  # call -- reply with result

            case "collector.get_status":
                return {
                    "last_run": self.last_run,
                    "last_result": self.last_result,
                }

    def _do_collection(self) -> dict:
        # ... actual collection logic ...
        return {"count": 42, "sources": ["chrome", "shell", "git"]}


class PatternHandler(Handler):
    """GenServer equivalent for pattern discovery."""

    def __init__(self) -> None:
        super().__init__()
        self.subscriptions = [
            "data.collected",       # Triggered by CollectorHandler
            "patterns.decay",       # Self-scheduled
            "patterns.get",         # Sync query
        ]
        self.patterns: list = []
        self.last_refresh: float | None = None

    def init(self, bus: EventBus) -> None:
        # Schedule pattern decay check every 6 hours
        bus.schedule("patterns.decay", delay_sec=6 * 3600)

    def handle(self, event: Event) -> Any:
        match event.topic:
            case "data.collected":
                # New data arrived -- refresh patterns
                self.patterns = self._discover_patterns()
                self.last_refresh = time.monotonic()
                return None

            case "patterns.decay":
                self._decay_stale_patterns()
                event.payload.get("_bus").schedule(
                    "patterns.decay", delay_sec=6 * 3600
                )
                return None

            case "patterns.get":
                return self.patterns

    def _discover_patterns(self) -> list:
        # ... statistical pattern discovery ...
        return []

    def _decay_stale_patterns(self) -> None:
        # ... apply temporal decay to pattern confidence ...
        pass
```

**Key insight**: The Python version collapses `handle_call`, `handle_cast`, and
`handle_info` into a single `handle()` method with `match/case`. The distinction
between sync and async is handled by the presence of `event.reply_to`. This is
simpler than Elixir's three-callback model while preserving the same mental model.

---

## 2. Supervisor Trees — Fault Isolation and Restart Strategies

### What Elixir Does

Supervisors monitor child processes. When a child crashes, the supervisor decides what
to do based on the restart strategy:

| Strategy | Behavior | When to use |
|----------|----------|-------------|
| **`:one_for_one`** | Only restart the crashed child | Children are independent (our collectors) |
| **`:one_for_all`** | Restart ALL children if any one crashes | Children are tightly coupled (rare for us) |
| **`:rest_for_one`** | Restart the crashed child and everything started after it | Pipeline stages (collector -> scorer depends on collector) |

The philosophy is **"let it crash"**: don't write defensive try/except spaghetti.
Instead, let the process die and have the supervisor restart it in a known-good state.
This sounds reckless but produces cleaner code: error handling is separated from
business logic and centralized in the supervisor.

```elixir
defmodule LWM.DaemonSupervisor do
  use Supervisor

  def start_link(opts) do
    Supervisor.start_link(__MODULE__, opts, name: __MODULE__)
  end

  @impl true
  def init(_opts) do
    children = [
      # Independent collectors -- one crashing shouldn't kill others
      {LWM.CollectorServer, interval: 3_600_000},
      {LWM.PatternServer, []},
      {LWM.ScorerServer, []},
      {LWM.ExperimentServer, []},
      {LWM.NotificationServer, []},
      {LWM.SuggestionServer, []}
    ]

    # one_for_one: if the pattern server crashes, don't restart the collector
    Supervisor.init(children, strategy: :one_for_one, max_restarts: 5, max_seconds: 60)
  end
end
```

Critical detail: `max_restarts: 5, max_seconds: 60` means "if a child crashes more than
5 times in 60 seconds, give up and shut down the supervisor too." This prevents infinite
restart loops.

### What to STEAL for Python

1. **Fault isolation per handler** — wrap each handler's `handle()` in its own
   try/except. One handler crashing should not kill the daemon.
2. **Restart counting** — track crash count per handler. If it exceeds a threshold,
   disable that handler and log a critical error instead of looping forever.
3. **Strategy selection** — for our daemon, `:one_for_one` is correct: if the Chrome
   collector crashes (maybe Chrome isn't running), the shell history collector should
   keep going.

### Python Translation

```python
"""
Supervisor-inspired fault isolation for the event bus.

Instead of Erlang processes, we have Handler instances.
Instead of process restart, we have handler reset (re-init).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

log = logging.getLogger("lwm.supervisor")


@dataclass
class HandlerHealth:
    crash_count: int = 0
    last_crash: float | None = None
    disabled: bool = False
    max_crashes: int = 5          # max_restarts equivalent
    crash_window_sec: float = 60  # max_seconds equivalent


class SupervisedEventBus:
    """Event bus with one_for_one supervision built in.

    Each handler is isolated: if it throws, the bus catches the exception,
    increments the crash counter, and continues dispatching to other handlers.
    If a handler exceeds max_crashes within crash_window_sec, it is disabled.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}  # topic -> [handlers]
        self._health: dict[str, HandlerHealth] = {}    # handler_id -> health
        self._timers: list = []

    def register(self, handler: Handler) -> None:
        handler_id = f"{handler.__class__.__name__}_{id(handler)}"
        self._health[handler_id] = HandlerHealth()

        for topic in handler.subscriptions:
            self._handlers.setdefault(topic, []).append(handler)

        # Store handler_id on the handler for lookup
        handler._supervisor_id = handler_id
        handler.init(self)

    def emit(self, topic: str, payload: dict | None = None) -> None:
        """Fire-and-forget dispatch (equivalent to GenServer.cast)."""
        payload = payload or {}
        payload["_bus"] = self
        event = Event(topic=topic, payload=payload)

        for handler in self._handlers.get(topic, []):
            self._dispatch_safe(handler, event)

    def call(self, topic: str, payload: dict | None = None) -> Any:
        """Synchronous dispatch -- returns first handler's reply.

        Equivalent to GenServer.call.
        """
        payload = payload or {}
        payload["_bus"] = self
        event = Event(topic=topic, payload=payload)

        for handler in self._handlers.get(topic, []):
            result = self._dispatch_safe(handler, event)
            if result is not None:
                return result
        return None

    def _dispatch_safe(self, handler: Handler, event: Event) -> Any:
        """One-for-one supervision: isolate each handler's failures."""
        health = self._health.get(handler._supervisor_id)
        if health and health.disabled:
            return None

        try:
            return handler.handle(event)
        except Exception:
            log.exception(
                "Handler %s crashed on topic %s",
                handler.__class__.__name__,
                event.topic,
            )
            if health:
                self._record_crash(handler, health)
            return None

    def _record_crash(self, handler: Handler, health: HandlerHealth) -> None:
        """Track crashes and disable handler if it exceeds the threshold.

        This is the max_restarts/max_seconds equivalent.
        """
        now = time.monotonic()

        # Reset crash count if outside the window
        if (health.last_crash is not None
                and now - health.last_crash > health.crash_window_sec):
            health.crash_count = 0

        health.crash_count += 1
        health.last_crash = now

        if health.crash_count >= health.max_crashes:
            health.disabled = True
            log.critical(
                "Handler %s disabled after %d crashes in %.0fs",
                handler.__class__.__name__,
                health.crash_count,
                health.crash_window_sec,
            )

    def schedule(self, topic: str, delay_sec: float,
                 payload: dict | None = None) -> None:
        """Schedule an event to be emitted after a delay.

        Equivalent to Process.send_after(self(), message, milliseconds).
        In a threaded implementation, this would use threading.Timer.
        In an asyncio implementation, this would use loop.call_later.
        """
        import threading
        timer = threading.Timer(delay_sec, self.emit, args=(topic, payload))
        timer.daemon = True
        timer.start()
        self._timers.append(timer)
```

### How "Let It Crash" Applies to a Python Daemon

In Erlang, "let it crash" works because:
1. Processes are cheap to restart (microseconds).
2. Supervisors automatically restart crashed processes.
3. Process state is reconstructed from scratch in `init/1`.

In Python, the translation is:
1. **Don't wrap individual collector calls in try/except within the collector.**
   Let exceptions propagate.
2. **Catch at the bus dispatch level** (the supervisor boundary).
3. **Re-initialize handler state on repeated crashes** — call `handler.init(bus)` again
   to reset to a known-good state.
4. **Disable after threshold** — the `max_restarts / max_seconds` pattern prevents
   infinite restart loops.

The current daemon code does the opposite: `except Exception: pass` inside the
collector loop (line 31 of `daemon/collector.py`). This swallows errors silently, which
is the worst of both worlds: no crash recovery AND no error visibility.

---

## 3. GenStage — Producer-Consumer with Backpressure

### What Elixir Does

GenStage is a specification built on GenServer for exchanging events between processes
with demand-driven backpressure. Three roles:

- **Producer** — emits events when downstream consumers request them
- **ProducerConsumer** — receives events, transforms them, passes them downstream
- **Consumer** — terminal sink that processes events

The key innovation: consumers send **demand** upstream. A consumer says "I can handle 10
events," the producer sends at most 10. This prevents the producer from overwhelming a
slow consumer.

```elixir
# Producer: emits raw events
defmodule LWM.EventProducer do
  use GenStage

  def init(:ok) do
    {:producer, %{pending_events: []}}
  end

  def handle_demand(demand, state) when demand > 0 do
    # Only produce what was requested
    {events, remaining} = Enum.split(state.pending_events, demand)
    {:noreply, events, %{state | pending_events: remaining}}
  end
end

# ProducerConsumer: bucketizes raw events into LifeStates
defmodule LWM.Bucketizer do
  use GenStage

  def init(:ok) do
    {:producer_consumer, %{}}
  end

  def handle_events(events, _from, state) do
    life_states = Enum.map(events, &bucketize/1)
    {:noreply, life_states, state}
  end
end

# Consumer: scores the day
defmodule LWM.Scorer do
  use GenStage

  def init(:ok) do
    {:consumer, %{}}
  end

  def handle_events(life_states, _from, state) do
    score = calculate_score(life_states)
    {:noreply, [], %{state | latest_score: score}}
  end
end
```

### How Our Pipeline Maps to GenStage

```
CollectorProducer -> BucketizerProducerConsumer -> [ScorerConsumer,
                                                     PatternConsumer,
                                                     SuggestionConsumer]
```

The collector produces `RawEvent` items. The bucketizer transforms them into
`LifeState` items. Multiple consumers (scorer, pattern discoverer, suggestion engine)
each independently consume `LifeState` items at their own pace.

### What to STEAL for Python

**Backpressure via bounded queues.** In a single-process Python daemon, we don't
actually need GenStage's demand-driven protocol. The simpler equivalent:

1. Use `asyncio.Queue(maxsize=N)` or `queue.Queue(maxsize=N)`.
2. If the queue is full, `put()` blocks the producer automatically.
3. This gives us natural backpressure without implementing demand.

For our daemon, however, the pipeline is **synchronous and single-threaded**:
collect -> bucketize -> score. Backpressure is implicit because each stage runs to
completion before the next starts. The GenStage insight is still valuable for the
**fan-out** after bucketizing: pattern discovery, scoring, and suggestions can run
independently.

### Python Translation

```python
"""
GenStage-inspired pipeline for the LWM daemon.

For a single-process daemon, synchronous pipelines with optional
bounded queues are simpler than full demand-driven protocols.
"""
from __future__ import annotations

import queue
from typing import TypeVar, Generic, Callable

T = TypeVar("T")
U = TypeVar("U")


class SyncPipeline:
    """Synchronous pipeline: collect -> transform -> fan-out to consumers.

    No backpressure needed because each stage blocks until complete.
    This is the right choice for our hourly daemon cycle.
    """

    def run_cycle(self, collectors, bucketizer, consumers):
        # Stage 1: Produce raw events
        raw_events = []
        for collector in collectors:
            if collector.is_available():
                raw_events.extend(collector.collect_for_date(date.today()))

        # Stage 2: Transform (ProducerConsumer equivalent)
        life_states = bucketizer.bucketize(raw_events)

        # Stage 3: Fan-out to consumers (each gets all life_states)
        results = {}
        for consumer in consumers:
            results[consumer.name] = consumer.consume(life_states)

        return results


class BoundedPipeline:
    """Async pipeline with bounded queues for backpressure.

    Use this if stages have very different speeds (e.g., LLM calls).
    The bounded queue prevents fast producers from overwhelming slow consumers.
    """

    def __init__(self, max_queue_size: int = 100):
        self.collect_q: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self.state_q: queue.Queue = queue.Queue(maxsize=max_queue_size)

    def producer(self, collectors):
        """Fills collect_q. Blocks if queue is full (backpressure)."""
        for collector in collectors:
            for event in collector.collect_for_date(date.today()):
                self.collect_q.put(event)  # Blocks if full
        self.collect_q.put(None)  # Sentinel

    def transformer(self, bucketizer):
        """Reads from collect_q, writes to state_q."""
        while True:
            event = self.collect_q.get()
            if event is None:
                self.state_q.put(None)
                break
            state = bucketizer.bucketize_single(event)
            if state:
                self.state_q.put(state)

    def consumer(self, handler):
        """Reads from state_q at its own pace."""
        while True:
            state = self.state_q.get()
            if state is None:
                break
            handler.process(state)
```

**Verdict for LWM**: Use `SyncPipeline` for the daemon cycle. The entire
collect-bucketize-score pipeline runs in under a second for a day's data. GenStage's
complexity is not warranted. Reserve `BoundedPipeline` only if we add a streaming
mode that processes events as they arrive.

---

## 4. Phoenix.PubSub — Topic-Based Pub/Sub

### What Elixir Does

Phoenix.PubSub provides topic-based publish/subscribe messaging. Any process can
subscribe to a topic and receive messages broadcast to that topic. The architecture:

1. **Topics are strings** — `"data:collected"`, `"score:changed"`, `"pattern:discovered"`
2. **Subscribers are processes** — each subscribes to topics it cares about
3. **Fan-out is automatic** — publishing to a topic delivers to ALL subscribers
4. **Dispatching is pluggable** — custom dispatcher modules can optimize delivery

```elixir
# Subscribing
Phoenix.PubSub.subscribe(LWM.PubSub, "data:collected")

# Publishing
Phoenix.PubSub.broadcast(LWM.PubSub, "data:collected", %{event_count: 42})

# Receiving (in a GenServer's handle_info)
def handle_info(%{event_count: count}, state) do
  # React to new data being collected
  {:noreply, %{state | pending_analysis: true}}
end
```

The internal mechanism: Phoenix.PubSub uses an ETS table to map topics to subscriber
PIDs. On broadcast, it looks up all subscribers and sends the message to each one.
The default adapter (`PG2`) extends this across distributed nodes via Erlang's
process group module.

The custom dispatcher mechanism is especially clever: Phoenix Channels use a
"fastlaning" dispatcher that encodes a message once and writes directly to all
subscriber sockets, instead of encoding per-subscriber.

### What to STEAL for Python

1. **String-based topic routing** — simple, flexible, no type system overhead.
2. **Fan-out by default** — all subscribers get every message on their topic.
3. **Wildcard topics** — `"data:*"` to subscribe to all data events.
4. **The dispatcher is the bus, not the handler** — handlers don't know about
   each other. The bus handles routing.

### Python Translation

```python
"""
Phoenix.PubSub-inspired event bus for LWM.

This is the central nervous system of the daemon. All communication
between subsystems goes through topic-based events.
"""
from __future__ import annotations

import fnmatch
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("lwm.pubsub")


@dataclass
class Event:
    topic: str
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.monotonic)


# Type alias for handler functions
EventHandler = Callable[[Event], Any]


class EventBus:
    """Topic-based pub/sub with wildcard support and fault isolation.

    Combines Phoenix.PubSub (topic routing) with Supervisor (fault isolation).
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_subscribers: list[tuple[str, EventHandler]] = []
        self._lock = threading.Lock()

    def subscribe(self, topic: str, handler: EventHandler) -> Callable:
        """Subscribe a handler to a topic. Returns an unsubscribe function.

        Supports wildcards: "data.*" matches "data.collected", "data.error"
        """
        with self._lock:
            if "*" in topic:
                self._wildcard_subscribers.append((topic, handler))
            else:
                self._subscribers[topic].append(handler)

        def unsubscribe():
            with self._lock:
                if "*" in topic:
                    self._wildcard_subscribers.remove((topic, handler))
                else:
                    self._subscribers[topic].remove(handler)

        return unsubscribe

    def publish(self, topic: str, payload: dict | None = None) -> None:
        """Broadcast an event to all subscribers on this topic.

        Fan-out: every subscriber gets the message.
        Fault-isolated: one subscriber crashing doesn't affect others.
        """
        event = Event(topic=topic, payload=payload or {})

        # Direct subscribers
        for handler in self._subscribers.get(topic, []):
            self._dispatch_safe(handler, event)

        # Wildcard subscribers
        for pattern, handler in self._wildcard_subscribers:
            if fnmatch.fnmatch(topic, pattern):
                self._dispatch_safe(handler, event)

    def _dispatch_safe(self, handler: EventHandler, event: Event) -> None:
        """One-for-one fault isolation per handler."""
        try:
            handler(event)
        except Exception:
            log.exception(
                "Handler %s crashed on topic %s",
                getattr(handler, "__name__", handler),
                event.topic,
            )

    def schedule(self, topic: str, delay_sec: float,
                 payload: dict | None = None) -> threading.Timer:
        """Schedule a future publish. Returns the timer for cancellation.

        Equivalent to Process.send_after/3.
        """
        timer = threading.Timer(delay_sec, self.publish, args=(topic, payload))
        timer.daemon = True
        timer.start()
        return timer
```

**Topic naming convention for LWM**:

```
collector.tick          # Self-scheduled hourly tick
collector.completed     # Data collection finished
patterns.refresh        # New patterns discovered
patterns.decayed        # Stale patterns removed
score.updated           # Day score recalculated
score.changed           # Score crossed a threshold
experiment.completed    # An experiment finished its duration
experiment.checked      # Experiment status check ran
suggestion.generated    # New suggestions available
notification.send       # Request to send a macOS notification
notification.briefing   # Morning briefing triggered
daemon.started          # Daemon lifecycle
daemon.stopping         # Daemon lifecycle
```

---

## 5. Telemetry — Lightweight Event Emission for Metrics

### What Elixir Does

`:telemetry` is a lightweight, zero-dependency library for dynamic event dispatching
focused on metrics. It is NOT a general pub/sub system — it is specifically optimized
for instrumenting code with timing, counting, and measurement data.

Key characteristics:

1. **Events are lists of atoms**: `[:lwm, :collector, :run]`
2. **Measurements are numeric maps**: `%{duration: 1234, event_count: 42}`
3. **Metadata is context**: `%{source: "chrome", date: ~D[2026-04-07]}`
4. **Handlers execute synchronously** — in the emitting process, no message passing
5. **Single ETS lookup** — near-zero overhead when no handlers are attached

```elixir
# Emitting a telemetry event (in your collector)
:telemetry.span(
  [:lwm, :collector, :run],
  %{source: source_name},
  fn ->
    events = collect_for_date(date)
    {events, %{event_count: length(events)}}
  end
)

# Attaching a handler (at app startup)
:telemetry.attach(
  "lwm-collector-logger",
  [:lwm, :collector, :run, :stop],
  fn _event, measurements, metadata, _config ->
    Logger.info("Collected #{measurements.event_count} events " <>
                "from #{metadata.source} in #{measurements.duration}ns")
  end,
  nil
)
```

The `:telemetry.span/3` function is the key pattern: it automatically emits
`[..., :start]` before execution and `[..., :stop]` after (with duration measurement),
or `[..., :exception]` if the function raises. This is the pattern we want.

### What to STEAL for Python

1. **Separate telemetry from the event bus** — telemetry is for observability, not for
   business logic. Don't mix "score changed" events with "collector took 3.2s" events.
2. **The `span` pattern** — automatically emit start/stop/exception events with timing.
3. **Near-zero overhead** — if no handlers are attached, the cost should be negligible.
4. **Synchronous execution** — telemetry handlers run in the emitting thread, no queuing.

### Python Translation

```python
"""
Erlang :telemetry inspired instrumentation for LWM.

Separate from the EventBus. This is for timing, counting, and metrics.
Zero overhead when no handlers are attached.
"""
from __future__ import annotations

import functools
import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Callable

log = logging.getLogger("lwm.telemetry")

# Global handler registry: event_name -> [handler_fn]
_handlers: dict[tuple[str, ...], list[Callable]] = defaultdict(list)


def attach(handler_id: str, event_name: tuple[str, ...],
           handler: Callable, config: Any = None) -> None:
    """Register a handler for a telemetry event.

    handler signature: (event_name, measurements, metadata, config) -> None
    """
    _handlers[event_name].append((handler_id, handler, config))


def detach(handler_id: str) -> None:
    """Remove a handler by ID."""
    for event_name, handlers in _handlers.items():
        _handlers[event_name] = [
            (hid, h, c) for hid, h, c in handlers if hid != handler_id
        ]


def execute(event_name: tuple[str, ...], measurements: dict,
            metadata: dict | None = None) -> None:
    """Emit a telemetry event. Handlers run synchronously.

    Near-zero cost when no handlers are attached (just a dict lookup).
    """
    handlers = _handlers.get(event_name)
    if not handlers:
        return  # Fast path: no handlers, no cost

    metadata = metadata or {}
    for handler_id, handler, config in handlers:
        try:
            handler(event_name, measurements, metadata, config)
        except Exception:
            log.exception("Telemetry handler %s failed", handler_id)


@contextmanager
def span(event_prefix: tuple[str, ...], metadata: dict | None = None):
    """Context manager that emits start/stop/exception events with timing.

    Equivalent to :telemetry.span/3.

    Usage:
        with telemetry.span(("lwm", "collector", "run"), {"source": "chrome"}):
            events = collector.collect_for_date(today)
    """
    metadata = metadata or {}
    start_time = time.monotonic()
    system_time = time.time()

    execute((*event_prefix, "start"),
            {"system_time": system_time}, metadata)

    try:
        yield
    except Exception as exc:
        duration = time.monotonic() - start_time
        execute((*event_prefix, "exception"),
                {"duration": duration}, {**metadata, "exception": exc})
        raise
    else:
        duration = time.monotonic() - start_time
        execute((*event_prefix, "stop"),
                {"duration": duration}, metadata)


def timed(event_prefix: tuple[str, ...]):
    """Decorator version of span().

    Usage:
        @telemetry.timed(("lwm", "collector", "run"))
        def collect_for_date(self, date):
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            metadata = {"function": fn.__name__}
            with span(event_prefix, metadata):
                return fn(*args, **kwargs)
        return wrapper
    return decorator


# --- Convenience: built-in log handler ---

def log_handler(event_name: tuple[str, ...], measurements: dict,
                metadata: dict, _config: Any) -> None:
    """Default handler that logs telemetry events."""
    name = ".".join(event_name)
    if "duration" in measurements:
        log.info("%s completed in %.3fs | %s",
                 name, measurements["duration"], metadata)
    else:
        log.info("%s | measurements=%s metadata=%s",
                 name, measurements, metadata)
```

**Usage in the daemon**:

```python
# At daemon startup:
telemetry.attach("log-all", ("lwm", "collector", "run", "stop"),
                 telemetry.log_handler)

# In the collector:
with telemetry.span(("lwm", "collector", "run"), {"source": "chrome"}):
    events = chrome_collector.collect_for_date(today)

# Output: lwm.collector.run.stop completed in 0.342s | {'source': 'chrome'}
```

---

## 6. Broadway — Data Processing Pipelines

### What Elixir Does

Broadway is a layer on top of GenStage that massively simplifies building data
processing pipelines. It handles:

1. **Batching** — collect N messages or wait T milliseconds, whichever comes first
2. **Concurrency** — multiple processor and batcher stages run in parallel
3. **Acknowledgement** — messages are acked/nacked after processing
4. **Graceful shutdown** — drain all in-flight messages before stopping
5. **Rate limiting** — control how fast messages are consumed

```elixir
defmodule LWM.CollectionPipeline do
  use Broadway

  def start_link(_opts) do
    Broadway.start_link(__MODULE__,
      name: __MODULE__,
      producer: [
        module: {LWM.SourceProducer, []},
        concurrency: 1
      ],
      processors: [
        default: [concurrency: 4]  # 4 concurrent processors
      ],
      batchers: [
        storage: [batch_size: 100, batch_timeout: 5_000],
        analysis: [batch_size: 50, batch_timeout: 10_000]
      ]
    )
  end

  # Process individual messages
  def handle_message(:default, message, _context) do
    event = normalize_event(message.data)
    message
    |> Message.update_data(fn _ -> event end)
    |> Message.put_batcher(:storage)  # Route to storage batcher
  end

  # Process batches
  def handle_batch(:storage, messages, _batch_info, _context) do
    events = Enum.map(messages, & &1.data)
    SQLiteStore.save_raw_events(events)  # Bulk insert
    messages
  end

  def handle_batch(:analysis, messages, _batch_info, _context) do
    events = Enum.map(messages, & &1.data)
    PatternDiscovery.analyze_batch(events)
    messages
  end
end
```

The key insight: Broadway's batching is **batch by size OR time, whichever comes first**.
This is perfect for collection: collect up to 100 events, OR flush every 5 seconds.

### What to STEAL for Python

1. **Batch-then-process** — instead of saving each event individually, batch them and
   bulk-insert. Our SQLite store already does this with `save_raw_events(list)`.
2. **Batch timeout** — don't wait forever for a full batch. If 5 seconds pass with only
   3 events, process those 3.
3. **Route to different batchers** — some events go to storage, some to analysis. The
   `put_batcher` concept is a message tag/router.

### Python Translation

```python
"""
Broadway-inspired batch processing for LWM collection.

In a single-process daemon, batching is mostly about efficient I/O:
bulk SQLite inserts instead of one-at-a-time.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class BatchConfig:
    max_size: int = 100       # Flush when this many items accumulate
    timeout_sec: float = 5.0  # Flush after this many seconds regardless


class BatchProcessor:
    """Accumulates items and flushes when batch is full or timeout expires.

    Equivalent to a Broadway batcher.
    """

    def __init__(self, config: BatchConfig, flush_fn):
        self.config = config
        self.flush_fn = flush_fn
        self._buffer: list = []
        self._last_flush: float = time.monotonic()

    def add(self, item) -> None:
        """Add an item. Flushes if batch is full."""
        self._buffer.append(item)
        if len(self._buffer) >= self.config.max_size:
            self.flush()

    def tick(self) -> None:
        """Check timeout. Call this periodically."""
        if (self._buffer
                and time.monotonic() - self._last_flush > self.config_sec):
            self.flush()

    def flush(self) -> None:
        """Process the current batch and reset."""
        if not self._buffer:
            return
        batch = self._buffer
        self._buffer = []
        self._last_flush = time.monotonic()
        self.flush_fn(batch)


class CollectionPipeline:
    """Broadway-style pipeline: collect -> batch -> store + analyze."""

    def __init__(self, store, analyzer):
        self.storage_batch = BatchProcessor(
            BatchConfig(max_size=100, timeout_sec=5.0),
            flush_fn=store.save_raw_events,
        )
        self.analysis_batch = BatchProcessor(
            BatchConfig(max_size=50, timeout_sec=10.0),
            flush_fn=analyzer.analyze_batch,
        )

    def process_event(self, event) -> None:
        """Route each event to appropriate batchers."""
        # All events go to storage
        self.storage_batch.add(event)

        # Only interesting events go to analysis
        if event.duration_seconds and event.duration_seconds > 60:
            self.analysis_batch.add(event)

    def finalize(self) -> None:
        """Flush remaining items (graceful shutdown)."""
        self.storage_batch.flush()
        self.analysis_batch.flush()
```

**Verdict for LWM**: Batching is already implicit in our design — collectors return
full lists and `save_raw_events()` does a bulk insert. The Broadway insight to keep
is the **timeout-based flush** for any future streaming mode, and the **multiple
batcher routing** if we want events to flow to both storage and analysis.

---

## 7. Registry — Process Discovery

### What Elixir Does

Elixir's Registry provides a way to name processes and look them up by key instead of
by PID. This is crucial when you have dynamic processes (e.g., one GenServer per data
source) and need to find them at runtime.

```elixir
# Start the registry
{:ok, _} = Registry.start_link(keys: :unique, name: LWM.Registry)

# Register a process with a key
Registry.register(LWM.Registry, {:collector, "chrome"}, [])

# Look up a process by key
[{pid, _value}] = Registry.lookup(LWM.Registry, {:collector, "chrome"})

# Use {:via, Registry, ...} tuple for automatic registration at start
defmodule LWM.Collector do
  use GenServer

  def start_link(source) do
    GenServer.start_link(__MODULE__, source,
      name: {:via, Registry, {LWM.Registry, {:collector, source}}})
  end
end
```

The `{:via, Registry, ...}` tuple is elegant: it tells the BEAM to automatically
register the process with the Registry when it starts, and to look up the process
through the Registry when someone sends it a message.

### What to STEAL for Python

1. **Name-based handler lookup** — find a handler by name instead of holding a reference.
2. **Dynamic registration** — handlers register themselves when they start.
3. **The `via` pattern** — automatic registration on construction.

### Python Translation

```python
"""
Elixir Registry-inspired handler discovery for LWM.

Instead of passing handler references around, look them up by name.
Useful for CLI commands that need to query specific subsystems.
"""
from __future__ import annotations

from typing import Any


class HandlerRegistry:
    """Name-based handler registry.

    Handlers register themselves by name. Other code can look them up.
    """

    def __init__(self) -> None:
        self._registry: dict[str, Handler] = {}

    def register(self, name: str, handler: Handler) -> None:
        if name in self._registry:
            raise ValueError(f"Handler already registered: {name}")
        self._registry[name] = handler

    def lookup(self, name: str) -> Handler | None:
        return self._registry.get(name)

    def lookup_prefix(self, prefix: str) -> list[tuple[str, Handler]]:
        """Find all handlers whose name starts with prefix.

        Like Registry with :duplicate keys.
        """
        return [
            (name, handler)
            for name, handler in self._registry.items()
            if name.startswith(prefix)
        ]

    def all(self) -> dict[str, Handler]:
        return dict(self._registry)


# Decorator for automatic registration (the {:via, Registry, ...} pattern)
def registered(name: str):
    """Class decorator that auto-registers a handler on instantiation.

    Usage:
        @registered("collector.chrome")
        class ChromeCollectorHandler(Handler):
            ...
    """
    def decorator(cls):
        original_init = cls.__init__

        def new_init(self, *args, registry=None, **kwargs):
            original_init(self, *args, **kwargs)
            if registry:
                registry.register(name, self)

        cls.__init__ = new_init
        cls._registry_name = name
        return cls

    return decorator
```

**Usage in LWM**:

```python
registry = HandlerRegistry()

# Register handlers
collector = CollectorHandler(registry=registry)  # auto-registered

# Look up from CLI
handler = registry.lookup("collector.chrome")
if handler:
    status = handler.handle(Event(topic="collector.get_status"))
```

---

## 8. Task.async/Task.await — Supervised Async Work

### What Elixir Does

`Task.async` spawns a supervised process to do work, and `Task.await` blocks until the
result arrives (with a timeout). Three patterns:

1. **Fire-and-forget**: `Task.Supervisor.start_child(sup, fn -> ... end)` — no result
2. **Async/await**: `task = Task.async(fn -> ... end); result = Task.await(task, 5000)`
3. **Yield with fallback**: `Task.yield(task, 5000) || Task.shutdown(task)`

The third pattern is the most interesting: `yield` returns `{:ok, result}` if the task
finished, or `nil` if it timed out. You can then decide to wait longer or shut it down.
This is perfect for LLM calls.

```elixir
# Pattern 3: yield with timeout and fallback
defmodule LWM.NarrativeGenerator do
  def generate_with_timeout(prompt, timeout \\ 30_000) do
    task = Task.Supervisor.async_nolink(LWM.TaskSupervisor, fn ->
      LLM.generate(prompt)
    end)

    case Task.yield(task, timeout) do
      {:ok, narrative} ->
        narrative

      nil ->
        Task.shutdown(task)
        # Return a fallback instead of waiting forever
        "Unable to generate narrative within #{timeout}ms"
    end
  end
end
```

The `async_nolink` variant is critical: if the task crashes, the caller doesn't crash
with it. Instead, the caller gets `{:exit, reason}` from `Task.yield`.

### What to STEAL for Python

1. **Timeout-with-fallback for LLM calls** — never block forever waiting for Gemini/MLX.
2. **The yield/shutdown pattern** — check if ready, if not, cancel and use a fallback.
3. **Supervised tasks** — if the task crashes, don't crash the caller.

### Python Translation

```python
"""
Task.async/await/yield inspired patterns for LWM.

Primarily for LLM calls (Gemini/MLX) that might be slow or fail.
"""
from __future__ import annotations

import concurrent.futures
import logging
from typing import Any, Callable, TypeVar

log = logging.getLogger("lwm.task")

T = TypeVar("T")


class SupervisedTask:
    """Task with timeout, fallback, and crash isolation.

    Equivalent to Task.Supervisor.async_nolink + Task.yield + Task.shutdown.
    """

    def __init__(self, fn: Callable[..., T], *args, **kwargs):
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._future = self._executor.submit(fn, *args, **kwargs)

    def await_result(self, timeout_sec: float = 30.0) -> T:
        """Block until result or raise TimeoutError.

        Equivalent to Task.await(task, timeout).
        """
        return self._future.result(timeout=timeout_sec)

    def yield_result(self, timeout_sec: float = 30.0) -> T | None:
        """Return result if ready within timeout, else None.

        Equivalent to Task.yield(task, timeout).
        Does NOT raise on timeout -- returns None instead.
        """
        try:
            return self._future.result(timeout=timeout_sec)
        except concurrent.futures.TimeoutError:
            return None
        except Exception:
            log.exception("Task crashed")
            return None

    def shutdown(self) -> None:
        """Cancel the task if still running.

        Equivalent to Task.shutdown(task).
        """
        self._future.cancel()
        self._executor.shutdown(wait=False)

    def yield_or_fallback(self, timeout_sec: float, fallback: T) -> T:
        """Yield with timeout, return fallback if not ready.

        The most useful pattern: try the slow thing, but always return
        something within a bounded time.
        """
        result = self.yield_result(timeout_sec)
        if result is None:
            self.shutdown()
            return fallback
        return result


def async_task(fn: Callable[..., T], *args, **kwargs) -> SupervisedTask:
    """Spawn a supervised async task.

    Usage:
        task = async_task(llm.generate, prompt)
        narrative = task.yield_or_fallback(
            timeout_sec=30,
            fallback="Score: 72%. Details unavailable."
        )
    """
    return SupervisedTask(fn, *args, **kwargs)


def fan_out(fns: list[Callable[..., T]], timeout_sec: float = 30.0,
            fallback: T = None) -> list[T]:
    """Run multiple functions concurrently and collect results.

    Equivalent to Task.async_stream with ordered results.
    """
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(fn) for fn in fns]
        results = []
        for future in futures:
            try:
                results.append(future.result(timeout=timeout_sec))
            except (concurrent.futures.TimeoutError, Exception):
                results.append(fallback)
        return results
```

**Usage for LLM narrative generation**:

```python
task = async_task(gemini_client.generate, prompt)
narrative = task.yield_or_fallback(
    timeout_sec=30,
    fallback="Data collected but narrative generation timed out."
)
```

---

## 9. Go Channels + Select — Fan-Out/Fan-In with Timer Multiplexing

### What Go Does

Go's `select` statement multiplexes across multiple channels, blocking until one is
ready. Combined with `time.Ticker`, this creates an elegant daemon loop that handles
multiple periodic tasks at different intervals:

```go
func daemon(ctx context.Context) {
    collectTicker := time.NewTicker(1 * time.Hour)
    scoreTicker   := time.NewTicker(15 * time.Minute)
    decayTicker   := time.NewTicker(6 * time.Hour)
    experimentCh  := make(chan ExperimentResult)

    defer collectTicker.Stop()
    defer scoreTicker.Stop()
    defer decayTicker.Stop()

    for {
        select {
        case <-collectTicker.C:
            events := collectAll()
            go analyzeAsync(events, experimentCh) // Fan-out to goroutine

        case <-scoreTicker.C:
            score := scoreToday()
            if scoreChanged(score) {
                sendNotification(score)
            }

        case <-decayTicker.C:
            decayStalePatterns()

        case result := <-experimentCh:
            handleExperimentResult(result) // Fan-in from goroutine

        case <-ctx.Done():
            fmt.Println("Daemon stopping")
            return
        }
    }
}
```

The beauty: `select` blocks until ANY of the channels has data. Different tickers fire
at different rates. The `ctx.Done()` channel provides graceful shutdown. Fan-out
happens by launching goroutines; fan-in happens by reading from a shared result channel.

### The Fan-Out/Fan-In Pattern

```go
func analyzeParallel(events []RawEvent) []PatternResult {
    resultCh := make(chan PatternResult, 5)

    // Fan-out: launch 5 analyzers concurrently
    analyzers := []func(){
        func() { resultCh <- detectRoutines(events) },
        func() { resultCh <- detectCorrelations(events) },
        func() { resultCh <- detectRhythms(events) },
        func() { resultCh <- detectTriggers(events) },
        func() { resultCh <- detectTimeSinks(events) },
    }

    for _, analyze := range analyzers {
        go analyze()
    }

    // Fan-in: collect all results
    results := make([]PatternResult, 0, 5)
    for i := 0; i < 5; i++ {
        results = append(results, <-resultCh)
    }
    return results
}
```

### What to STEAL for Python

1. **Multi-rate ticker loop** — different subsystems tick at different intervals.
   Don't force everything into a single hourly cycle.
2. **Select-style multiplexing** — react to whichever event comes first.
3. **Graceful shutdown via a "done" channel** — clean way to stop the daemon.
4. **Fan-out/fan-in for pattern analysis** — run all 5 statistical detectors
   concurrently.

### Python Translation

```python
"""
Go select + ticker inspired daemon loop for LWM.

Uses threading.Event for shutdown signaling and a scheduler
for multi-rate tickers.
"""
from __future__ import annotations

import logging
import sched
import signal
import threading
import time
from typing import Callable

log = logging.getLogger("lwm.daemon")


class MultiRateDaemon:
    """Daemon with multiple subsystems ticking at different rates.

    Inspired by Go's select + multiple Tickers pattern.
    """

    def __init__(self) -> None:
        self._scheduler = sched.scheduler(time.monotonic, time.sleep)
        self._shutdown = threading.Event()
        self._tasks: dict[str, float] = {}  # name -> interval_sec

    def every(self, interval_sec: float, name: str,
              fn: Callable) -> "MultiRateDaemon":
        """Register a periodic task (equivalent to time.NewTicker)."""
        self._tasks[name] = interval_sec

        def _tick():
            if self._shutdown.is_set():
                return
            try:
                fn()
            except Exception:
                log.exception("Task %s failed", name)
            # Re-schedule (like Go's ticker auto-repeating)
            if not self._shutdown.is_set():
                self._scheduler.enter(interval_sec, 1, _tick)

        # Schedule first tick
        self._scheduler.enter(interval_sec, 1, _tick)
        return self

    def run(self) -> None:
        """Run the daemon (blocks). Ctrl+C to stop.

        Equivalent to Go's `for { select { ... } }` loop.
        """
        # Handle SIGTERM/SIGINT for graceful shutdown (like ctx.Done())
        def _handle_signal(signum, frame):
            log.info("Received signal %d, shutting down...", signum)
            self._shutdown.set()

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        log.info("Daemon started with tasks: %s",
                 {name: f"{interval}s" for name, interval in self._tasks.items()})

        while not self._shutdown.is_set():
            # Run pending events (like Go's select waiting for the next channel)
            if not self._scheduler.empty():
                self._scheduler.run(blocking=False)
            self._shutdown.wait(timeout=0.1)  # Short sleep to avoid busy-wait

        log.info("Daemon stopped.")


def fan_out_fan_in(tasks: list[Callable], timeout_sec: float = 30.0) -> list:
    """Run multiple tasks concurrently, collect all results.

    Go-style fan-out/fan-in:
    - Fan-out: launch each task in a thread
    - Fan-in: collect results into a list
    """
    import concurrent.futures

    results = [None] * len(tasks)
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future_to_idx = {
            pool.submit(task): i for i, task in enumerate(tasks)
        }
        for future in concurrent.futures.as_completed(
            future_to_idx, timeout=timeout_sec
        ):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception:
                log.exception("Fan-out task %d failed", idx)

    return results


# --- Usage for LWM ---

def build_daemon(settings, store) -> MultiRateDaemon:
    daemon = MultiRateDaemon()

    daemon.every(3600, "collect", lambda: collect_cycle(settings, store))
    daemon.every(900, "score", lambda: score_today(settings, store))
    daemon.every(21600, "decay_patterns", lambda: decay_stale_patterns(store))
    daemon.every(86400, "check_experiments", lambda: check_experiments(store))
    daemon.every(86400, "morning_briefing", lambda: send_morning_briefing(store))

    return daemon
```

---

## 10. Rust Tokio Broadcast Channels — Multi-Consumer Event Distribution

### What Rust Does

Tokio's `broadcast` channel is multi-producer, multi-consumer: every receiver sees every
message. The value is stored once and cloned on demand for each receiver. When all
receivers have consumed the clone, the original is dropped.

```rust
use tokio::sync::broadcast;

#[tokio::main]
async fn main() {
    // Create channel with capacity 16
    let (tx, _rx) = broadcast::channel::<DaemonEvent>(16);

    // Each subsystem gets its own receiver
    let mut collector_rx = tx.subscribe();
    let mut scorer_rx = tx.subscribe();
    let mut notifier_rx = tx.subscribe();

    // Spawn subsystems
    tokio::spawn(async move {
        loop {
            match collector_rx.recv().await {
                Ok(DaemonEvent::Tick) => { collect_all().await; }
                Ok(DaemonEvent::Shutdown) => break,
                _ => {}
            }
        }
    });

    tokio::spawn(async move {
        loop {
            match scorer_rx.recv().await {
                Ok(DaemonEvent::DataReady(events)) => {
                    let score = score_day(&events).await;
                    tx.send(DaemonEvent::ScoreUpdated(score)).unwrap();
                }
                Ok(DaemonEvent::Shutdown) => break,
                _ => {}
            }
        }
    });

    // Broadcast to all
    tx.send(DaemonEvent::Tick).unwrap();
}
```

Key design choices:

- **Bounded capacity** — if a receiver falls behind, it misses messages (gets `Lagged` error)
- **Clone on demand** — efficient memory use, no per-receiver copies until consumed
- **Subscribe at any time** — new receivers only see messages sent after they subscribe

### What to STEAL for Python

1. **Bounded broadcast** — if a subscriber is slow, it misses messages rather than
   causing backpressure on the sender. For a notification handler that's slow, this is
   the right choice: don't delay scoring just because notification sending is slow.
2. **Every subscriber sees every message** — this is pure fan-out, unlike a work queue
   where each message goes to one consumer.
3. **Late subscribers** — handlers added after the daemon starts only see future events.

### Python Translation

```python
"""
Tokio broadcast channel inspired multi-consumer event distribution.

Every subscriber sees every event. Bounded: slow subscribers miss events
rather than causing backpressure.
"""
from __future__ import annotations

import collections
import threading
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class BroadcastChannel:
    """Multi-producer, multi-consumer broadcast channel.

    Bounded: if a receiver falls behind by more than `capacity` messages,
    it skips to the latest (like Tokio's Lagged behavior).
    """

    def __init__(self, capacity: int = 64) -> None:
        self._buffer: collections.deque = collections.deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._sequence: int = 0
        self._receivers: list["BroadcastReceiver"] = []

    def send(self, value: Any) -> int:
        """Broadcast a value to all receivers. Returns number of receivers."""
        with self._lock:
            self._buffer.append((self._sequence, value))
            self._sequence += 1
            # Wake up all waiting receivers
            for rx in self._receivers:
                rx._notify.set()
            return len(self._receivers)

    def subscribe(self) -> "BroadcastReceiver":
        """Create a new receiver. Only sees messages sent AFTER this call."""
        rx = BroadcastReceiver(self, self._sequence)
        with self._lock:
            self._receivers.append(rx)
        return rx


class BroadcastReceiver:
    """Receiver end of a broadcast channel."""

    def __init__(self, channel: BroadcastChannel, start_seq: int) -> None:
        self._channel = channel
        self._next_seq = start_seq
        self._notify = threading.Event()

    def recv(self, timeout: float | None = None) -> Any | None:
        """Receive next message. Blocks until available or timeout."""
        while True:
            with self._channel._lock:
                for seq, value in self._channel._buffer:
                    if seq >= self._next_seq:
                        self._next_seq = seq + 1
                        return value

            # No message available, wait
            self._notify.clear()
            if not self._notify.wait(timeout=timeout):
                return None  # Timeout

    def try_recv(self) -> Any | None:
        """Non-blocking receive. Returns None if no message available."""
        return self.recv(timeout=0)
```

---

## 11. Clojure add-watch on Atoms — Reactive State

### What Clojure Does

Clojure atoms hold immutable values and support `add-watch` — a function that fires
whenever the atom's value changes. The watch function receives the old and new state,
enabling reactive programming without explicit pub/sub.

```clojure
;; Define observable state
(def day-score (atom {:total 0.0 :breakdown {}}))

;; Add a watcher that fires on every state change
(add-watch day-score :score-change-notifier
  (fn [key ref old-state new-state]
    (let [delta (- (:total new-state) (:total old-state))]
      (when (> (abs delta) 0.05)
        (send-notification
          (str "Score " (if (pos? delta) "up" "down")
               ": " (:total old-state) " -> " (:total new-state)))))))

;; Add a watcher for logging
(add-watch day-score :score-logger
  (fn [_ _ old new]
    (println "Score changed:" (:total old) "->" (:total new))))

;; When state changes, ALL watchers fire automatically
(swap! day-score assoc :total 0.75)
;; Output: "Score changed: 0.0 -> 0.75"
;; Also sends notification because delta > 0.05
```

The elegance: state changes and reactions are decoupled. The code that updates the score
doesn't know about notifications or logging. Watchers are added/removed independently.

Key semantics:
- Watchers fire **synchronously** on the same thread that changed the atom
- Watchers receive **(old-state, new-state)** — they can compute deltas
- Multiple watchers per atom, identified by a key for removal
- Watchers should be fast (since they're synchronous)

### What to STEAL for Python

1. **Observable state with automatic reactions** — when the score changes, notifications
   fire automatically without the scorer knowing about notifications.
2. **Old/new state in callbacks** — enables delta computation (score went up 5%).
3. **Named watchers** — add/remove watchers by key.
4. **Synchronous execution** — watchers run inline, keeping things simple.

### Python Translation

```python
"""
Clojure atom + add-watch inspired reactive state for LWM.

Observable state containers that automatically notify watchers on change.
"""
from __future__ import annotations

import copy
import logging
from typing import Any, Callable, Generic, TypeVar

log = logging.getLogger("lwm.state")

T = TypeVar("T")

# Watcher signature: (key, old_value, new_value) -> None
Watcher = Callable[[str, Any, Any], None]


class ObservableState:
    """Clojure atom equivalent: holds state and notifies watchers on change.

    Usage:
        score = ObservableState("score", {"total": 0.0})

        score.add_watch("notifier", lambda key, old, new:
            send_notification(f"Score: {old['total']} -> {new['total']}")
            if abs(new['total'] - old['total']) > 0.05
            else None
        )

        score.swap(lambda s: {**s, "total": 0.75})
        # Watcher fires automatically
    """

    def __init__(self, name: str, initial_value: Any = None) -> None:
        self._name = name
        self._value = initial_value
        self._watchers: dict[str, Watcher] = {}

    @property
    def value(self) -> Any:
        """Dereference the state (equivalent to @atom or deref)."""
        return self._value

    def reset(self, new_value: Any) -> None:
        """Replace the value entirely (equivalent to reset!)."""
        old_value = self._value
        self._value = new_value
        self._notify_watchers(old_value, new_value)

    def swap(self, fn: Callable[[Any], Any]) -> Any:
        """Apply a function to the current value (equivalent to swap!).

        fn receives the current value and returns the new value.
        """
        old_value = self._value
        self._value = fn(copy.deepcopy(old_value))
        self._notify_watchers(old_value, self._value)
        return self._value

    def add_watch(self, key: str, watcher: Watcher) -> None:
        """Register a watcher. Fires on every state change."""
        self._watchers[key] = watcher

    def remove_watch(self, key: str) -> None:
        """Unregister a watcher by key."""
        self._watchers.pop(key, None)

    def _notify_watchers(self, old_value: Any, new_value: Any) -> None:
        """Call all watchers synchronously."""
        for key, watcher in self._watchers.items():
            try:
                watcher(key, old_value, new_value)
            except Exception:
                log.exception("Watcher %s on %s failed", key, self._name)


# --- Usage for LWM ---

# Daemon-wide observable state
day_score = ObservableState("day_score", {"total": 0.0, "breakdown": {}})
active_patterns = ObservableState("patterns", [])
active_experiments = ObservableState("experiments", [])

# Wire up reactions
day_score.add_watch("score_notification", lambda key, old, new:
    send_notification(
        "LWM Score Change",
        f"Score {'up' if new['total'] > old['total'] else 'down'}: "
        f"{old['total']:.0%} -> {new['total']:.0%}"
    )
    if abs(new["total"] - old["total"]) > 0.05 else None
)

day_score.add_watch("score_logger", lambda key, old, new:
    log.info("Score: %.1f%% -> %.1f%%", old["total"] * 100, new["total"] * 100)
)

active_patterns.add_watch("pattern_suggestions", lambda key, old, new:
    regenerate_suggestions(new) if len(new) != len(old) else None
)
```

**This is perhaps the most powerful pattern for LWM.** The current daemon has score
change detection hardcoded in the main loop. With `ObservableState`, the scorer just
updates the score, and the notification system reacts automatically. Clean separation.

---

## 12. Swift Combine — Publisher-Subscriber Pipelines

### What Swift Does

Combine is Apple's reactive framework built around three concepts:

1. **Publishers** — emit values over time (like RxPY `Observable`)
2. **Operators** — transform, filter, combine streams (`map`, `filter`, `debounce`)
3. **Subscribers** — consume values (`sink`, `assign`)

Two key Subject types:
- **PassthroughSubject** — no memory, just passes values through (like our EventBus)
- **CurrentValueSubject** — holds the current value, new subscribers get it immediately
  (like Clojure atoms)

```swift
import Combine

class DaemonController {
    // Subjects (event sources)
    let dataCollected = PassthroughSubject<CollectionResult, Never>()
    let scoreUpdated = CurrentValueSubject<DayScore, Never>(DayScore.empty)

    private var cancellables = Set<AnyCancellable>()

    func setupPipeline() {
        // When data is collected, score the day
        dataCollected
            .map { result in scoreDay(result.events) }
            .sink { [weak self] score in
                self?.scoreUpdated.send(score)
            }
            .store(in: &cancellables)

        // When score changes by >5%, send notification
        scoreUpdated
            .removeDuplicates()
            .scan((DayScore.empty, DayScore.empty)) { prev, new in
                (prev.1, new)  // Keep (old, new) tuple
            }
            .filter { old, new in abs(new.total - old.total) > 0.05 }
            .sink { old, new in
                sendNotification(
                    "Score \(new.total > old.total ? "up" : "down"): "
                    + "\(old.total) -> \(new.total)"
                )
            }
            .store(in: &cancellables)

        // Debounce pattern refresh (don't refresh on every event)
        dataCollected
            .debounce(for: .seconds(30), scheduler: RunLoop.main)
            .sink { _ in refreshPatterns() }
            .store(in: &cancellables)
    }
}
```

Key Combine concepts relevant to us:

- **`scan`** — accumulate state across events (like `reduce` but emits intermediates).
  Perfect for tracking old/new score.
- **`debounce`** — wait until events stop arriving for N seconds before processing.
  Perfect for pattern refresh (don't refresh on every single event).
- **`removeDuplicates`** — only emit when value actually changes.
- **`AnyCancellable` + `store(in:)`** — subscription lifetime management. When the
  owner is deallocated, all subscriptions are cancelled.

### What to STEAL for Python

1. **Operator chaining on event streams** — `filter`, `map`, `debounce` as composable
   transforms before reaching handlers.
2. **`scan` for old/new tracking** — cleaner than manually tracking `last_score`.
3. **`debounce` for bursty events** — if 50 events arrive at once, only trigger pattern
   refresh once, 30 seconds after the last event.
4. **Subscription lifetime management** — subscriptions should auto-cancel when their
   owner is cleaned up.

### Python Translation

```python
"""
Swift Combine-inspired reactive operators for LWM event streams.

Not a full reactive framework -- just the specific operators that
are useful for our daemon.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable


class EventStream:
    """A chainable event stream with Combine-like operators.

    Usage:
        bus.stream("score.updated")
            .scan(lambda acc, val: (acc[1], val), (None, None))
            .filter(lambda old_new: old_new[0] is not None
                    and abs(old_new[1] - old_new[0]) > 0.05)
            .sink(lambda old_new: send_notification(...))
    """

    def __init__(self) -> None:
        self._handlers: list[Callable] = []

    def _emit(self, value: Any) -> None:
        for handler in self._handlers:
            try:
                handler(value)
            except Exception:
                pass

    def map(self, fn: Callable) -> "EventStream":
        """Transform each value."""
        output = EventStream()
        self._handlers.append(lambda v: output._emit(fn(v)))
        return output

    def filter(self, predicate: Callable) -> "EventStream":
        """Only pass values that match the predicate."""
        output = EventStream()
        self._handlers.append(
            lambda v: output._emit(v) if predicate(v) else None
        )
        return output

    def scan(self, fn: Callable, initial: Any = None) -> "EventStream":
        """Accumulate state across events.

        fn(accumulator, new_value) -> new_accumulator
        Emits the accumulator after each event.
        """
        output = EventStream()
        state = {"acc": initial}

        def _scan(value):
            state["acc"] = fn(state["acc"], value)
            output._emit(state["acc"])

        self._handlers.append(_scan)
        return output

    def debounce(self, delay_sec: float) -> "EventStream":
        """Only emit after no events for delay_sec seconds.

        Resets the timer on each new event.
        """
        output = EventStream()
        state = {"timer": None}

        def _debounce(value):
            if state["timer"]:
                state["timer"].cancel()
            state["timer"] = threading.Timer(
                delay_sec, lambda: output._emit(value)
            )
            state["timer"].daemon = True
            state["timer"].start()

        self._handlers.append(_debounce)
        return output

    def remove_duplicates(self, key: Callable | None = None) -> "EventStream":
        """Only emit when the value changes."""
        output = EventStream()
        state = {"last": object()}  # Sentinel

        def _dedup(value):
            k = key(value) if key else value
            if k != state["last"]:
                state["last"] = k
                output._emit(value)

        self._handlers.append(_dedup)
        return output

    def sink(self, handler: Callable) -> "Cancellable":
        """Terminal subscriber. Returns a Cancellable for lifetime management."""
        self._handlers.append(handler)
        return Cancellable(lambda: self._handlers.remove(handler))


class Cancellable:
    """Subscription lifetime token. Cancel to unsubscribe.

    Equivalent to Swift's AnyCancellable.
    """

    def __init__(self, cancel_fn: Callable) -> None:
        self._cancel_fn = cancel_fn
        self._cancelled = False

    def cancel(self) -> None:
        if not self._cancelled:
            self._cancel_fn()
            self._cancelled = True

    def __del__(self):
        self.cancel()


class CancellableStore:
    """Collection of cancellables. Equivalent to Set<AnyCancellable>.

    All subscriptions are cancelled when the store is garbage-collected
    or explicitly cleared.
    """

    def __init__(self) -> None:
        self._items: list[Cancellable] = []

    def add(self, cancellable: Cancellable) -> None:
        self._items.append(cancellable)

    def cancel_all(self) -> None:
        for item in self._items:
            item.cancel()
        self._items.clear()

    def __del__(self):
        self.cancel_all()
```

**Usage for LWM score notification pipeline**:

```python
# Create stream from event bus
score_stream = bus.stream("score.updated")

# Combine-style pipeline: detect significant score changes
cancellable = (
    score_stream
    .scan(lambda acc, score: (acc[1], score), (0.0, 0.0))
    .filter(lambda pair: pair[0] is not None
            and abs(pair[1] - pair[0]) > 0.05)
    .sink(lambda pair: send_notification(
        "LWM Score Change",
        f"Score {'up' if pair[1] > pair[0] else 'down'}: "
        f"{pair[0]:.0%} -> {pair[1]:.0%}"
    ))
)

# Debounced pattern refresh
pattern_cancel = (
    bus.stream("data.collected")
    .debounce(delay_sec=30)
    .sink(lambda _: refresh_patterns())
)
```

---

## 13. Synthesis: The LWM Daemon Architecture

### Current State (Flat While-True Loop)

```python
# daemon/collector.py (current)
while True:
    collected = _collect_cycle(settings, store)     # All collectors
    current_score = _score_today(settings, store)   # Score
    if score_changed: send_notification(...)        # Notify
    time.sleep(interval_minutes * 60)               # Sleep
```

Problems:
1. **Single rate** — everything runs hourly. Scoring could run every 15 min.
2. **Silent failures** — `except Exception: pass` swallows errors.
3. **No fault isolation** — if scoring crashes, collection stops too.
4. **No observability** — no timing, no metrics, no telemetry.
5. **Tight coupling** — scorer knows about notifications, collection knows about scoring.
6. **No graceful shutdown** — `KeyboardInterrupt` with no cleanup.

### Proposed Architecture (Stealing from Everyone)

```
                          +------------------+
                          | SupervisedEventBus|  <-- Elixir Supervisor + Phoenix.PubSub
                          | (fault isolation  |
                          |  + topic routing) |
                          +--------+---------+
                                   |
            +----------+-----------+----------+-----------+
            |          |           |          |           |
   +--------+--+ +-----+----+ +---+------+ +-+--------+ +---+--------+
   | Collector  | | Pattern  | | Scorer   | |Experiment| |Notification|
   | Handler    | | Handler  | | Handler  | | Handler  | | Handler    |
   +--------+--+ +-----+----+ +---+------+ +-+--------+ +---+--------+
   GenServer    GenServer     GenServer    GenServer     GenServer
   (self-tick   (reacts to    (reacts to   (self-tick   (reacts to
    hourly)      data.*)       data.*)      daily)       score.*)
```

### What We Steal From Each Language

| Source | Concept | What We Take |
|--------|---------|-------------|
| **Elixir GenServer** | Stateful process + message dispatch | Handler base class with `handle()` and self-scheduling |
| **Elixir Supervisor** | Fault isolation + restart counting | try/except per handler, crash counters, auto-disable |
| **Elixir GenStage** | Backpressure | `asyncio.Queue(maxsize=N)` for future streaming mode |
| **Phoenix.PubSub** | Topic-based fan-out | `EventBus` with string topics and wildcard support |
| **Erlang Telemetry** | Lightweight metrics | `telemetry.span()` context manager + `@timed` decorator |
| **Elixir Broadway** | Batch processing | `BatchProcessor` with size/timeout flush |
| **Elixir Registry** | Name-based lookup | `HandlerRegistry` with `@registered` decorator |
| **Elixir Task** | Supervised async + timeout | `SupervisedTask.yield_or_fallback()` for LLM calls |
| **Go select + Ticker** | Multi-rate daemon loop | `MultiRateDaemon` with `sched` module |
| **Rust broadcast** | Multi-consumer events | `BroadcastChannel` for fan-out without backpressure |
| **Clojure add-watch** | Reactive state | `ObservableState` with old/new value watchers |
| **Swift Combine** | Operator pipelines | `EventStream` with `.scan()`, `.debounce()`, `.filter()` |

### The Minimal Viable Architecture

Not everything above needs to be built at once. Priority order:

1. **EventBus with fault isolation** (Phoenix.PubSub + Supervisor) — replaces the
   while-True loop with topic-based event routing and per-handler crash isolation.
   **This is the foundation.**

2. **Handler base class** (GenServer) — each subsystem is a Handler with state and
   a `handle()` method. Self-scheduling via `bus.schedule()`.

3. **ObservableState** (Clojure add-watch) — `day_score`, `active_patterns`,
   `active_experiments` as observable state. Notification logic decoupled from scoring.

4. **Telemetry** (Erlang :telemetry) — `@timed` decorator on collectors and LLM calls.
   Near-zero overhead.

5. **SupervisedTask** (Elixir Task) — for LLM narrative generation with timeout/fallback.

6. **Everything else** — MultiRateDaemon, BroadcastChannel, EventStream operators,
   BatchProcessor, HandlerRegistry. Build when needed.

### Concrete Next Steps

```
src/life_world_model/
  daemon/
    bus.py              # EventBus + Event (from Phoenix.PubSub)
    handler.py          # Handler base class (from GenServer)
    supervisor.py       # SupervisedEventBus (from Supervisor)
    state.py            # ObservableState (from Clojure add-watch)
    telemetry.py        # Telemetry module (from Erlang :telemetry)
    task.py             # SupervisedTask (from Elixir Task)
    collector.py        # Rewrite: CollectorHandler extends Handler
    loop.py             # MultiRateDaemon or event-driven loop
```

The rewritten daemon startup:

```python
def run_daemon(interval_minutes: int = 60) -> None:
    settings = load_settings()
    store = SQLiteStore(settings.database_path)

    # Create the supervised event bus (Supervisor + PubSub)
    bus = SupervisedEventBus()

    # Create observable state (Clojure atoms)
    score_state = ObservableState("day_score", {"total": 0.0})

    # Wire up reactive notifications (add-watch)
    score_state.add_watch("notifier", lambda _key, old, new:
        bus.emit("notification.send", {
            "title": "LWM Score Change",
            "body": f"Score {'up' if new['total'] > old['total'] else 'down'}: "
                    f"{old['total']:.0%} -> {new['total']:.0%}"
        })
        if abs(new["total"] - old["total"]) > 0.05 else None
    )

    # Register handlers (GenServer equivalents)
    bus.register(CollectorHandler(settings, store, interval_sec=interval_minutes * 60))
    bus.register(PatternHandler(store))
    bus.register(ScorerHandler(settings, store, score_state))
    bus.register(ExperimentHandler(store))
    bus.register(NotificationHandler())

    # Attach telemetry logging
    telemetry.attach("log-all", ("lwm",), telemetry.log_handler)

    # Run (blocks until SIGINT/SIGTERM)
    bus.run()
```

---

## Sources

### Elixir/OTP
- [GenServer behaviour (Elixir v1.19.5)](https://hexdocs.pm/elixir/GenServer.html)
- [Elixir GenServer: Concurrent Stateful Process Implementation | Curiosum](https://curiosum.com/blog/what-is-elixir-genserver)
- [Client-server with GenServer](https://hexdocs.pm/elixir/genservers.html)
- [When and Where to use cast, call, info messages | Medium](https://medium.com/blackode/when-and-where-to-use-cast-cal-info-messages-in-elixir-erlang-genserver-9baf937b6494)
- [Supervisor behaviour (Elixir v1.19.5)](https://hexdocs.pm/elixir/Supervisor.html)
- [OTP Supervisors - Elixir School](https://elixirschool.com/en/lessons/advanced/otp_supervisors)
- [How to build a self-healing system using supervision tree in Elixir | Kodius](https://kodius.com/blog/elixir-supervision-tree)
- [GenStage - Elixir School](https://elixirschool.com/en/lessons/data_processing/genstage)
- [GenStage - gen_stage v1.3.2](https://hexdocs.pm/gen_stage/GenStage.html)
- [Announcing GenStage - Elixir](https://elixir-lang.org/blog/2016/07/14/announcing-genstage/)
- [Phoenix.PubSub v2.2.0](https://hexdocs.pm/phoenix_pubsub/Phoenix.PubSub.html)
- [Phoenix PubSub - pompecki.com](https://www.pompecki.com/post/phoenix-pubsub/)
- [Broadway v1.2.1](https://hexdocs.pm/broadway/Broadway.html)
- [Constructing Effective Data Processing Workflows Using Elixir and Broadway](https://softwaremill.com/constructing-effective-data-processing-workflows-using-elixir-and-broadway/)
- [Understanding Elixir's Broadway - Samuel Mullen](https://samuelmullen.com/articles/understanding-elixirs-broadway)
- [Registry (Elixir v1.19.5)](https://hexdocs.pm/elixir/Registry.html)
- [Process registry in Elixir: a practical example](https://www.brianstorti.com/process-registry-in-elixir/)
- [Task (Elixir v1.19.5)](https://hexdocs.pm/elixir/Task.html)
- [Recurring Work with GenServer - ElixirCasts](https://elixircasts.io/recurring-work-with-genserver)
- [telemetry v1.4.1](https://hexdocs.pm/telemetry/telemetry.html)
- [Introducing Telemetry - Erlang Solutions](https://www.erlang-solutions.com/blog/introducing-telemetry/)
- [beam-telemetry/telemetry - GitHub](https://github.com/beam-telemetry/telemetry)

### Erlang OTP
- [Supervisor Behaviour - Erlang System Documentation](https://www.erlang.org/doc/system/sup_princ.html)
- [BEAM OTP: Why Everyone Keeps Reinventing It](https://variantsystems.io/blog/beam-otp-process-concurrency)
- [Building Fault-Tolerant Systems: Inside the OTP Design Principles | Medium](https://medium.com/@matheuscamarques/building-fault-tolerant-systems-inside-the-otp-design-principles-of-erlang-8aed442d4a84)

### Python Libraries
- [fauxtp: Erlang/OTP primitives for Python - GitHub](https://github.com/fizzAI/fauxtp)
- [Pykka: Python actor model](https://github.com/jodal/pykka)
- [Pypubsub: Publish-subscribe for Python](https://pypi.org/project/Pypubsub/)
- [Lahja: Async event bus - GitHub](https://github.com/ethereum/lahja)
- [Python structured concurrency | Applifting Blog](https://applifting.io/blog/python-structured-concurrency)
- [Python 3.11 asyncio.TaskGroup](https://bruceeckel.substack.com/p/python-311-asynciotaskgroup)
- [Manage async I/O backpressure using bounded queues](https://tech-champion.com/programming/python-programming/manage-async-i-o-backpressure-using-bounded-queues-and-timeouts/)
- [AsyncIO at Scale: Backpressure, Structured Concurrency](https://www.kherashanu.com/blogs/2020-asyncio-at-scale-backpressure-structured-concurrency-cancellation)

### Go
- [Go Concurrency Patterns: Pipelines and cancellation - Go Blog](https://go.dev/blog/pipelines)
- [Go Concurrency: Fan-out, Fan-in - pboyd.io](https://pboyd.io/posts/go-concurrency-fan-out-fan-in/)
- [Synchronising Periodic Tasks and Graceful Shutdown with Goroutines | Medium](https://medium.com/the-bug-shots/synchronising-periodic-tasks-and-graceful-shutdown-with-goroutines-and-tickers-golang-9d50f1aaf097)
- [Go advanced concurrency patterns: part 2 (timers)](https://blogtitle.github.io/go-advanced-concurrency-patterns-part-2-timers/)

### Rust
- [Channels | Tokio Tutorial](https://tokio.rs/tokio/tutorial/channels)
- [tokio::sync::broadcast - Rust](https://docs.rs/tokio/latest/tokio/sync/broadcast/index.html)
- [Async Channels in Rust: mpsc, broadcast, watch | Medium](https://medium.com/@adamszpilewicz/async-channels-in-rust-mpsc-broadcast-watch-which-one-fits-your-app-0ceaf566a092)

### Clojure
- [add-watch - clojure.core | ClojureDocs](https://clojuredocs.org/clojure.core/add-watch)
- [Clojure - Atoms](https://clojure.org/reference/atoms)
- [Managing State | Learn ClojureScript](https://www.learn-clojurescript.com/section-4/lesson-22-managing-state/)
- [Clojure Watchers - TutorialsPoint](https://www.tutorialspoint.com/clojure/clojure_watchers.htm)

### Swift
- [Combine: Publishers & Subscribers | Kodeco](https://www.kodeco.com/books/combine-asynchronous-programming-with-swift/v2.0/chapters/2-publishers-subscribers)
- [Combine | Swift by Sundell](https://www.swiftbysundell.com/basics/combine/)
- [Managing self and cancellable references in Combine | Swift by Sundell](https://www.swiftbysundell.com/articles/combine-self-cancellable-memory-management/)
- [PassthroughSubject vs. CurrentValueSubject explained](https://www.avanderlee.com/combine/passthroughsubject-currentvaluesubject-explained/)
- [Understanding the sink Operator in Combine Framework | Medium](https://medium.com/@ramdhas/understanding-the-sink-operator-in-combine-framework-d622bd9fd960)
