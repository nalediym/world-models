# Language Evaluation: Should LWM Be Written in Elixir (or Something Else)?

> Decision document. Written 2026-04-07.
> Evaluates whether to rewrite the Life World Model from Python to another language.

---

## Current State of the Codebase

| Metric | Value |
|--------|-------|
| Source files | 46 Python modules |
| Source lines | ~5,500 |
| Test files | 40 |
| Test lines | ~6,900 |
| Tests passing | 203 |
| Required dependencies | 0 (stdlib only) |
| Optional deps | Gemini SDK, Anthropic SDK, MLX |
| Architecture | CLI + daemon + SQLite + 5 collectors |

The daemon already implements OTP-inspired patterns: EventBus (Phoenix.PubSub), fault-isolated handlers (Supervisor), typed events (GenServer messages), WatchableValue (Clojure atoms), ShutdownSignal (Go context). These work. They're tested. They're ~250 lines of Python.

---

## Scorecard

Each criterion scored 1-10 (10 = best). Weighted final score at bottom.

| Criterion | Weight | Python | Elixir | Go | Rust | Swift | TS/Bun | Clojure |
|-----------|--------|--------|--------|----|------|-------|--------|---------|
| **A. macOS Data Access** | 8% | 9 | 6 | 7 | 7 | **10** | 7 | 5 |
| **B. SQLite Ecosystem** | 10% | **10** | 6 | 8 | 8 | 9 | 8 | 4 |
| **C. LLM Integration** | 7% | **10** | 5 | 8 | 7 | 6 | 9 | 4 |
| **D. Daemon/Background** | 10% | 6 | **10** | 9 | 8 | 8 | 5 | 7 |
| **E. CLI Tooling** | 8% | 9 | 5 | **10** | 9 | 7 | 7 | 6 |
| **F. Web UI Potential** | 8% | 7 | **10** | 8 | 6 | 7 | **10** | 7 |
| **G. Pattern/Statistics** | 10% | **10** | 7 | 5 | 6 | 5 | 6 | 8 |
| **H. Developer Velocity** | 15% | **10** | 5 | 7 | 4 | 6 | 8 | 7 |
| **I. Ecosystem Maturity** | 8% | **10** | 6 | 9 | 7 | 7 | 9 | 6 |
| **J. macOS Native** | 7% | 5 | 3 | 5 | 5 | **10** | 4 | 2 |
| **K. Concurrency Model** | 5% | 4 | **10** | 9 | 9 | 7 | 6 | 8 |
| **L. Single Binary** | 4% | 4 | 5 | **10** | **10** | 8 | 7 | 6 |

### Weighted Totals

| Language | Weighted Score |
|----------|---------------|
| **Python** | **8.13** |
| **Go** | 7.62 |
| **TS/Bun** | 7.16 |
| **Swift** | 7.13 |
| **Rust** | 6.82 |
| **Elixir** | 6.28 |
| **Clojure** | 5.85 |

---

## Per-Language Analysis

### 1. Python (Current) -- Score: 8.13

**Strengths.** Python is the undisputed champion for developer velocity on a solo project. Zero-dep stdlib SQLite (with WAL mode support), first-party Anthropic and Google Gemini SDKs, the richest statistics ecosystem on the planet (scipy, numpy, statistics stdlib), and 800k+ PyPI packages. The existing 5,500 lines of working, tested code represent ~2-3 weeks of focused development that would need to be replicated. LLM-assisted coding tools work best with Python because training data volume is highest. For a solo founder iterating fast, nothing beats Python's prototyping speed -- studies consistently show ~30% faster development cycles compared to compiled languages.

**Weaknesses.** The daemon pattern is the awkward part. Python's concurrency story is genuinely weak: the GIL limits true parallelism, `asyncio` is viral (everything must be async or nothing is), and `threading` requires manual synchronization. The current sched-based daemon works but feels like building a car from Lego -- functional but not what the material was designed for. macOS native integration requires shelling out to `osascript` for notifications (via pync/rumps) rather than using native APIs directly. Single-binary distribution via PyInstaller/Nuitka works but produces large, brittle bundles (100MB+ with hidden extract-on-first-run). No compile-time type checking -- mypy is voluntary and often bypassed.

