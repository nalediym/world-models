from __future__ import annotations

from life_world_model.types import Goal, LifeState

# Default goals derived from user interview:
# alignment=0.4, energy=0.3, flow=0.3
DEFAULT_GOALS: list[Goal] = [
    Goal(
        name="goal_alignment",
        description="Time on productive activities (coding, research, creating)",
        metric="productive_focus_ratio",
        weight=0.4,
    ),
    Goal(
        name="energy",
        description="Sustainable work patterns with breaks between focus blocks",
        metric="recovery_ratio",
        weight=0.3,
    ),
    Goal(
        name="flow",
        description="Low context-switching, long uninterrupted sessions",
        metric="flow_score",
        weight=0.3,
    ),
]

PRODUCTIVE_ACTIVITIES = {"coding", "research", "ai_tooling"}


def load_goals() -> list[Goal]:
    """Load goals. Returns DEFAULT_GOALS for now, extensible to storage later."""
    return list(DEFAULT_GOALS)


def compute_metric(states: list[LifeState], metric: str) -> float:
    """Compute a single metric value (0.0-1.0) from a day's LifeStates."""
    if not states:
        return 0.0
    if metric == "productive_focus_ratio":
        # Ratio of buckets in productive activities to total buckets
        productive = sum(
            1 for s in states if s.primary_activity in PRODUCTIVE_ACTIVITIES
        )
        return productive / len(states)
    elif metric == "recovery_ratio":
        # Ratio of idle/break buckets to total. Ideal is ~20% (1 break per 4 focus blocks)
        # Score peaks at 0.2 ratio, drops toward 0 (no breaks) and 1 (all breaks)
        idle = sum(1 for s in states if s.primary_activity == "idle")
        ratio = idle / len(states)
        # Bell curve around 0.2: score = 1 - abs(ratio - 0.2) * 3, clamped to [0, 1]
        return max(0.0, min(1.0, 1.0 - abs(ratio - 0.2) * 3))
    elif metric == "flow_score":
        # Inverse of context-switch rate, normalized
        switches = [
            s.context_switches for s in states if s.context_switches is not None
        ]
        if not switches:
            return 0.5  # unknown
        avg_switches = sum(switches) / len(switches)
        # 0 switches = 1.0, 10+ switches = 0.0
        return max(0.0, min(1.0, 1.0 - avg_switches / 10.0))
    else:
        return 0.0
