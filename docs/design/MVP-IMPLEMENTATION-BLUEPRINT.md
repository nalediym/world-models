# Personal Life World Model: MVP Implementation Blueprint

> A text-based world model that predicts your daily life in Tolkien-esque narrative prose, trained on literary world-building (The Hobbit) and personalized with your real digital footprint.

**Date**: March 21, 2026 (Full Day Rollout: 00:00 - 23:59)

**Update**: March 21, 2026 - Incorporating latest research insights from Genie 3 (DeepMind), Dreamer 4, World Labs, and VERSES AI

---

## Research Context

This blueprint synthesizes insights from the cutting edge of world model research (March 2026):

- **Genie 3** (DeepMind): First real-time interactive world model at 20-24 FPS, with memory recalling interactions for up to a minute
- **Dreamer 4**: Training agents inside world models without environment interaction; achieves complex goals purely from offline data
- **World Labs**: Spatial intelligence as the next frontier — 3D world understanding
- **VERSES AI**: Active inference paradigm — learning in real-time without massive pre-training

**Key Insight Applied**: While most world models use video (pixels), this MVP uses **text as the representation medium** — following the UI-Simulator approach but applied to personal life narrative generation.

---

## Research-to-Implementation Mapping

**Each decision in this blueprint is grounded in specific research. Here's how:**

| Research Source | Key Finding | How We Apply It |
|----------------|-------------|-----------------|
| **DreamDojo** (NVIDIA) | "44,000 hours of diverse human egocentric videos" — "pre-training with latent actions on large-scale human datasets to acquire comprehensive physical knowledge" | We use **The Hobbit** as our "44,000 hours" of narrative data for pre-training the literary style |
| **DreamZero** (NVIDIA) | "Adapts to YAM robot with only **30 minutes of play data**" — "knowledge gained from AgiBot pretraining transfers directly" | After training on The Hobbit, we adapt to your life with only **7-14 days of personal data** |
| **1X World Model** | "70 hours of robot data to adapt to NEO's visual appearance" — "World Model Backbone: 14B generative video model" | Our "backbone" is GPT-4/Claude API (the "14B model" equivalent for text) + fine-tuning on your activity patterns |
| **Rhoda AI DVA** | "Data-efficient task learning with as little as **~10 hours** of robot data" — "Web video is the most scalable data source" | We use web-scale text (The Hobbit) as our scalable source, then adapt efficiently with minimal personal data |
| **UI-Simulator** | "Digital world model built on LLMs that: Generates structured accessibility trees with textual content, spatial coordinates, dynamic attributes" | **This is our core approach**: Text-based world model (not video), using LLMs to predict textual "next states" |
| **Seoul World Model** | "Retrieval-augmented generation with street-view database" — "Virtual Lookahead Sink: Continuously re-grounds generation over hundreds of meters" | Our **Memory Manager** is the equivalent: retrieves established facts to re-ground narrative consistency over 24 hours |
| **Genie 3** (DeepMind) | "Memory recalling changes from specific interactions for up to a minute" — "World consistency and stability: Previously seen details are recalled when revisited" | **Three-tier memory system**: short-term (3-5 frames), medium-term (period summaries), long-term (established facts) |
| **Dreamer 4** | "Training agents inside of world models without environment interaction" — "First agent to obtain diamonds in Minecraft purely from offline data" | We train on The Hobbit **offline first** (no personal data needed), then adapt to your life |
| **World Labs** | "3D is becoming the universal interface for space" — "Spatial intelligence is AI's next frontier" | We treat **time** as our spatial dimension: midnight → midnight timeline as the "space" to navigate |
| **VERSES AI** | "Genius: SENSE/THINK/ACT/SHARE — learning in real-time without extensive pre-training" | **Future v2.0**: Add Bayesian layer for real-time adaptation without pre-training (alternative to deep learning approach) |
| **Stable-WorldModel-v1** (LeCun & Balestriero) | "World Models have emerged as a powerful paradigm for learning compact, predictive representations of environment dynamics, enabling agents to reason, plan, and generalize beyond direct experience" | This is our **core definition**: Text-based predictive representation enabling you to "reason, plan, and generalize" about your future |

**Every design decision in this blueprint traces back to these research findings.**

---

## Executive Summary

This document provides the complete technical blueprint for building a personal life world model MVP. The system ingests your digital life data (Chrome history, file system activity, project work) and generates autoregressive narrative rollouts—predicting your entire day from midnight to midnight in the style of rich fantasy literature.

**Key Innovation**: Unlike visual world models that predict video frames, this predicts **narrative states**—describing what you're doing, where you are, and what might happen next, all in literary prose.

---

## Table of Contents