**Deal-breakers.** None for the current scope. Python's weaknesses are real but manageable for a single-user, single-machine tool. The daemon runs a sched loop with per-handler fault isolation -- it doesn't need true concurrency for hourly collection cycles.

---

### 2. Elixir/Erlang -- Score: 6.28

**Strengths.** OTP is legitimately the best daemon/supervision architecture ever built. The BEAM VM was designed for exactly this: long-running processes, fault tolerance, hot code reloading, message passing. Phoenix LiveView would give LWM a real-time web dashboard with almost no JavaScript -- live-updating scores, patterns refreshing in real-time, all over WebSockets with server-rendered HTML. The concurrency model is unmatched: lightweight processes, supervisors, GenServers are first-class citizens, not bolted-on patterns. The EventBus/WatchableValue/ShutdownSignal patterns you built in Python are literally what Elixir does natively in ~10 lines.

**Weaknesses.** SQLite is a second-class citizen in the Elixir world. Ecto's sqlite3 adapter (v0.22.0) works but the ecosystem assumes Postgres. WAL mode is supported, but you lose async test sandboxing. More critically: Elixir has no direct macOS API access. Reading Chrome's SQLite is fine (file I/O), but there's no EventKit binding, no FSEvents wrapper, no NotificationCenter integration. You'd be shelling out to `osascript` just like Python, but with worse tooling. The Hex ecosystem has ~15,000 packages vs Python's 800,000+. Statistics libraries exist (Explorer + Nx) but are designed for ML pipelines, not the simple means/correlations/time-series that LWM's pattern discovery needs. The learning curve is 3-6 months of reduced productivity for a Python developer transitioning to functional programming paradigms. Burrito can produce single binaries but they extract the entire BEAM runtime on first run.

**Deal-breakers.** The CLI story is genuinely bad. Elixir's startup time is 1-2 seconds (BEAM boot), which makes `lwm patterns --show` feel sluggish compared to Python's ~100ms. Burrito mitigates this somewhat but adds deployment complexity. For a tool you run 20+ times a day from the terminal, this matters. More importantly: you'd be rewriting 5,500 lines of working code AND learning a new language AND losing access to Python's statistics/LLM ecosystem, all to get a better daemon -- which is maybe 15% of the codebase.

---

### 3. Go -- Score: 7.62

**Strengths.** Go is the second-best option and the only serious rewrite candidate. Goroutines + channels are a natural fit for the daemon pattern -- arguably cleaner than Python's sched-based approach, without the conceptual overhead of OTP. Cobra gives you best-in-class CLI tooling with subcommands, completions, and man pages. Single binary distribution is trivial: `go build` produces a static binary, no runtime needed, no extraction. Cross-compilation is a one-liner. Official Anthropic Go SDK shipped March 2026. The fsnotify/fsevents package provides native macOS FSEvents access. modernc.org/sqlite gives you pure-Go SQLite (no CGO) with good performance. Startup time is essentially instant.

**Weaknesses.** Go's type system fights you when doing data processing. No generics until recently, and even now they're limited. Statistical computation would need to be hand-rolled -- there's no scipy equivalent. The language is intentionally spartan: no pattern matching, no sum types, verbose error handling. Developer velocity for a solo project is measurably lower than Python. The web dashboard story is improving (Go + templ + HTMX) but doesn't match Phoenix LiveView's real-time capabilities. LLM SDK support exists but is less mature than Python's.

**Deal-breakers.** For LWM specifically, the pattern discovery module does statistical analysis (correlations, time-series, multi-day comparisons). In Python, this is clean and expressive. In Go, it would be verbose, manual, and harder to iterate on. If you were building a pure daemon/CLI, Go would be the answer. But LWM is a data processing pipeline that also runs as a daemon, and that ordering matters.

---

### 4. Rust -- Score: 6.82

**Strengths.** Tokio provides an excellent async runtime. Rusqlite/SQLx for SQLite are mature. Clap for CLI is arguably the best CLI framework in any language. Single binary, tiny footprint, blazing performance. The genai crate provides multi-provider LLM access. Memory safety without GC means no pause spikes in the daemon. mac-notification-sys exists for macOS notifications.

