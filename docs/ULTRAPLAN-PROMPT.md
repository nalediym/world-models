# Ultraplan Prompt: Life World Model — Final Confirmation Interview

> Paste everything below the line into an ultraplan session. It will interview you, confirm the plan, and prepare for implementation.

---

## Context

You are planning the next major evolution of a personal Life World Model project. The project lives at `/Users/naledi/Projects/world-models`. Two comprehensive documents have been prepared:

1. **Full Planning Brief** — read this FIRST:
   `/Users/naledi/Projects/world-models/docs/ULTRAPLAN-BRIEF.md`
   (~700 lines — contains the complete user interview transcript, existing codebase analysis, data source discovery, TikTok analysis, and the full 6-phase implementation plan with code snippets)

2. **TikTok Recommendation System Deep Dive** — read this SECOND:
   `/Users/naledi/Projects/world-models/docs/research/TIKTOK-RECOMMENDATION-SYSTEM-DEEP-DIVE.md`
   (~1,070 lines — exhaustive research on TikTok's Monolith architecture, signal collection, the leaked Algo 101 formula, pipeline architecture, and lessons for personal behavior modeling with 35 cited sources)

3. **Existing Implementation Plan** — read this THIRD:
   `/Users/naledi/.claude/plans/glistening-soaring-stearns.md`
   (The detailed 6-phase plan file with file paths, function signatures, and verification steps)

## Your Task

Read all three documents thoroughly. Then conduct a structured confirmation interview with me to validate the plan before we build. Use plan mode to track your findings.

### Phase 1: Read & Synthesize

Read all three documents. Identify:
- What the plan proposes (6 phases from multi-source collection to suggestions)
- What the TikTok research reveals (the tight feedback loop matters more than model sophistication, implicit signals beat explicit ones, the Algo 101 scoring formula pattern)
- Where the plan already incorporates TikTok learnings (signal extraction, sequence modeling)
- Where gaps remain (real-time updating, proactive experiments, multi-objective optimization, user goals)

### Phase 2: Interview Me

Ask me the following questions in structured rounds. These are the open questions from the planning session that still need answers. DO NOT skip any — each one affects the implementation.

**Round 1 — Priority & Scope:**

1. Should we close the three biggest TikTok gaps NOW (user goals system, proactive experiment tracking, continuous learning daemon) or build Phases 1-5 first and layer those on after? The TikTok research says the tight feedback loop is more important than model sophistication — does that change your priority?

2. Within Phase 1 (multi-source collection), should we build all 5 collectors at once, or ship knowledgeC first (it's the highest-value single source — 4 weeks of app-level usage data) and iterate with shell history, git, and calendar after?

3. The TikTok research revealed they dedicate ~50% of recommendations to exploration (testing hypotheses about the user). Should our suggestion engine be proactive from the start ("I notice you've never coded before 9am — want to try it for 3 days and I'll measure?") or passive ("here are suggestions, pick one")?

**Round 2 — The Scoring Formula:**

4. TikTok's core formula is: `Score = Plike x Vlike + Pcomment x Vcomment + Eplaytime x Vplaytime + Pplay x Vplay`. For your personal world model, what would your version look like? The TikTok research suggests something like:
   ```
   Score = P_productive x V_productive + P_energizing x V_energizing + E_focus_time x V_focus + P_aligned_with_goals x V_goals
   ```
   What V (value) weights matter most to YOU? What are you optimizing your day for — deep work hours? Energy? Creative output? Balance? Something else?

5. The research found that TikTok uses temporal decay: `weight = e^(-lambda * (t_current - t_i))` — recent behavior matters more than old behavior. How fast should YOUR patterns decay? Should a habit from 2 weeks ago carry the same weight as one from yesterday?

**Round 3 — User Experience:**

6. Narrative style: The MVP uses Tolkien-esque prose. For the new pattern/suggestion/simulation features, should we: (a) keep Tolkien for everything, (b) switch to plain English for analysis and keep Tolkien for day narratives only, or (c) make it configurable per command?

7. How detailed should suggestions be? Quick one-liners ("limit browsing to 1hr") or full evidence reports with your specific numbers ("you spend 2.3 hrs/day in Safari with 12 context switches per session — limiting to 1hr would free 1.3hrs based on your pattern from the last 3 weeks")?

8. Should the system notify you proactively (macOS notification: "you've been in Safari for 45 minutes with 8 context switches — your pattern says this leads to a 45-min recovery period") or only respond when you ask?

**Round 4 — Technical Decisions:**

9. The TikTok research emphasizes that model update speed matters more than model sophistication. Our current plan is batch-only (run `lwm patterns` manually). Should we add a lightweight daemon mode from the start that collects and re-analyzes on a schedule (e.g., every hour), or is manual triggering fine for v1?

10. For the simulation engine, the plan uses mechanical schedule manipulation + LLM narration. The TikTok research suggests using a scoring formula instead: score each simulated day against your personal objectives. Should we add formula-based scoring to simulations (not just narrative comparison)?

**Round 5 — Personal Goals:**

11. What habits do you MOST want to change? Be specific. (e.g., "I spend too much time browsing after 9pm", "I can't get into deep work before noon", "I context-switch too much between Slack and coding"). This directly affects which patterns we surface first and which suggestions we prioritize.

12. What does your IDEAL day look like? If you could design your perfect weekday schedule, what would it be? This could serve as the north star that the suggestion engine optimizes toward.

13. What's your biggest suspected time sink right now? If you already have a hunch, the first thing the system should do is confirm or deny it with data.

### Phase 3: Update the Plan

Based on my answers, update the implementation plan at `/Users/naledi/.claude/plans/glistening-soaring-stearns.md` to:

1. Incorporate any scope changes (adding/removing phases, reordering priorities)
2. Add the TikTok-inspired scoring formula if I want it
3. Add user goals system if I want it early
4. Add daemon mode if I want it early
5. Add proactive suggestions if I want them
6. Refine the suggestion engine to target my specific habits/goals
7. Update the verification section to include checking patterns against my stated goals

### Phase 4: Confirm Readiness

After updating the plan, summarize:
- What we're building (scope)
- What order we're building it in (phases)
- What TikTok principles we're incorporating (and which we're deliberately skipping)
- What the first command I'll be able to run is
- What tests will prove it works

Then ask me: "Ready to build?"