1. [Core Architecture](#core-architecture)
2. [Data Sources & Collection](#data-sources--collection)
3. [State Representation](#state-representation)
4. [Consistency & Memory Management](#consistency--memory-management)
5. [Narrative Generation Pipeline](#narrative-generation-pipeline)
6. [Full-Day Rollout System](#full-day-rollout-system)
7. [Training Approach: Two Paradigms](#training-approach-two-paradigms)
8. [Movie Comparison: Everything Everywhere All At Once](#movie-comparison-everything-everywhere-all-at-once)
9. [Implementation Phases](#implementation-phases)
10. [Implementation Details for Claude](#implementation-details-for-claude)
    - [Code Organization](#code-organization)
    - [Error Handling Strategy](#error-handling-strategy)
    - [Database Schema](#database-schema-sqlite)
    - [Edge Cases & Handling](#edge-cases--handling)
    - [Configuration System](#configuration-system)
    - [Prompt Templates](#prompt-templates-exact)
    - [CLI Interface](#cli-interface-specification)
    - [Testing Strategy](#testing-strategy)
    - [File Naming Conventions](#file-naming-conventions)
11. [Technical Specifications](#technical-specifications)
12. [Safety & Privacy Considerations](#safety--privacy-considerations)
13. [Appendix: Two Paradigms in Practice](#appendix-two-paradigms-in-practice)
14. [Future Extensions](#future-extensions-post-mvp)

---

## Core Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT LAYER: Real-Time Data Collection                      │
│  - Chrome history (every 15 min)                             │
│  - File system activity (file opens, saves)                  │
│  - Project context (active directory, git commits)           │
│  - System events (wake/sleep, app switches)                  │
└──────────────────────┬────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  STATE ENCODER: Structured Representation                     │
│  - Current timestamp                                          │
│  - Location context (from Chrome history patterns)          │
│  - Activity type (coding, browsing, communication)          │
│  - Project context (which repo/directory)                   │
│  - Recent narrative history (last 3-5 states)                 │
└──────────────────────┬────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  WORLD MODEL CORE: GPT-4/Claude API (Few-Shot Prompted)       │
│  - Pre-trained on The Hobbit (literary style)               │
│  - Conditioned on personal data patterns                    │
│  - Generates next narrative "frame" (2-3 sentences)         │
└──────────────────────┬────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  ROLLOUT GENERATOR: Autoregressive Chain                    │
│  - Takes generated frame → feeds back as input              │
│  - Repeats for full 24-hour prediction                      │
│  - Outputs complete narrative timeline                      │
└─────────────────────────────────────────────────────────────┘
```

### Key Differences from Visual World Models (Why Text Works)

**From Stable-WorldModel-v1 (LeCun & Balestriero)**:
> "World Models have emerged as a powerful paradigm for learning compact, predictive representations of environment dynamics, enabling agents to reason, plan, and generalize beyond direct experience."

**Key word**: "representations" — not "visual representations." World models predict state transitions. The representation (video vs text vs structured data) is an implementation detail.

**From UI-Simulator**:
> "Digital world model built on LLMs that: Simulates UI environment dynamics... Generates structured accessibility trees with textual content, spatial coordinates, dynamic attributes"

**This is the precedent**: UI-Simulator proved that **text-based world models work** for digital agents. We're applying the same principle to **personal life narrative**.

**Why Video is Chosen for Robots (Not Because It's Required)**:

From **Rhoda AI**:
> "Web video is the most scalable data source capturing the dynamic physical world, and video generation is the most effective objective for a model to learn the deep physical knowledge robots need for decision-making"

**Video is chosen because it's the most SCALABLE data source, not because it's the only valid representation.**

From **1X World Model**:
> "Internet video implicitly encodes the structural priors of reality"

**For your project**: The Hobbit implicitly encodes the structural priors of **narrative** — pacing, world-building, character development.

**Comparison Table**:

| Aspect | Visual World Models (Robots) | Text World Model (Your Life) |
|--------|------------------------------|------------------------------|
| **Pre-training Data** | 44,000 hours video (DreamDojo) | The Hobbit (literary text) |
| **Representation** | Video frames (pixels) | Narrative frames (text) |
| **Adaptation Data** | 30 min - 70 hours (DreamZero, 1X) | 7-14 days personal activity |
| **Core Mechanism** | Predict next video frame | Predict next narrative sentence |
| **Output** | 720p @ 20-24 FPS (Genie 3) | Text @ 2 FPS (much faster!) |
| **Use Case** | Robot control, physics simulation | Life prediction, planning, reflection |

**Research-Backed Conclusion**: Video works for robots because they need visual-motor control. **Text works for life narrative** because you're building a literary experience, not a physics simulator.

From the research:

> "World Models have emerged as a powerful paradigm for learning compact, predictive representations of environment dynamics, enabling agents to reason, plan, and generalize beyond direct experience." — *Stable-WorldModel-v1*

**Traditional Approach** (DreamDojo, 1X, DreamZero):
- Predicts **video frames** (pixels)
- Uses 44,000 hours of video data
- Generates 10 FPS video rollouts

**Our Approach** (Text-Based):
- Predicts **narrative states** (text)
- Uses The Hobbit + your digital logs
- Generates prose "frames" describing activities

> "Digital world model built on LLMs that: Simulates UI environment dynamics... Generates structured accessibility trees with textual content, spatial coordinates, dynamic attributes" — *UI-Simulator*

**We're applying the UI-Simulator approach to LIFE instead of UI.**

---

## Data Sources & Collection

### Data Schema

#### 1. Chrome History Stream
```json
{
  "timestamp": "2026-03-21T09:15:00Z",
  "url": "https://github.com/...",
  "title": "world-models-landscape.md",
  "domain": "github.com",
  "visit_duration_seconds": 420,
  "transition_type": "link|typed|reload",
  "previous_url": "https://google.com/search?q=..."
}
```

#### 2. File System Activity
```json
{
  "timestamp": "2026-03-21T09:18:00Z",
  "event_type": "file_open|file_save|directory_change",
  "file_path": "/Users/naledi/Projects/world-models/...",
  "project_name": "world-models",
  "file_extension": ".md|.py|.js",
  "lines_changed": 45
}
```

#### 3. System Context
```json
{
  "timestamp": "2026-03-21T09:00:00Z",
  "event_type": "wake|sleep|lock|unlock|app_switch",
  "active_app": "Cursor|Chrome|Terminal|Messages",
  "screen_locked": false,
  "idle_time_seconds": 0
}
```

#### 4. Git Activity (if in repo)
```json
{
  "timestamp": "2026-03-21T10:30:00Z",
  "repo": "world-models",
  "branch": "main",
  "commit_hash": "abc123...",
  "commit_message": "Add DreamDojo citations",
  "files_changed": ["world-models-landscape.md"],
  "lines_added": 50,
  "lines_deleted": 10
}
```

### Data Collection Implementation

```python
# Data Collector Agent (runs continuously in background)
class LifeDataCollector:
    """
    Collects digital life data every 15 minutes
    Stores in local SQLite database
    """
    
    def collect_chrome_history(self, since: datetime) -> List[ChromeEvent]:
        # Reads from Chrome's History SQLite database
        # Path: ~/Library/Application Support/Google/Chrome/Default/History
        pass
    
    def collect_file_system_activity(self, since: datetime) -> List[FSEvent]:
        # Uses fseventsd or similar system hooks
        # Tracks file opens, saves, directory navigation
        pass
    
    def collect_system_context(self) -> SystemEvent:
        # Uses macOS APIs to detect wake/sleep/app switches
        pass
    
    def collect_git_activity(self, root_dirs: List[str]) -> List[GitEvent]:
        # Scans project directories for recent commits
        pass
```

---

## State Representation

### The "Life State" Object

```typescript
interface LifeState {
  // Temporal
  timestamp: ISOString;
  timeOfDay: "dawn" | "morning" | "midday" | "afternoon" | "evening" | "night";
  dayOfWeek: "Saturday";
  
  // Activity Context
  currentActivity: {
    primary: "coding" | "research" | "communication" | "browsing" | "break";
    secondary?: string; // e.g., "world-models project", "AI research"
  };
  
  // Location (inferred)
  digitalLocation: {
    domain?: string;      // e.g., "github.com"
    project?: string;     // e.g., "world-models"
    app?: string;         // e.g., "Cursor"
  };
  
  // Recent History (last 3 states)
  narrativeHistory: string[]; // Last 3 generated narrative frames
  
  // Physical Context (optional, if available)
  physicalContext?: {
    location?: "home_office" | "cafe" | "commute";
    noiseLevel?: "quiet" | "moderate" | "loud";
  };
}
```

### Example State (9:15 AM, March 21)

```json
{
  "timestamp": "2026-03-21T09:15:00-07:00",
  "timeOfDay": "morning",
  "dayOfWeek": "Saturday",
  "currentActivity": {
    "primary": "research",
    "secondary": "world-models documentation"
  },
  "digitalLocation": {
    "domain": "github.com",
    "project": "world-models",
    "app": "Chrome"
  },
  "narrativeHistory": [
    "The scribe stirred from slumber as the first grey light crept through the curtains, reaching instinctively for the glowing rectangle that held the day's first mysteries.",
    "With morning coffee steaming beside the glowing screen, the researcher delved into scrolls of ancient AI wisdom, seeking patterns in the world models of distant laboratories.",
    "The browser window flickered with new knowledge—NVIDIA's DreamDojo, a generalist robot world model trained upon 44,000 hours of human endeavor."
  ]
}
```

---

## Consistency & Memory Management

**Insight from Genie 3 (DeepMind)**:
> "The environments remain largely consistent for several minutes, with memory recalling changes from specific interactions for up to a minute."

For a **full-day text-based world model**, maintaining narrative coherence over 24 hours is critical. Without memory management, the story could contradict itself or lose track of established facts.

### The Challenge

One of the main challenges of generating AI worlds is keeping them consistent over time. This is harder than generating an entire video, as inaccuracies tend to increase the longer the world is actively generated. — *Genie 3 research*

**For text narratives**: If at 9am you "started researching world models," at 3pm you shouldn't be "starting your day" or "just waking up." The model must remember the day's accumulated context.

### Memory Architecture

```typescript
interface NarrativeMemory {
  // Short-term: Last few states (immediate context)
  shortTerm: {
    frames: string[];        // Last 3-5 narrative frames
    activities: string[];    // Recent activities for continuity
  };
  
  // Medium-term: Morning/afternoon/evening summaries
  mediumTerm: {
    morningSummary?: string;    // Generated at noon
    afternoonSummary?: string;   // Generated at 6pm
    keyEvents: string[];         // Important events (meals, meetings, milestones)
  };
  
  // Long-term: Day theme & established facts
  longTerm: {
    dayTheme: string;            // e.g., "A day of deep research"
    establishedFacts: Map<string, string>;  // Immutable facts about the day
    // e.g., "breakfast" -> "oatmeal and coffee", "location" -> "home office"
  };
}
```

### Memory Update Strategy

**From VERSES AI (Active Inference)**:
> "Every signal—color, shape, position—sharpens the existing model and enables SENSE to maintain a map of the world—in other words, a world model that gets more accurate with every glimpse."

**Implementation**:
```python
class NarrativeMemoryManager:
    """
    Maintains narrative consistency across 24-hour rollouts
    """
    
    def update_memory(self, new_frame: str, timestamp: datetime):
        """
        After generating each frame, update all memory tiers
        """
        # Short-term: Always keep last 5 frames
        self.short_term.push(new_frame)
        
        # Medium-term: Every 3 hours, generate summary
        if self.time_for_summary(timestamp):
            summary = self.generate_period_summary()
            self.medium_term.add_summary(summary)
        
        # Long-term: Extract and verify established facts
        facts = self.extract_facts(new_frame)
        for fact in facts:
            if not self.conflicts_with_existing(fact):
                self.long_term.establishedFacts[fact.key] = fact.value
    
    def get_consistency_context(self) -> str:
        """
        Returns context string ensuring narrative coherence
        """
        return f"""
        REMEMBER (established facts):
        {self.format_long_term_facts()}
        
        TODAY'S FLOW:
        {self.medium_term.morningSummary or "Morning not yet summarized"}
        {self.medium_term.afternoonSummary or "Afternoon not yet summarized"}
        
        RECENT CONTEXT (last hour):
        {self.format_short_term()}
        """
```

### Conflict Detection

```python
def detect_temporal_conflicts(
    proposed_narrative: str, 
    established_facts: Dict[str, str]
) -> List[Conflict]:
    """
    Check if proposed narrative contradicts established facts
    
    Examples of conflicts:
    - "The scribe awoke" at 3pm (already established wake time was 7am)
    - "First cup of coffee" at 2pm (already had 3 coffees in morning)
    - "Began working on world-models" at 5pm (already worked 4 hours on it)
    """
    conflicts = []
    
    for fact_key, fact_value in established_facts.items():
        if implies_contradiction(proposed_narrative, fact_key, fact_value):
            conflicts.append(Conflict(
                type=fact_key,
                established=fact_value,
                proposed=extract_contradiction(proposed_narrative, fact_key)
            ))
    
    return conflicts
```

### Recovery from Inconsistencies

**From Dreamer 4**:
> "World models learn general knowledge from videos and simulate experience for training behaviors in imagination."

If inconsistency detected:
1. **Flag the inconsistency** in metadata
2. **Generate alternative frame** that maintains consistency
3. **Log for review** to improve model
4. **Use as training data** (negative example)

---

## Narrative Generation Pipeline

### The Prompt Architecture

```python
NARRATIVE_PROMPT = """
You are a world model predicting the next state of a person's life.
Write in the rich, descriptive style of J.R.R. Tolkien's "The Hobbit".

CONTEXT:
- Current Time: {timestamp}
- Time of Day: {timeOfDay}
- Activity: {currentActivity.primary} ({currentActivity.secondary})
- Location: {digitalLocation.domain} / {digitalLocation.project}
- Recent Activity:
{format_narrative_history(narrativeHistory)}

PREVIOUS NARRATIVE:
{narrativeHistory[-1] if narrativeHistory else "The day begins..."}

TASK:
Write the next narrative "frame" (2-3 sentences) describing what happens next.
- Continue the story naturally from the previous state
- Use Tolkien-esque prose (rich descriptions, fantasy metaphors)
- Describe the activity based on the context data
- Suggest what might come next (but don't jump too far ahead)

OUTPUT FORMAT:
Just the narrative text. No headers, no bullet points.
"""
```

### Example Generation

**Input State** (9:18 AM):
- Activity: coding, world-models documentation
- Location: github.com / world-models project
- Previous: "The browser window flickered with new knowledge..."

**Generated Output**:
> "The scribe's fingers danced across the enchanted keys, weaving markdown spells into the digital tome. Lines of structured wisdom flowed like the Great River, cataloging the discoveries of DreamDojo and DreamZero for future seekers of knowledge."

### Temperature & Sampling

From **DreamZero**:
> "The temperature for model inference is set to 0.6"

**Recommendation**: 
- Temperature: 0.7 (some creativity, not too random)
- Top-p: 0.9
- Max tokens: 100 per frame

---

## Full-Day Rollout System

### Midnight-to-Midnight Architecture

The system generates a complete narrative timeline by **autoregressively** predicting each next state:

```python
class DayRolloutGenerator:
    """
    Generates a full 24-hour narrative rollout
    """
    
    def generate_day_rollout(
        self,
        start_time: datetime,  # 2026-03-21T00:00:00
        initial_state: LifeState,
        time_step_minutes: int = 15  # Generate every 15 minutes
    ) -> List[NarrativeFrame]:
        """
        Returns 96 narrative frames (15-min intervals × 24 hours)
        """
        frames = []
        current_state = initial_state
        
        for i in range(96):  # 24 hours ÷ 15 minutes
            # Generate next narrative frame
            narrative = self.world_model.predict_next_state(current_state)
            
            # Create timestamp for this frame
            frame_time = start_time + timedelta(minutes=i * 15)
            
            # Create frame object
            frame = NarrativeFrame(
                timestamp=frame_time,
                narrative=narrative,
                state=current_state
            )
            frames.append(frame)
            
            # Update state for next prediction (autoregressive)
            current_state = self.update_state_with_prediction(
                current_state, 
                narrative,
                frame_time
            )
        
        return frames
```

### Rollout Visualization

```
00:00 - "The night was deep and still when the scribe finally surrendered to the embrace of dreams, the glowing screen casting long shadows upon the walls..."

00:15 - "[Sleep continues - no activity detected]"

00:30 - "[Sleep continues - no activity detected]"

...

07:00 - "The first light of dawn crept through the curtains, rousing the sleeper from distant dreams of far-off lands and forgotten quests..."

07:15 - "With weary eyes still heavy with slumber, the scribe reached for the small glowing rectangle that held the day's first mysteries..."

07:30 - "The scent of morning coffee filled the quiet chamber as fingers brushed against the enchanted keys, awakening the machines..."

...

09:00 - "In the bright morning hours, the researcher delved deep into ancient scrolls of AI wisdom, seeking patterns in the world models of distant laboratories..."

09:15 - "The browser window flickered with new knowledge—NVIDIA's DreamDojo, a generalist robot world model trained upon 44,000 hours of human endeavor..."

09:30 - "The scribe's fingers danced across the enchanted keys, weaving markdown spells into the digital tome, cataloging discoveries for future seekers..."

...

12:00 - "As the sun reached its zenith, the scribe paused in their labors, seeking sustenance in the form of a humble midday meal..."

...

23:45 - "The hour grew late, and the candles burned low. With one final commit to the great repository, the day's labors were laid to rest..."

00:00 - "The night embraced the weary scribe once more, dreams of world models and digital realms fading into the peaceful dark..."
```

### Conditional Rollouts (What-If Scenarios)

From **DreamZero** research:
> "What are the limits on task generalization beyond what NEO has already seen and done?"

**Implementation**:

```python
def generate_conditional_rollout(
    self,
    start_state: LifeState,
    intervention: str  # e.g., "What if I skip my meeting?"
) -> List[NarrativeFrame]:
    """
    Generate a rollout with a specific intervention
    """
    # Modify the prompt to include the intervention
    modified_prompt = f"""
    {base_prompt}
    
    SPECIAL CONDITION: {intervention}
    Describe what happens differently given this change.
    """
    
    # Generate the alternative timeline
    return self.generate_rollout(start_state, modified_prompt)
```

**Example Interventions**:
- "What if I don't check email until noon?"
- "What if I work from a cafe instead of home?"
- "What if I take a 2-hour midday walk?"

---

## Training Approach: Two Paradigms

The research shows **two distinct approaches** to world models:

### Paradigm 1: Deep Learning (NVIDIA, DeepMind, Rhoda)
- Massive pre-training on diverse data
- Neural network architectures
- Scale-driven performance
- **Examples**: DreamDojo, DreamZero, Genie 3, Dreamer 4

### Paradigm 2: Active Inference (VERSES AI)
- Probabilistic Bayesian models
- Real-time belief updating
- No pre-training required (learns on-the-fly)
- **Examples**: Genius SENSE/THINK/ACT/SHARE

**This MVP uses Paradigm 1** (deep learning with LLMs) because it's more accessible for a weekend project, but we'll incorporate insights from both.

---

### Phase 1: Literary Style Pre-training (Offline Training)

**Insight from Dreamer 4**:
> "World models learn general knowledge from videos and simulate experience for training behaviors in imagination, offering a path towards intelligent agents."
> 
> "Extracts the majority of its knowledge from **diverse unlabeled videos**... learns general action conditioning from only a **small amount of data**"

**Application to Text**: Instead of video, we use literature (The Hobbit) as "unlabeled narrative data" to learn the "physics" of fantasy storytelling.

**Data**: The Hobbit (full text) + similar rich narrative books

**Objective**: Learn Tolkien-esque prose style, pacing, world-building patterns

**Implementation**:
```python
# Two approaches:
# A) Fine-tune a small model (GPT-2, TinyLlama) on The Hobbit
# B) Few-shot prompting with base model (GPT-4/Claude) - RECOMMENDED for MVP

FEW_SHOT_EXAMPLES = [
    {
        "context": "Morning, waking up, checking phone",
        "narrative": "The first grey light of dawn crept through the round window of Bag End, waking the hobbit from pleasant dreams. With a yawn and a stretch, he reached for the small brass bell to summon his morning tea."
    },
    {
        "context": "Walking through a forest, discovering something new",
        "narrative": "The path wound deeper into the dark woods, where the branches grew thick and the light grew dim. It was then, beneath an ancient oak, that he spotted something glinting in the undergrowth—a small key, no bigger than a matchstick, yet heavy with the promise of secrets."
    },
    # ... 20-30 examples covering:
    # - Morning routines
    # - Work/research activities
    # - Meals and breaks
    # - Evening wind-down
    # - Sleep
]
```

**Offline Training Advantage** (from Dreamer 4):
> "Dreamer 4 is the first agent to obtain diamonds in Minecraft **purely from offline data, without environment interaction**"

Your model learns the "literary physics" of how stories flow without needing to interact with your actual life first.

---

### Phase 2: Personalization (Domain Adaptation)

From **DreamZero**:
> "Adapts to YAM robot with only **30 minutes of play data** (55 trajectories)"

From **Rhoda AI**:
> "Data-efficient task learning with as little as **~10 hours** of robot data"

From **VERSES AI** (Alternative View):
> "ACT allows robots and agents to learn new tasks quickly in physical and digital worlds, **without the extensive pre-training that conventional systems require**"
> 
> "In August 2025, we published results of our robotics model, which outperformed other models on Meta's Habitat benchmark simulation **without any pre-training**... Unlike a deep-learning robotics model that required imitation-based pre-training with more than 1.3 billion steps to acquire these skills, the VERSES model adapted and learned in real time."

**The Hybrid Approach for Your MVP**:

```python
# Collect 7-14 days of your personal data
# Create "state → narrative" pairs from real life

PERSONAL_EXAMPLES = [
    {
        "state": {
            "time": "09:15",
            "activity": "coding",
            "project": "world-models",
            "location": "home office"
        },
        "narrative": "In the quiet of the morning study, with coffee steaming beside the enchanted screen, the scribe wove markdown spells into the digital tome..."
    },
    # ... 50-100 examples covering your typical patterns
]

# Training strategy:
# 1. Start with The Hobbit few-shot examples (general narrative skill)
# 2. Add your personal examples (domain adaptation)
# 3. Use in-context learning at inference time (mix general + personal)
```

**Implementation**:
```python
# Collect 7-14 days of your personal data
# Create "state → narrative" pairs from real life

PERSONAL_EXAMPLES = [
    {
        "state": {
            "time": "09:15",
            "activity": "coding",
            "project": "world-models",
            "location": "home office"
        },
        "narrative": "In the quiet of the morning study, with coffee steaming beside the enchanted screen, the scribe wove markdown spells into the digital tome..."
    },
    # ... examples from YOUR actual life
]
```

**Key Insight**: You don't need 44,000 hours of data! The model already knows how to write (from The Hobbit). You just need enough personal examples to teach it YOUR patterns.

### Phase 3: Continuous Learning

From **UI-Simulator-Grow**:
> "Continual learning with replay strategy... selects the most representative tasks from previous iteration"

**Implementation**:
- Weekly review of generated rollouts vs. actual life
- Identify mismatches (model got it wrong)
- Add correct examples to training set
- Re-fine-tune or update few-shot examples

---

## Movie Comparison: Everything Everywhere All At Once

### The Connection

**YES! Your project is conceptually similar to the movie!**

In the movie:
- Characters can see and experience multiple parallel universes ("the multiverse")
- Each universe shows a different version of how their life could have gone
- The protagonist jumps between these "rollouts" to find the best path

Your world model does the same:
- Generates multiple possible timelines (rollouts) of your day
- Each rollout shows a different version of how your life could unfold
- You can compare them: "What if I code vs. what if I take a walk?"

### Key Differences

| Movie | Your World Model |
|-------|-----------------|
| Jump between universes instantly | Generate narratives sequentially |
| Visual/sensory experience | Text-based narrative descriptions |
| Infinite universes | Finite rollouts (computational limits) |
| Must be experienced | Can be read and compared side-by-side |
| Cosmic stakes | Personal, practical stakes |

### The "Everything Bagel" Moment

In the movie, the antagonist creates an "everything bagel"—a black hole representing all possibilities at once.

Your equivalent:
> Generate 10 parallel rollouts from the same starting point (9:00 AM), each with slight variations in randomness, then compare them side-by-side to see the "shape of possible futures."

This is the **best-of-N sampling** mentioned in the research:

> "Generating multiple rollouts in parallel and executing the best one... the ability to select the highest quality generation from eight choices does lead to improved task success." — *1X World Model*

### Practical Application

**Morning Planning Ritual**:
1. Generate 3 parallel rollouts from current state
2. Read each "possible future"
3. Choose which timeline to pursue
4. Take actions to steer reality toward that rollout

It's like the movie's multiverse jumping, but for your daily productivity!

---

## Implementation Phases

### Phase 1: Data Pipeline (Week 1)

**Goal**: Collect and store personal data

**Tasks**:
1. Create Chrome history scraper
2. Create file system watcher
3. Create system context monitor
4. Set up SQLite database schema
5. Test data collection for 24 hours

**Deliverable**: Database with 24 hours of personal data

### Phase 2: State Encoder (Week 1-2)

**Goal**: Convert raw data into structured "LifeState" objects

**Tasks**:
1. Parse Chrome history into meaningful activities
2. Infer context from file paths (project detection)
3. Classify activities (coding, research, communication)
4. Build state history management

**Deliverable**: Function that takes timestamp → returns LifeState

### Phase 3: Narrative Generator (Week 2)

**Goal**: Generate Tolkien-esque prose from LifeState

**Tasks**:
1. Prepare few-shot examples from The Hobbit
2. Create prompt template
3. Integrate with Claude/GPT-4 API
4. Test generation quality
5. Iterate on prompts

**Deliverable**: Working narrative generator with good prose quality

### Phase 4: Rollout Engine (Week 3)

**Goal**: Autoregressive full-day generation

**Tasks**:
1. Build autoregressive loop (state → narrative → next state)
2. Implement 24-hour timeline generation
3. Handle sleep/idle periods gracefully
4. Create visualization/output format

**Deliverable**: Generate complete day rollout from midnight to midnight

### Phase 5: Personalization (Week 4+)

**Goal**: Make it sound like YOUR life, not generic

**Tasks**:
1. Collect 7 days of personal data
2. Create personal few-shot examples
3. Fine-tune or prompt-tune on your patterns
4. Test accuracy (does it predict you correctly?)

**Deliverable**: Personalized world model that knows your routines

### Phase 6: Conditional Rollouts (Week 5+)

**Goal**: "What-if" scenario generation

**Tasks**:
1. Add intervention system
2. Generate alternative timelines
3. Compare rollouts side-by-side
4. Build user interface for choosing paths

**Deliverable**: Everything Everywhere All At Once-style multiverse viewer

---

## Implementation Details for Claude

This section provides specific technical details, edge cases, and patterns Claude needs to implement the MVP correctly.

### Code Organization

```
src/life_world_model/
├── __init__.py              # Package version, imports
├── config.py                # Pydantic settings, env vars
├── exceptions.py            # Custom exceptions
├── collectors/
│   ├── __init__.py
│   ├── base.py             # Abstract base class
│   ├── chrome_collector.py
│   ├── filesystem_collector.py
│   ├── system_collector.py
│   └── git_collector.py
├── models/
│   ├── __init__.py
│   ├── llm_interface.py    # API client wrapper
│   └── prompts.py          # Prompt templates
├── memory/
│   ├── __init__.py
│   ├── manager.py          # Memory management
│   ├── facts.py            # Fact extraction/storage
│   └── conflicts.py        # Conflict detection
├── generators/
│   ├── __init__.py
│   ├── base.py             # Abstract generator
│   ├── day_rollout.py      # 24-hour rollout
│   ├── live_narrator.py    # Real-time mode
│   └── conditional.py      # What-if scenarios
├── utils/
│   ├── __init__.py
│   ├── state_encoder.py    # Convert raw data to LifeState
│   ├── database.py         # SQLite interface
│   └── logging.py          # Structured logging
└── cli.py                  # Click CLI entry point
```

### Error Handling Strategy

```python
# exceptions.py
class LifeWorldModelError(Exception):
    """Base exception"""
    pass

class DataCollectionError(LifeWorldModelError):
    """Failed to collect data from a source"""
    pass

class ChromeHistoryError(DataCollectionError):
    """Chrome history unavailable or locked"""
    pass

class APIGenerationError(LifeWorldModelError):
    """LLM API failed"""
    pass

class MemoryConsistencyError(LifeWorldModelError):
    """Narrative conflict detected"""
    pass

class InsufficientDataError(LifeWorldModelError):
    """Not enough data to generate meaningful narrative"""
    pass
```

**Handling Pattern**:
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def generate_narrative(state: LifeState) -> str:
    try:
        response = client.messages.create(...)
        return response.content[0].text
    except anthropic.RateLimitError as e:
        logger.warning("Rate limited, waiting...")
        raise APIGenerationError("Rate limited") from e
    except anthropic.APIError as e:
        logger.error(f"API error: {e}")
        # Fallback: use cached similar narrative or generic
        return get_fallback_narrative(state)
```

### Database Schema (SQLite)

```sql
-- schema.sql
CREATE TABLE IF NOT EXISTS raw_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    source TEXT NOT NULL,  -- 'chrome', 'filesystem', 'system', 'git'
    event_type TEXT NOT NULL,
    data JSON,  -- Flexible JSON storage
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS life_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL UNIQUE,
    time_of_day TEXT,
    primary_activity TEXT,
    secondary_activity TEXT,
    domain TEXT,
    project TEXT,
    app TEXT,
    raw_data_sources JSON,  -- Which sources contributed
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS narrative_frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    state_id INTEGER,
    narrative TEXT NOT NULL,
    temperature REAL,
    model_version TEXT,
    FOREIGN KEY (state_id) REFERENCES life_states(id)
);

CREATE TABLE IF NOT EXISTS established_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_key TEXT NOT NULL UNIQUE,  -- e.g., 'wake_time', 'first_meal'
    fact_value TEXT NOT NULL,
    established_at DATETIME NOT NULL,
    confidence REAL DEFAULT 1.0
);

CREATE INDEX idx_events_timestamp ON raw_events(timestamp);
CREATE INDEX idx_states_timestamp ON life_states(timestamp);
CREATE INDEX idx_frames_timestamp ON narrative_frames(timestamp);
```

### Edge Cases & Handling

#### 1. Sleep/Idle Periods

**Problem**: User sleeps from 00:00-07:00. No data collected.

**Solution**:
```python
def handle_sleep_periods(frames: List[NarrativeFrame]) -> List[NarrativeFrame]:
    """
    If no activity detected for > 2 hours (and it's nighttime):
    - Mark as [Sleep - continues]
    - Don't call expensive API for each 15-min slot
    - Generate one "sleep" narrative, repeat with minor variations
    """
    result = []
    sleep_start = None
    
    for frame in frames:
        if is_nighttime(frame.timestamp) and frame.activity == "idle":
            if sleep_start is None:
                sleep_start = frame.timestamp
                # Generate rich sleep narrative once
                frame.narrative = generate_sleep_narrative(time_of_night=frame.timestamp)
            else:
                # Reuse narrative with variation
                hours_slept = (frame.timestamp - sleep_start).total_seconds() / 3600
                frame.narrative = vary_sleep_narrative(hours_slept)
        else:
            sleep_start = None
            result.append(frame)
    
    return result

# Narrative variations for sleep
SLEEP_VARIATIONS = [
    "The night was deep and still...",
    "Dreams of far-off lands drifted through the sleeping mind...",
    "The darkness held the world in gentle embrace...",
    "Slumber continued undisturbed...",
]

def vary_sleep_narrative(hours_slept: float) -> str:
    base = random.choice(SLEEP_VARIATIONS)
    if hours_slept > 6:
        return f"{base} The night had grown long, and dawn approached."
    return base
```

#### 2. Missing Data Gaps

**Problem**: Data collection failed for 2 hours (Chrome locked, etc.)

**Solution**:
```python
def interpolate_missing_states(
    start_time: datetime,
    end_time: datetime,
    known_states: List[LifeState]
) -> List[LifeState]:
    """
    Interpolate states between known data points
    """
    result = []
    current = start_time
    
    while current < end_time:
        # Find nearest known states
        before = find_last_state_before(current, known_states)
        after = find_first_state_after(current, known_states)
        
        if before and after and (after.timestamp - before.timestamp) < timedelta(hours=3):
            # Interpolate reasonably
            state = interpolate_state(before, after, current)
        else:
            # Too big a gap - mark as unknown but keep timeline
            state = LifeState(
                timestamp=current,
                time_of_day=infer_time_of_day(current),
                primary_activity="unknown",
                secondary_activity=None,
                confidence=0.3  # Low confidence
            )
        
        result.append(state)
        current += timedelta(minutes=15)
    
    return result

def interpolate_state(before: LifeState, after: LifeState, target: datetime) -> LifeState:
    """
    Simple interpolation - if before was coding and after was coding, probably still coding
    """
    if before.primary_activity == after.primary_activity:
        return LifeState(
            timestamp=target,
            primary_activity=before.primary_activity,
            secondary_activity=before.secondary_activity,
            confidence=0.7  # Medium confidence
        )
    # Different activities - transition state
    return LifeState(
        timestamp=target,
        primary_activity="transition",
        secondary_activity=f"from_{before.primary_activity}_to_{after.primary_activity}",
        confidence=0.5
    )
```

#### 3. API Failures During Rollout

**Problem**: API rate limited or down mid-rollout (frame 45 of 96)

**Solution**:
```python
class ResilientRolloutGenerator:
    def generate_with_fallback(
        self,
        start_time: datetime,
        initial_state: LifeState
    ) -> List[NarrativeFrame]:
        frames = []
        current_state = initial_state
        
        for i in range(96):
            try:
                narrative = self.generate_frame(current_state)
            except APIGenerationError:
                # Fallback 1: Use cached similar narrative
                narrative = self.find_similar_cached_narrative(current_state)
                
                if not narrative:
                    # Fallback 2: Use generic template
                    narrative = self.generic_narrative_template(current_state)
                
                # Mark as fallback
                logger.warning(f"Frame {i}: Used fallback narrative")
            
            frame = NarrativeFrame(
                timestamp=start_time + timedelta(minutes=i*15),
                narrative=narrative,
                state=current_state,
                is_fallback=isinstance(narrative, FallbackNarrative)
            )
            frames.append(frame)
            
            # Update state
            current_state = self.update_state(current_state, narrative)
        
        return frames
```

#### 4. Chrome History Privacy Mode

**Problem**: Chrome in Incognito or history cleared

**Solution**:
```python
def collect_chrome_history(since: datetime) -> List[ChromeEvent]:
    db_path = Path.home() / "Library/Application Support/Google/Chrome/Default/History"
    
    if not db_path.exists():
        logger.warning("Chrome History DB not found")
        return []
    
    try:
        # Chrome locks the DB when running - copy it first
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        shutil.copy2(db_path, temp_db.name)
        temp_db.close()
        
        conn = sqlite3.connect(temp_db.name)
        # ... query logic ...
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            logger.error("Chrome History locked (browser running)")
            # Try reading from Last Session instead
            return collect_from_last_session(since)
        raise ChromeHistoryError(f"Failed to read Chrome history: {e}")
    finally:
        Path(temp_db.name).unlink(missing_ok=True)
```

### Configuration System

```python
# config.py
from pydantic import BaseSettings, Field
from typing import Optional, List

class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    
    # Model Settings
    default_model: str = "claude-3-sonnet-20240229"
    temperature: float = 0.7
    max_tokens_per_frame: int = 100
    
    # Data Collection
    collection_interval_minutes: int = 15
    chrome_profile: str = "Default"
    watched_directories: List[str] = Field(default_factory=lambda: [
        str(Path.home() / "Projects"),
        str(Path.home() / "Documents")
    ])
    
    # Storage
    database_path: str = "data/life_world_model.db"
    raw_data_retention_days: int = 365
    
    # Generation
    rollout_time_step_minutes: int = 15
    narrative_history_length: int = 5
    
    # Privacy
    anonymize_urls: bool = True  # Remove specific URLs, keep domains only
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

### Prompt Templates (Exact)

```python
# prompts.py

NARRATIVE_PROMPT_TEMPLATE = """You are a world model predicting the next state of a person's life. Write in the rich, descriptive style of J.R.R. Tolkien's "The Hobbit".

CONTEXT:
- Current Time: {timestamp}
- Time of Day: {time_of_day}
- Day: {day_of_week}
- Activity: {primary_activity} ({secondary_activity})
- Location: {domain} / {project}
- App: {app}

ESTABLISHED FACTS (remember these):
{established_facts}

RECENT NARRATIVE HISTORY (continue the story):
{recent_history}

PREVIOUS FRAME:
{previous_narrative}

INSTRUCTIONS:
1. Write 2-3 sentences describing what happens next in this person's life
2. Continue naturally from the previous narrative
3. Use Tolkien-esque prose (rich descriptions, fantasy metaphors, sensory details)
4. Incorporate the established facts - don't contradict them
5. Suggest what might come next (subtle foreshadowing)
6. Match the tone: whimsical, slightly archaic, descriptive

EXAMPLE STYLE:
"With morning coffee steaming beside the glowing screen, the researcher delved into scrolls of ancient AI wisdom, seeking patterns in the world models of distant laboratories. The browser window flickered with new knowledge, and the scribe's fingers danced across enchanted keys, weaving markdown spells into the digital tome."

OUTPUT:
Just the narrative text. No headers, no bullet points, no meta-commentary.
"""

SLEEP_PROMPT_TEMPLATE = """Write a brief (1 sentence) description of sleep continuing during the {time_of_night}.

Use Tolkien-esque style. Focus on:
- The depth of night
- Dreams or rest
- Passage of time
- Atmospheric details

VARIATIONS:
- The night was deep and still...
- Dreams of distant lands drifted through the sleeping mind...
- Darkness held the world in gentle embrace...
- Slumber continued undisturbed beneath the quiet stars...

OUTPUT: Just one sentence.
"""
```

### CLI Interface Specification

```python
# cli.py
import click
from datetime import datetime, timedelta

@click.group()
def cli():
    """Personal Life World Model - Predict your day in Tolkien-esque prose"""
    pass

@cli.command()
@click.option('--days', '-d', default=7, help='Days of data to collect')
@click.option('--background', '-b', is_flag=True, help='Run continuously in background')
def collect(days: int, background: bool):
    """Collect personal data (Chrome history, files, git)"""
    if background:
        click.echo("Starting background data collection...")
        run_collector_daemon()
    else:
        click.echo(f"Collecting {days} days of data...")
        collector = DataCollector()
        collector.collect_range(days=days)
        click.echo("✓ Collection complete")

@cli.command()
@click.option('--date', '-d', default='today', help='Date to generate (YYYY-MM-DD or "today")')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--parallel', '-p', default=1, help='Number of parallel rollouts (for comparison)')
def generate(date: str, output: str, parallel: int):
    """Generate full-day narrative rollout"""
    target_date = parse_date(date)
    
    if parallel > 1:
        click.echo(f"Generating {parallel} parallel rollouts...")
        rollouts = generate_parallel_rollouts(target_date, n=parallel)
        display_comparison(rollouts)
    else:
        click.echo(f"Generating day rollout for {target_date}...")
        generator = DayRolloutGenerator()
        frames = generator.generate(target_date)
        
        output_path = output or f"data/rollouts/{target_date.strftime('%Y-%m-%d')}.md"
        save_rollout(frames, output_path)
        click.echo(f"✓ Saved to {output_path}")

@cli.command()
@click.option('--interval', '-i', default=5, help='Minutes between updates')
def live(interval: int):
    """Run real-time narrator (bard mode)"""
    click.echo(f"Starting live narrator (updates every {interval} minutes)...")
    click.echo("Press Ctrl+C to stop")
    
    narrator = LiveNarrator(interval_minutes=interval)
    try:
        narrator.run()
    except KeyboardInterrupt:
        click.echo("\n✓ Live narrator stopped")

@cli.command()
@click.option('--start', '-s', default='now', help='Start time')
@click.option('--intervention', '-i', required=True, help='What-if scenario (e.g., "skip lunch")')
def whatif(start: str, intervention: str):
    """Generate conditional rollout with intervention"""
    click.echo(f"Generating 'what-if': {intervention}")
    
    generator = ConditionalRolloutGenerator()
    frames = generator.generate(
        start_time=parse_datetime(start),
        intervention=intervention
    )
    
    display_rollout(frames, title=f"What if: {intervention}")

@cli.command()
def demo():
    """Generate demo rollout using synthetic data (no personal data needed)"""
    click.echo("Generating demo rollout with synthetic data...")
    
    generator = DemoRolloutGenerator()
    frames = generator.generate_demo_day()
    
    click.echo("\n" + "="*60)
    click.echo("SAMPLE DAY ROLLOUT (Synthetic Data)")
    click.echo("="*60 + "\n")
    
    for frame in frames[::4]:  # Show every hour (4 frames)
        click.echo(f"{frame.timestamp.strftime('%H:%M')} - {frame.narrative[:100]}...")

if __name__ == '__main__':
    cli()
```

### Testing Strategy

```python
# tests/conftest.py
import pytest
from datetime import datetime, timedelta
from life_world_model.utils.state_encoder import LifeState

@pytest.fixture
def sample_life_state():
    return LifeState(
        timestamp=datetime(2026, 3, 21, 9, 15),
        time_of_day="morning",
        day_of_week="Saturday",
        primary_activity="research",
        secondary_activity="world-models documentation",
        domain="github.com",
        project="world-models",
        app="Chrome"
    )

@pytest.fixture
def mock_chrome_events():
    return [
        {
            "timestamp": datetime(2026, 3, 21, 9, 15),
            "url": "https://github.com/user/world-models",
            "title": "world-models/README.md",
            "domain": "github.com",
            "visit_duration_seconds": 420
        },
        {
            "timestamp": datetime(2026, 3, 21, 9, 22),
            "url": "https://arxiv.org/abs/2602.06949",
            "title": "DreamDojo paper",
            "domain": "arxiv.org",
            "visit_duration_seconds": 180
        }
    ]
```

```python
# tests/test_memory.py
def test_conflict_detection():
    """Test that we detect temporal contradictions"""
    from life_world_model.memory.conflicts import ConflictDetector
    
    detector = ConflictDetector()
    established_facts = {
        "wake_time": "07:00",
        "breakfast": "oatmeal"
    }
    
    # This should trigger conflict
    proposed_narrative = "The scribe awoke at dawn, reaching for morning coffee..."
    
    conflicts = detector.detect(proposed_narrative, established_facts)
    
    assert len(conflicts) == 1
    assert conflicts[0].type == "wake_time"
    assert "already established" in conflicts[0].message

def test_fact_extraction():
    """Test extracting facts from narrative"""
    from life_world_model.memory.facts import FactExtractor
    
    extractor = FactExtractor()
    
    narrative = "The first grey light of dawn crept through the curtains at 7am."
    facts = extractor.extract(narrative, timestamp=datetime(2026, 3, 21, 7, 0))
    
    assert "wake_time" in facts
    assert facts["wake_time"] == "07:00"
```

### File Naming Conventions

```python
# utils/paths.py
from datetime import datetime
from pathlib import Path

def get_rollout_path(date: datetime, variant: str = "default") -> Path:
    """
    Naming convention: {date}_{variant}.md
    Examples:
    - 2026-03-21_default.md
    - 2026-03-21_coding-focused.md
    - 2026-03-21_no-meetings.md
    """
    base = f"{date.strftime('%Y-%m-%d')}_{variant}.md"
    return Path("data/rollouts") / base

def get_db_path() -> Path:
    return Path("data/life_world_model.db")

def get_raw_data_path(source: str, date: datetime) -> Path:
    """
    Naming: data/raw/{source}/{date}.jsonl
    """
    return Path(f"data/raw/{source}/{date.strftime('%Y-%m-%d')}.jsonl")
```

---

## Technical Specifications

### Technology Stack

**Backend**:
- Python 3.11+
- SQLite (data storage)
- OpenAI/Anthropic API (narrative generation)
- watchdog (file system monitoring)
- plistlib (macOS system events)

**Frontend** (optional):
- Terminal output (MVP)
- Simple web UI (Phase 6)
- Markdown reports

**Infrastructure**:
- Runs locally on your machine
- No cloud storage of personal data
- API calls only for narrative generation

### API Costs Estimate

For 96 frames per day (15-minute intervals):
- GPT-4: ~$2-3 per full-day rollout
- Claude: ~$1-2 per full-day rollout
- Local model (once fine-tuned): $0

### Storage Requirements

- Chrome history: ~10MB per year
- File system logs: ~50MB per year
- Generated rollouts: ~100KB per day (text)
- Total: < 1GB for full year

### Performance Targets

**Real-Time Targets** (inspired by Genie 3):
> "**Real-time**: 20-24 frames per second fluid interaction" — *Genie 3*

> "Real-time interactive inference on a **single GPU**" — *Dreamer 4*

**For Text-Based World Model**:
- **Data collection**: Real-time (15-minute intervals) — every 15 min is 0.0011 FPS, easily achievable
- **Narrative generation**: < 500ms per frame (text is faster than video!)
- **Full day rollout**: < 1 minute to generate 96 frames (24 hours ÷ 15 min intervals)
- **Memory retrieval**: < 50ms to recall established facts from earlier in the day

**Why Text is Faster**:
While Genie 3 achieves 20-24 FPS video generation (impressive!), text generation is orders of magnitude faster:
- Video: 720p × 24 FPS = 33 million pixels/second
- Text: ~100 tokens per frame × 96 frames = 9,600 tokens for full day

**Comparison**:
| Model | Medium | Real-Time Speed | Full Day Generation |
|-------|--------|----------------|---------------------|
| Genie 3 | Video | 20-24 FPS | N/A (continuous) |
| Dreamer 4 | Pixels | Single GPU | Minutes (imagination training) |
| **Your MVP** | **Text** | **2 FPS** | **< 1 minute** |

### Real-Time Interaction Mode

Beyond batch generating the full day, support **live mode**:

```python
class RealTimeLifeNarrator:
    """
    Runs continuously, narrating your life as it happens
    Like having a bard following you around, describing your actions
    """
    
    def run_live_mode(self):
        """
        Every 5 minutes:
        1. Check current system state
        2. Generate narrative frame for what just happened
        3. Display/announce it (terminal, notification, etc.)
        4. Update memory banks
        """
        while self.active:
            current_state = self.detect_current_state()
            
            # Generate narrative for last 5 minutes
            narrative = self.world_model.generate_frame(
                current_state,
                memory_context=self.get_relevant_memories()
            )
            
            # Output to user
            self.output_narrative(narrative)
            
            # Update memories
            self.memory_manager.update(narrative, current_state.timestamp)
            
            # Wait 5 minutes
            time.sleep(300)  # 5 minutes
    
    def output_narrative(self, narrative: str):
        """
        Options:
        - Print to terminal
        - macOS notification
        - Log to file for daily compilation
        - Speak aloud (text-to-speech) for truly immersive experience!
        """
        print(f"[{datetime.now().strftime('%H:%M')}] {narrative}\n")
        
        # Optional: macOS notification
        os.system(f'''
            osascript -e 'display notification "{narrative[:100]}..." with title "Life World Model"'
        ''')
```

**Live Mode Use Cases**:
1. **Morning startup**: Narrates your routine as you do it
2. **Work session**: Describes your coding/research in literary style
3. **Break reminders**: "The scribe has been hunched over the glowing screen for many hours..."
4. **End of day**: Summarizes what you accomplished

---

## Safety & Privacy Considerations

### Data Privacy

**Principle**: All personal data stays on your machine

- Chrome history: Read locally, store in local SQLite
- File system: Monitor locally, never upload
- API calls: Only send activity summaries (not raw URLs/files)

### Security

- Database encrypted at rest
- No network access except to API endpoints
- Audit logging of all data access

### Ethical Considerations

From **The Bitter Lesson** reminder in the research:
> "We want AI agents that can discover like we can, not which contain what we have discovered."

**Implementation**:
- Model helps you discover patterns in your own life
- Does not make decisions for you
- You control all interventions and choices
- Transparent about what's predicted vs. actual

### Consent & Control

- Easy pause/stop of data collection
- Clear view of what data is collected
- Option to delete all personal data
- No sharing of rollouts without explicit consent

---

## Success Metrics

### Qualitative

- [ ] Narratives sound like Tolkien (rich, descriptive)
- [ ] Narratives accurately describe your activities
- [ ] Predictions feel "surprisingly right" about your patterns
- [ ] Useful for morning planning
- [ ] Fun to read your life as a fantasy novel

### Quantitative

- [ ] Generate 96 frames in < 5 minutes
- [ ] Activity classification > 80% accurate
- [ ] Project detection > 90% accurate
- [ ] Timeline continuity (no jumps > 1 hour unexplained)

---

## Appendix: Two Paradigms in Practice

### Choosing Your Approach

The research landscape shows **two fundamentally different ways** to build world models. Here's how to choose for your personal project:

#### Paradigm 1: Deep Learning (This MVP)
**Philosophy**: Scale is the primary driver. Pre-train on massive data, fine-tune on personal data.

**From the research**:
> "All successful world models rely on massive pre-training (web-scale video, 44k hours of human data)" — *The Bitter Lesson*

**Pros**:
- Works out-of-the-box with GPT-4/Claude APIs
- Rich, creative prose generation
- Quick to prototype (weekend project)
- No need to understand the "physics" of your life

**Cons**:
- Requires API calls (costs ~$1-3 per day)
- Less interpretable (black box)
- Needs personal data to adapt (7-14 days minimum)
- Hallucinations possible

**Best for**: Creative narrative generation, quick prototyping, literary quality

---

#### Paradigm 2: Active Inference (Future Extension)
**Philosophy**: Build probabilistic models that update beliefs in real-time. No pre-training needed.

**From VERSES AI**:
> "ACT allows robots and agents to learn new tasks quickly in physical and digital worlds, **without the extensive pre-training that conventional systems require**"

**Pros**:
- Learns in real-time (no pre-training period)
- Interpretable (you can see the probability distributions)
- Works with zero personal data (learns as it goes)
- More robust to novel situations
- Privacy-preserving (runs locally)

**Cons**:
- More complex to implement
- Requires probabilistic programming knowledge
- Prose quality might be less "literary"
- Needs custom model development

**Best for**: Long-term deployment, privacy-critical applications, scientific rigor

---

### Hybrid Approach (Recommended for v2.0)

**Combine both paradigms**:

```
LAYER 1: Deep Learning (LLM)
- Generates the rich, Tolkien-esque prose
- Handles creativity and literary quality
- API-based (GPT-4/Claude)

         ↓

LAYER 2: Active Inference (Bayesian)
- Maintains belief state about your patterns
- Updates probabilities in real-time
- Handles uncertainty and predictions
- Runs locally (no API)

         ↓

OUTPUT: Layer 1 prose guided by Layer 2 beliefs
```

**Example Integration**:

```python
class HybridLifeWorldModel:
    """
    Combines deep learning (LLM) with active inference (Bayesian)
    """
    
    def __init__(self):
        self.llm = LLMInterface()  # GPT-4/Claude for prose
        self.bayesian = ActiveInferenceEngine()  # Local probabilistic model
    
    def generate_frame(self, current_state: LifeState) -> str:
        # Step 1: Bayesian layer updates beliefs
        # "What's the probability they're still coding at 3pm?"
        beliefs = self.bayesian.infer_next_state(current_state)
        
        # Step 2: LLM layer generates prose conditioned on beliefs
        # "Given 85% probability they're coding, write narrative"
        prompt = f"""
        Current state: {current_state}
        
        Probabilistic predictions:
        - Coding: {beliefs['coding']:.0%}
        - Break: {beliefs['break']:.0%}
        - Meeting: {beliefs['meeting']:.0%}
        
        Write narrative reflecting most likely activity.
        """
        
        narrative = self.llm.generate(prompt)
        
        # Step 3: Bayesian layer updates based on what actually happened
        self.bayesian.update_beliefs(current_state, narrative)
        
        return narrative
```

**Why This is Powerful**:
- **LLM** handles what it's good at: creativity, prose, style
- **Bayesian** handles what it's good at: uncertainty, learning, adaptation
- You get literary quality + rigorous probabilistic predictions
- Can run Bayesian layer locally (privacy) while using API for prose (quality)

---

### Migration Path

**Phase 1** (This MVP): Deep learning only (quick to build)
**Phase 2** (Future): Add Bayesian layer for predictions
**Phase 3** (Advanced): Full hybrid with local LLM (no API costs)

---

## Future Extensions (Post-MVP)

### Short Term
- Voice input for manual state updates
- Integration with calendar APIs
- Physical location detection (GPS/WiFi)
- Mood/energy tracking
- Hybrid paradigm (add Bayesian layer)

### Medium Term
- Visual world model (generate images of predicted states)
- Multi-day rollouts (predict whole week)
- Goal-conditioned rollouts ("how do I finish this project by Friday?")
- Social rollouts (predict interactions with specific people)
- Local LLM deployment (no API costs)

### Long Term
- Real-time course correction (gentle notifications: "your current path leads to X")
- Predictive task suggestions
- Life narrative compilation (your entire year as a fantasy novel)
- Active inference full implementation (no pre-training needed)

---

## Conclusion

This blueprint describes a **text-based world model** that applies the principles from cutting-edge world model research to **personal life prediction**.

### Research Synthesized

**Visual World Models** (Robotics, 3D):
- DreamDojo, DreamZero (NVIDIA): 44k hours video, zero-shot generalization
- 1X World Model: Real-time humanoid control via video prediction
- Genie 3 (DeepMind): First real-time interactive world model at 20-24 FPS
- Dreamer 4: Training agents inside world models from offline data
- World Labs (Fei-Fei Li): Spatial intelligence as next frontier
- Seoul World Model: City-scale generation with memory consistency

**Text/UI World Models** (Digital Agents):
- UI-Simulator: LLM-based digital world simulation
- VERSES AI/Genius: Active inference paradigm (Bayesian, real-time learning)

**Your Innovation**: Applying these principles to **personal life narrative generation**—text as the representation medium, with the literary quality of The Hobbit and the predictive power of world models.

### Key Innovations

1. **Text/Narrative** instead of video (following UI-Simulator approach)
2. **Memory & Consistency** architecture (from Genie 3's recall mechanisms)
3. **Offline Training** paradigm (from Dreamer 4: learn from The Hobbit first, then adapt)
4. **Full-day autoregressive rollouts** (midnight to midnight, 96 frames)
5. **Conditional what-if scenarios** (like Everything Everywhere All At Once)
6. **Two paradigms** documented: Deep Learning (now) + Active Inference (future)

### Two Paths Forward

**Path A: Deep Learning MVP** (Recommended for now)
- Quick to build (5-6 weeks)
- GPT-4/Claude for prose generation
- Costs ~$1-3/day in API calls
- Requires 7-14 days personal data
- High literary quality

**Path B: Active Inference Future** (v2.0)
- More complex but powerful
- Bayesian belief updating
- No pre-training required
- Fully local (privacy)
- Scientific rigor

**The Hybrid Path**: Combine both—LLM for prose quality, Bayesian for predictions.

### Implementation Path

**Phase 1** (Week 1-2): Data pipeline + State encoder
**Phase 2** (Week 2-3): Narrative generator with The Hobbit examples
**Phase 3** (Week 3-4): Full-day rollout system (96 frames)
**Phase 4** (Week 4-5): Personalization with your data
**Phase 5** (Week 5-6): Conditional rollouts + live mode
**Phase 6** (Future): Hybrid paradigm, visual generation, week-long predictions

### The Ultimate Goal

Transform your digital life data into a rich, Tolkien-esque narrative that helps you:
- **See possible futures** (multiverse viewer for productivity)
- **Choose your path** (conditional rollouts + planning)
- **Understand patterns** (Bayesian belief tracking)
- **Reflect on life** (daily narrative as fantasy novel)

Like having a personal bard that follows you around, describing your life in epic prose while helping you navigate possible timelines—just like Everything Everywhere All At Once, but for your daily productivity.

---

## Complete References (All Research Papers & URLs)

**EVERY implementation decision in this document traces back to these sources. Claude MUST reference these when building:**

### Core World Model Research (Your Original Links)

1. **DreamDojo (NVIDIA)** - Large-scale robot world models
   - Website: https://dreamdojo-world.github.io/
   - Paper: https://arxiv.org/abs/2602.06949
   - Code: https://github.com/NVIDIA/DreamDojo
   - **Key Quote**: "44,000 hours of diverse human egocentric videos"
   - **Applied**: Pre-training paradigm using The Hobbit as "44k hours" of narrative data

2. **1X World Model** - Humanoid robot world models
   - Website: https://www.1x.tech/discover/world-model-self-learning
   - **Key Quote**: "70 hours of robot data to adapt to NEO's visual appearance and kinematics"
   - **Applied**: 7-14 days personal data for adaptation after literary pre-training

3. **Rhoda AI DVA** - Direct Video-Action models
   - Website: https://www.rhoda.ai/research/direct-video-action
   - **Key Quote**: "Data-efficient task learning with as little as ~10 hours of robot data"
   - **Applied**: 10 hours personal data benchmark; text-based approach ("not called world model but first part of pipeline is similar")

4. **DreamZero (NVIDIA)** - Zero-shot robot policies
   - Website: https://dreamzero0.github.io/
   - Paper: https://arxiv.org/abs/2602.15922
   - Code: https://github.com/dreamzero0/dreamzero
   - **Key Quote**: "Adapts to YAM robot with only 30 minutes of play data"
   - **Applied**: Minimal data adaptation; cross-embodiment transfer principles

5. **Seoul World Model** - City-scale world simulation
   - Website: https://seoul-world-model.github.io/
   - Paper: https://arxiv.org/abs/2603.15583
   - Code: https://github.com/naver-ai/seoul-world-model
   - **Key Quote**: "Virtual Lookahead Sink: Continuously re-grounds generation over hundreds of meters"
   - **Applied**: Memory Manager as equivalent for 24-hour narrative consistency

6. **UI-Simulator** - Digital agent world models
   - Paper: https://arxiv.org/abs/2510.14969
   - Code: https://github.com/WadeYin9712/UI-Simulator
   - **Key Quote**: "Digital world model built on LLMs that generates structured accessibility trees with textual content, spatial coordinates, dynamic attributes"
   - **Applied**: **THIS IS THE CORE PRECEDENT** - Text-based world models work!

7. **Stable-WorldModel-v1** - Reproducible world model research
   - Paper: https://arxiv.org/abs/2602.08968
   - Authors: Lucas Maes, Quentin Le Lidec, Dan Haramati, Nassim Massaudi, Damien Scieur, **Yann LeCun**, **Randall Balestriero**
   - **Key Quote**: "World Models have emerged as a powerful paradigm for learning compact, predictive representations of environment dynamics, enabling agents to reason, plan, and generalize beyond direct experience"
   - **Applied**: Core definition of what a world model is (not necessarily visual!)

### Latest Research (March 2026 Update)

8. **Genie 3 (Google DeepMind)** - Interactive world generation
   - Website: https://deepmind.google/models/genie/
   - **Key Quote**: "First real-time, interactive world model at 20-24 FPS, with memory recalling changes from specific interactions for up to a minute"
   - **Applied**: Three-tier memory system (short/medium/long-term)

9. **Dreamer 4** - Training agents inside world models
   - Paper: https://arxiv.org/abs/2509.24527
   - Website: https://danijar.com/dreamer4/
   - **Key Quote**: "First agent to obtain diamonds in Minecraft purely from offline data, without environment interaction"
   - **Applied**: Offline training paradigm (The Hobbit pre-training)

10. **World Labs** - Spatial intelligence
    - Website: https://www.worldlabs.ai/blog
    - **Key Quote**: "3D is becoming the universal interface for space"
    - **Applied**: Time as spatial dimension (midnight→midnight timeline)

11. **VERSES AI / Genius** - Active inference paradigm
    - Website: https://www.verses.ai/blog/genius-can-sense-think-act-and-share-intelligently
    - **Key Quote**: "Genius: SENSE/THINK/ACT/SHARE — learning in real-time without extensive pre-training"
    - **Applied**: Future v2.0 Bayesian approach (alternative to deep learning)

### Additional Context

12. **The Bitter Lesson** - Rich Sutton
    - URL: http://www.incompleteideas.net/IncIdeas/BitterLesson.html
    - **Key Quote**: "The biggest lesson that can be read from 70 years of AI research is that general methods that leverage computation are ultimately the most effective"
    - **Applied**: Scale pre-training (The Hobbit) + compute-efficient adaptation (personal data)

---

**Document Version**: MVP Blueprint v2.0  
**Date**: March 21, 2026  
**Total References**: 12 research papers/projects  
**Research Coverage**: NVIDIA (DreamDojo, DreamZero), DeepMind (Genie 3, Dreamer), World Labs, VERSES AI, Rhoda AI, Seoul World Model, UI-Simulator, Stable-WorldModel (LeCun & Balestriero)

**Claude Implementation Note**: 
- **Every code comment** should reference which research finding it implements
- **Every architectural decision** should cite the source
- **Every prompt** should ground in the research insights
- Use these URLs when explaining design choices in code reviews

🚀 **Ready to build — with full research backing!**