**Weaknesses.** Developer velocity is the worst of all candidates. Rust's borrow checker is a steep learning curve, and the compile-feedback loop is slow. For a solo developer iterating on a personal tool, fighting lifetimes and trait bounds is the wrong use of time. The statistics ecosystem is immature compared to Python. Prototyping speed is roughly 3-4x slower than Python for this kind of data-centric application. The Anthropic Rust SDK exists but is community-maintained, not official.

**Deal-breakers.** The rewrite would take 2-3x longer than any other language. For a personal tool where correctness matters less than iteration speed, Rust's safety guarantees are solving a problem you don't have. You're not building a web server handling 10k concurrent connections. You're processing ~500 events per day for one person.

---

### 5. Swift -- Score: 7.13

**Strengths.** This is the dark horse. Swift has direct, native access to EVERYTHING LWM needs on macOS: EventKit (Calendar, no SQLite hacking needed), FSEvents, UserNotifications (real notification center, not osascript), HealthKit (if you ever want sleep/activity data), and Core Data/SQLite via GRDB (excellent library, actively maintained through Feb 2026). For a macOS-only tool, Swift eliminates entire categories of hacks. The `swift-argument-parser` provides clean CLI tooling. SwiftAnthropic and AnyLanguageModel provide LLM access. You could build a menu bar app with native SwiftUI that shows your score in real-time -- no web UI needed.

**Weaknesses.** Swift's statistics ecosystem is minimal. StatKit and SigmaSwiftStatistics exist but are hobby projects compared to Python's scipy/pandas. Developer velocity is slower than Python (compiled, type-heavy, Xcode-centric tooling). The package ecosystem (Swift Package Index) is small -- focused on iOS/macOS development, not general-purpose tools. Build times are notoriously slow, frustrating for rapid iteration. Community outside Apple platforms is growing but thin.

**Deal-breakers.** Two things kill Swift for this project. First: it locks you to macOS permanently. Right now that's fine, but if you ever want to run LWM on a Linux server or share it, you'd need a full rewrite. Second: the data analysis / statistics gap is real. LWM's pattern discovery does correlation analysis, time-series decomposition, peak/valley detection, and multi-day behavioral comparisons. In Python, this is 300 lines of clean code using standard statistical functions. In Swift, you'd be implementing basic statistics from scratch or depending on unmaintained packages.

---

### 6. TypeScript/Bun -- Score: 7.16

**Strengths.** If the web UI is the endgame, TS/Bun is compelling. Bun has built-in SQLite (3-6x faster than better-sqlite3), compiles to a 60MB single binary, and the npm ecosystem has packages for everything. Claude Code itself ships as a Bun binary. The path from CLI to web dashboard to Electron/Tauri app is seamless. LLM SDKs (Anthropic, Google) are first-class in TypeScript. The fsevents npm package provides macOS file system watching.

**Weaknesses.** TypeScript for data processing is clunky compared to Python. No scipy/numpy equivalent. The daemon pattern would be setTimeout/setInterval-based, which is less elegant than Python's current sched approach. macOS native integration beyond FSEvents requires native modules (node-gyp pain). Bun is fast-moving but has breaking changes -- API stability is a concern for a long-lived project. The statistics story is weak.

**Deal-breakers.** You'd be trading Python's data processing strengths for JavaScript's web strengths, but LWM is fundamentally a data processing tool that might someday have a web UI, not a web app that processes data. Optimizing for the future UI at the cost of the current core functionality is premature.

---

### 7. Clojure -- Score: 5.85

**Strengths.** Clojure's data-oriented philosophy is a great fit for LWM conceptually. Persistent data structures, REPL-driven development, and the atom/watch pattern that inspired WatchableValue are native. Babashka provides fast-starting scripts. The REPL experience for data exploration is unmatched.

**Weaknesses.** SQLite support in Babashka has been a known pain point for years -- it "hangs, adds 20MB to the binary." The JVM startup time problem is real for CLI tools (2-3 seconds). The package ecosystem is small (~25k Clojars packages). macOS integration is essentially non-existent. Hiring or getting community help is difficult. Babashka has limitations on which libraries it can use.

**Deal-breakers.** The SQLite story alone kills Clojure for this project. LWM's entire data pipeline reads from and writes to SQLite. A language where SQLite is awkward is a non-starter.

