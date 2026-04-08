"""EventBus with fault isolation + WatchableValue for reactive state.

EventBus: type-dispatched pub/sub (inspired by Elixir Phoenix.PubSub).
  - Handlers subscribe by event type (dataclass), not string keys.
  - Each handler is try/except isolated (Elixir Supervisor pattern).
  - One handler crash doesn't kill the rest.

WatchableValue: reactive state with watchers (inspired by Clojure atoms + add-watch).
  - Set a value, watchers fire automatically with (old, new).
  - Decouples state producers from consumers.
"""

from __future__ import annotations

import signal
import threading
from collections import defaultdict
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class EventBus:
    """Type-dispatched event bus with per-handler fault isolation."""

    def __init__(self) -> None:
        self._handlers: dict[type, list[Callable]] = defaultdict(list)
        self._error_counts: dict[str, int] = defaultdict(int)
        self._max_errors = 10  # auto-disable handler after this many crashes

    def on(self, event_type: type, handler: Callable, name: str | None = None) -> None:
        """Subscribe a handler to an event type."""
        if name is not None:
            handler._bus_name = name  # type: ignore[attr-defined]
        self._handlers[event_type].append(handler)

    def emit(self, event: Any) -> None:
        """Emit an event. All subscribed handlers are called with fault isolation."""
        for handler in self._handlers.get(type(event), []):
            handler_name = getattr(handler, "_bus_name", handler.__qualname__)
            if self._error_counts[handler_name] >= self._max_errors:
                continue  # auto-disabled after too many crashes
            try:
                handler(event)
            except Exception as e:
                self._error_counts[handler_name] += 1
                count = self._error_counts[handler_name]
                print(
                    f"[bus] Handler {handler_name} failed on "
                    f"{type(event).__name__}: {e} ({count}/{self._max_errors})"
                )
                if count >= self._max_errors:
                    print(f"[bus] Handler {handler_name} auto-disabled after {count} errors")

    @property
    def handler_errors(self) -> dict[str, int]:
        return dict(self._error_counts)


class WatchableValue(Generic[T]):
    """Reactive state container inspired by Clojure atoms + add-watch.

    Watchers are called with (old_value, new_value) whenever the value changes.
    """

    def __init__(self, initial: T) -> None:
        self._value = initial
        self._watchers: list[Callable[[T, T], None]] = []

    @property
    def value(self) -> T:
        return self._value

    def set(self, new: T) -> None:
        old = self._value
        self._value = new
        for watcher in self._watchers:
            try:
                watcher(old, new)
            except Exception as e:
                print(f"[watch] Watcher error: {e}")

    def watch(self, fn: Callable[[T, T], None]) -> None:
        """Register a watcher. Called with (old, new) on every set()."""
        self._watchers.append(fn)


class ShutdownSignal:
    """Cooperative shutdown signal inspired by Go context / Rust CancellationToken.

    Call .request() to signal shutdown. Check .is_set or wait with .wait().
    Automatically hooks SIGINT/SIGTERM.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def request(self) -> None:
        self._event.set()

    @property
    def is_set(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float | None = None) -> bool:
        """Block until shutdown is requested. Returns True if shutdown was signaled."""
        return self._event.wait(timeout=timeout)

    def install_signal_handlers(self) -> None:
        """Hook SIGINT and SIGTERM to trigger shutdown."""
        def _handler(signum: int, frame: Any) -> None:
            print(f"\n[daemon] Received signal {signum}, shutting down...")
            self.request()

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