---

## The Elixir Question: Deep Analysis

The question that triggered this evaluation: "We just built OTP patterns in Python. Should we just USE Elixir?"

### What OTP Would Actually Give You

1. **Supervision trees**: Automatic restart of crashed handlers. Your Python EventBus does fault isolation (try/except per handler, auto-disable after 10 errors). OTP does this better -- it restarts processes, not just catches exceptions. But your handlers don't crash often enough for this to matter. You're collecting data hourly from local SQLite databases, not handling 10,000 concurrent WebSocket connections.

2. **GenServer state management**: Your WatchableValue is a simplified GenServer. In Elixir, you'd get `handle_cast`, `handle_call`, `handle_info` for free. But WatchableValue is 25 lines of Python and does exactly what you need.

3. **Hot code reloading**: You could update pattern discovery logic without restarting the daemon. Cool in theory. But you restart the daemon maybe once a week, and it takes 2 seconds to boot.

4. **Distributed computing**: OTP lets you run nodes across machines. You have one machine. One user.

### What OTP Would Cost You

1. **3-6 months learning curve** for a Python developer
2. **Complete rewrite** of 5,500 lines of source + 6,900 lines of tests
3. **Loss of Python's statistics ecosystem** (scipy, pandas, statistics stdlib)
4. **Loss of first-party LLM SDKs** (Anthropic, Google Gemini have Python-first SDKs)
5. **Slower CLI startup** (BEAM boot: ~1-2s vs Python: ~100ms)
6. **Worse macOS integration** (no native APIs, same osascript shelling as Python)
7. **Smaller community** for debugging weird issues (~15k Hex packages vs 800k PyPI)

### The Honest Assessment

OTP is designed for telecom switches handling millions of concurrent calls with five-nines uptime. LWM is a personal behavior tracker running on one MacBook, collecting data hourly, for one person. The supervision/fault-tolerance/distribution features that make OTP legendary are solving problems LWM does not have and will never have.

The one genuinely compelling Elixir feature is Phoenix LiveView for the web dashboard. But that's a future feature, not a current need, and you can get 80% of that with Python + HTMX or even Go + templ.

**Verdict on Elixir: No.** The OTP patterns you implemented in Python are good enough. They're tested, they work, and they cost 250 lines. Rewriting to Elixir would burn 2-3 months for marginal architectural improvement in the daemon layer while degrading everything else (data processing, CLI, LLM integration, macOS access, dev velocity).

---

## The Swift Question: Deep Analysis

Swift deserves special attention because LWM is a macOS-only tool, and Swift is macOS's native language.

### What Swift Would Give You

1. **Direct EventKit access**: Read Calendar events through Apple's official API instead of hacking into Calendar's locked SQLite database. Proper permission dialogs. Real-time calendar change notifications.
2. **Native UserNotifications**: Rich notifications with actions, images, sounds -- not osascript hacks.
3. **FSEvents**: Direct kernel-level file system monitoring, not a Python wrapper.
4. **Menu bar app**: SwiftUI gives you a native menu bar widget showing your daily score. No web server, no Electron, no hacks.
5. **HealthKit**: Sleep data, activity data, heart rate -- a goldmine for a behavior engine.
6. **Single binary**: `swift build -c release` produces a native binary. No runtime, no extraction.

### What Swift Would Cost You

1. **Statistics gap**: No scipy equivalent. You'd hand-roll correlation, time-series analysis, peak detection.
2. **LLM SDK gap**: SwiftAnthropic exists but is community-maintained. Less mature than Python SDKs.
3. **Platform lock**: macOS only. Forever.
4. **Slower iteration**: Compiled language, slower build times, less forgiving for rapid prototyping.
5. **Complete rewrite**: Same 5,500 + 6,900 line cost as Elixir.
6. **Smaller community**: Fewer StackOverflow answers for CLI/daemon patterns in Swift.

### The Honest Assessment

Swift's macOS native access is genuinely compelling. The Calendar collector currently copies a locked SQLite database to temp, queries it with raw SQL, and converts Mac epoch timestamps. In Swift, it would be `EKEventStore().events(matching:)` -- five lines replacing 100. The notification system would go from shelling out to `osascript` to using `UNUserNotificationCenter` natively.

But the statistics gap is real and unfixable. LWM's pattern discovery is the core differentiator, and it needs correlation analysis, time-series decomposition, and multi-day behavioral comparisons. In Python, this is clean and well-supported. In Swift, you'd be writing numerical code from scratch.

**Verdict on Swift: Not for a rewrite, but consider for a companion app.** A lightweight Swift menu bar agent that displays the daily score, shows notifications, and provides quick actions would be a natural complement to the Python backend. The heavy lifting (collection, analysis, pattern discovery, scoring) stays in Python where the ecosystem supports it. The thin macOS-native presentation layer goes in Swift where it belongs.

---

## Verdict: Stay in Python

**Python wins, and it's not close for this project.**

The weighted scorecard shows Python at 8.13 vs the nearest competitor (Go) at 7.62. But the scorecard understates Python's advantage because it doesn't capture the rewrite tax: 5,500 lines of source code, 6,900 lines of tests, 203 passing tests, and 2-3 weeks of development time that would need to be replicated in any other language.

### The Reasoning

1. **LWM is fundamentally a data processing pipeline.** It reads events, buckets them, computes statistics, discovers patterns, scores days. Python's data ecosystem (even without pandas/numpy, just stdlib statistics + custom code) is the strongest of any language for this workload.

2. **The daemon is 15% of the codebase.** You don't rewrite the other 85% to optimize the 15%. The Python daemon works. It's tested. The OTP-inspired patterns are good enough for hourly collection on a single machine.

3. **LLM integration is Python-first.** Anthropic and Google both ship Python SDKs first, with the richest features. Go and TypeScript are close seconds. Everything else is community-maintained.

4. **Developer velocity matters most for a solo project.** You need to ship features, not fight compilers. Python's ~30% productivity advantage over compiled languages compounds over months of development.

5. **The rewrite tax is real.** 2-3 weeks minimum to reach feature parity in Go, 4-6 weeks in Rust, 6-8 weeks in Elixir (including learning curve). That's 6-8 weeks of zero new features. For a personal tool, this is death.

6. **Zero dependencies is a superpower.** The current Python codebase requires nothing beyond the stdlib. This is rare and valuable. Most other languages would require pulling in packages for SQLite, CLI parsing, or basic data structures.

---

## If Not Python, Then What? Migration Strategy

Even though the verdict is to stay in Python, here's the plan if Python becomes a bottleneck:

### Phase 1: Harden Python (Now)

- Add mypy strict mode for type safety
- Add `py.typed` marker for downstream use
- Consider `uvloop` if the daemon needs better async performance
- Use `watchdog` library for FSEvents (already a Python package)

### Phase 2: Swift Menu Bar Companion (When Web UI Is Needed)

Instead of a web dashboard, build a native macOS menu bar app in Swift that:
- Reads the SQLite database directly (GRDB)
- Shows daily score in the menu bar
- Sends native UserNotifications
- Provides quick actions (start experiment, view patterns)
- Communicates with the Python daemon via the SQLite database (shared state)

This gives you native macOS integration without rewriting the engine.

### Phase 3: Performance-Critical Paths in Rust (If Needed)

If pattern discovery or scoring becomes slow with months of data:
- Write Rust extensions via PyO3 for hot paths
- ~30% of new PyPI native extensions already use Rust
- Keep Python as the orchestrator, use Rust for computation

### Phase 4: Go for Distribution (If Sharing)

If LWM needs to be distributed to other users:
- Rewrite the CLI/daemon layer in Go for single-binary distribution
- Keep the analysis engine as a Python subprocess or rewrite it
- Go + SQLite + Cobra gives you the best distribution story

---

## The One-Sentence Answer

**Stay in Python.** The daemon patterns you borrowed from Elixir work fine in Python, and rewriting would sacrifice your strongest assets (data processing, LLM integration, dev velocity, zero deps) to marginally improve your least important weakness (daemon architecture elegance).

---

## Sources

### Elixir
- [ecto_sqlite3 - Ecto SQLite3 Adapter](https://github.com/elixir-sqlite/ecto_sqlite3)
- [Elixir Desktop - Native macOS/iOS/Android Apps](https://github.com/elixir-desktop/desktop)
- [Burrito - Single Binary Elixir Apps](https://github.com/burrito-elixir/burrito)
- [Elixir Learning Curve Forum Discussion](https://elixirforum.com/t/learning-curve-expectations-how-long-does-it-typically-take-to-become-proficient-in-elixir/53512)
- [State of Elixir 2025 Survey](https://elixir-hub.com/surveys/2025)
- [Elixir vs Python for Data Science - DockYard](https://dockyard.com/blog/2022/07/12/elixir-versus-python-for-data-science)
- [Explorer - DataFrames for Elixir](https://github.com/elixir-explorer/explorer)
- [Phoenix LiveView](https://github.com/phoenixframework/phoenix_live_view)

### Swift
- [GRDB.swift - SQLite Toolkit](https://github.com/groue/GRDB.swift)
- [EventKit - Apple Developer](https://developer.apple.com/documentation/eventkit)
- [SwiftAnthropic - Claude SDK for Swift](https://github.com/jamesrochabrun/SwiftAnthropic)
- [AnyLanguageModel - Unified LLM API](https://www.infoq.com/news/2025/11/anylanguagemodel/)
- [StatKit - Statistics for Swift](https://github.com/JimmyMAndersson/StatKit)
- [swift-argument-parser - CLI Framework](https://github.com/apple/swift-argument-parser)
- [State of Swift 2026](https://devnewsletter.com/p/state-of-swift-2026/)
- [Swift on the Server Ecosystem](https://www.swift.org/blog/swift-on-the-server-ecosystem/)

### Go
- [Anthropic Go SDK (Official)](https://github.com/anthropics/anthropic-sdk-go)
- [Cobra - CLI Framework](https://github.com/spf13/cobra)
- [fsevents for Go](https://github.com/fsnotify/fsevents)
- [modernc SQLite - Pure Go](https://pkg.go.dev/modernc.org/sqlite)
- [Go + templ + HTMX Dashboards](https://medium.com/@iamsiddharths/building-reactive-uis-with-go-templ-and-htmx-a-simpler-path-beyond-spas-17e7dad2c7a2)
- [Go Ecosystem 2025 - JetBrains](https://blog.jetbrains.com/go/2025/11/10/go-language-trends-ecosystem-2025/)
- [macOS LaunchAgents in Go](https://ieftimov.com/posts/create-manage-macos-launchd-agents-golang/)

### Rust
- [genai - Multi-Provider LLM Crate](https://github.com/jeremychone/rust-genai)
- [tokio-rusqlite](https://crates.io/crates/tokio-rusqlite)
- [mac-notification-sys](https://crates.io/crates/mac-notification-sys)
- [State of Rust 2025 Survey](https://blog.rust-lang.org/2026/03/02/2025-State-Of-Rust-Survey-results/)
- [Rust Crate Ecosystem Stats](https://lib.rs/stats)

### TypeScript/Bun
- [Bun SQLite - Built-in Driver](https://bun.com/docs/runtime/sqlite)
- [Bun 1.2 Deep Dive](https://dev.to/pockit_tools/bun-12-deep-dive-built-in-sqlite-s3-and-why-it-might-actually-replace-nodejs-4738)
- [fsevents npm Package](https://www.npmjs.com/package/fsevents)
- [Tigris CLI - Bun Single Binary](https://www.tigrisdata.com/blog/using-bun-and-benchmark/)

### Clojure
- [Babashka - Native Clojure Scripting](https://github.com/babashka/babashka)
- [State of Clojure 2025 Results](https://clojure.org/news/2026/02/18/state-of-clojure-2025)

### Python (Staying the Course)
- [watchdog - FSEvents for Python](https://github.com/gorakhargosh/watchdog)
- [rumps - macOS Menu Bar Apps](https://github.com/jaredks/rumps)
- [pync - macOS Notifications](https://pypi.org/project/pync/)
- [PyInstaller vs Nuitka Comparison](https://sparxeng.com/blog/software/python-standalone-executable-generators-pyinstaller-nuitka-cx-freeze)
- [Python Trends 2025](https://www.netguru.com/blog/future-of-python)
- [PyPI - 800k+ Packages](https://pypi.org/)
