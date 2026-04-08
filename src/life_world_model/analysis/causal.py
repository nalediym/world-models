"""Causal transition graph built from historical LifeState data.

Captures activity-to-activity transition probabilities, time-of-day effects,
and activity impact on downstream metrics. Used by Monte Carlo simulation
to propagate ripple effects of interventions.
"""

from __future__ import annotations

import copy
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from statistics import mean, stdev

from life_world_model.types import LifeState


@dataclass
class TransitionEdge:
    from_activity: str
    to_activity: str
    probability: float  # P(to | from)
    sample_count: int  # how many times observed
    avg_delay_minutes: float  # average time between activities


@dataclass
class CausalGraph:
    edges: list[TransitionEdge]
    activity_effects: dict[str, dict[str, float]]  # activity -> {metric: effect_size}
    # Time-of-day activity distributions: hour -> {activity: probability}
    hourly_priors: dict[int, dict[str, float]] = field(default_factory=dict)
    # Per-activity metric variance: activity -> {metric: stdev}
    activity_variance: dict[str, dict[str, float]] = field(default_factory=dict)
    # Recovery cost: average buckets after high context_switches before focus returns
    recovery_cost_buckets: float = 0.0


def build_causal_graph(multi_day_states: dict[date, list[LifeState]]) -> CausalGraph:
    """Build transition probabilities from historical LifeState data.

    For each consecutive pair of buckets, record:
    - P(activity_B follows activity_A)
    - Average gap between activities
    - Effect on subsequent metrics (context switches, session depth)
    """
    if not multi_day_states:
        return CausalGraph(
            edges=[],
            activity_effects={},
            hourly_priors={},
            activity_variance={},
            recovery_cost_buckets=0.0,
        )

    # --- Transition counting ---
    transition_counts: Counter[tuple[str, str]] = Counter()
    transition_delays: dict[tuple[str, str], list[float]] = defaultdict(list)
    outgoing_totals: Counter[str] = Counter()

    for states in multi_day_states.values():
        for i in range(len(states) - 1):
            a = states[i].primary_activity
            b = states[i + 1].primary_activity
            transition_counts[(a, b)] += 1
            outgoing_totals[a] += 1

            # Delay in minutes between bucket timestamps
            delta = (states[i + 1].timestamp - states[i].timestamp).total_seconds() / 60.0
            transition_delays[(a, b)].append(delta)

    # Build edges with conditional probabilities
    edges: list[TransitionEdge] = []
    for (a, b), count in transition_counts.items():
        total = outgoing_totals[a]
        prob = count / total if total > 0 else 0.0
        delays = transition_delays[(a, b)]
        avg_delay = mean(delays) if delays else 0.0

        edges.append(TransitionEdge(
            from_activity=a,
            to_activity=b,
            probability=round(prob, 4),
            sample_count=count,
            avg_delay_minutes=round(avg_delay, 1),
        ))

    # --- Activity effects on downstream metrics ---
    # For each activity, measure the average context_switches and session_depth
    # of the NEXT bucket
    activity_next_switches: dict[str, list[float]] = defaultdict(list)
    activity_next_depth: dict[str, list[float]] = defaultdict(list)

    for states in multi_day_states.values():
        for i in range(len(states) - 1):
            a = states[i].primary_activity
            next_s = states[i + 1]
            if next_s.context_switches is not None:
                activity_next_switches[a].append(float(next_s.context_switches))
            if next_s.session_depth is not None:
                activity_next_depth[a].append(float(next_s.session_depth))

    # Compute effect size as deviation from global mean
    all_switches = [
        v for vals in activity_next_switches.values() for v in vals
    ]
    all_depths = [
        v for vals in activity_next_depth.values() for v in vals
    ]
    global_avg_switches = mean(all_switches) if all_switches else 0.0
    global_avg_depth = mean(all_depths) if all_depths else 0.0

    activity_effects: dict[str, dict[str, float]] = {}
    all_activities = set(activity_next_switches.keys()) | set(activity_next_depth.keys())

    for activity in all_activities:
        effects: dict[str, float] = {}
        if activity in activity_next_switches and activity_next_switches[activity]:
            local_avg = mean(activity_next_switches[activity])
            effects["context_switches"] = round(local_avg - global_avg_switches, 3)
        if activity in activity_next_depth and activity_next_depth[activity]:
            local_avg = mean(activity_next_depth[activity])
            effects["session_depth"] = round(local_avg - global_avg_depth, 3)
        activity_effects[activity] = effects

    # --- Time-of-day priors ---
    hour_activity_counts: dict[int, Counter[str]] = defaultdict(Counter)
    for states in multi_day_states.values():
        for state in states:
            hour = state.timestamp.hour
            hour_activity_counts[hour][state.primary_activity] += 1

    hourly_priors: dict[int, dict[str, float]] = {}
    for hour, counts in hour_activity_counts.items():
        total = sum(counts.values())
        if total > 0:
            hourly_priors[hour] = {
                activity: round(count / total, 4)
                for activity, count in counts.items()
            }

    # --- Per-activity metric variance ---
    activity_switch_values: dict[str, list[float]] = defaultdict(list)
    activity_depth_values: dict[str, list[float]] = defaultdict(list)
    activity_dwell_values: dict[str, list[float]] = defaultdict(list)

    for states in multi_day_states.values():
        for state in states:
            act = state.primary_activity
            if state.context_switches is not None:
                activity_switch_values[act].append(float(state.context_switches))
            if state.session_depth is not None:
                activity_depth_values[act].append(float(state.session_depth))
            if state.dwell_seconds is not None:
                activity_dwell_values[act].append(state.dwell_seconds)

    activity_variance: dict[str, dict[str, float]] = {}
    for act in set(activity_switch_values) | set(activity_depth_values) | set(activity_dwell_values):
        var: dict[str, float] = {}
        if act in activity_switch_values and len(activity_switch_values[act]) >= 2:
            var["context_switches"] = round(stdev(activity_switch_values[act]), 3)
        if act in activity_depth_values and len(activity_depth_values[act]) >= 2:
            var["session_depth"] = round(stdev(activity_depth_values[act]), 3)
        if act in activity_dwell_values and len(activity_dwell_values[act]) >= 2:
            var["dwell_seconds"] = round(stdev(activity_dwell_values[act]), 3)
        activity_variance[act] = var

    # --- Recovery cost ---
    recovery_times: list[int] = []
    for states in multi_day_states.values():
        for i, state in enumerate(states):
            if state.context_switches is not None and state.context_switches > 5:
                for j in range(i + 1, len(states)):
                    if (
                        states[j].session_depth is not None
                        and states[j].session_depth >= 2
                    ):
                        recovery_times.append(j - i)
                        break

    recovery_cost = mean(recovery_times) if recovery_times else 0.0

    return CausalGraph(
        edges=edges,
        activity_effects=activity_effects,
        hourly_priors=hourly_priors,
        activity_variance=activity_variance,
        recovery_cost_buckets=round(recovery_cost, 2),
    )


def _get_transition_probs(graph: CausalGraph, activity: str) -> dict[str, float]:
    """Get outgoing transition probabilities for a given activity."""
    probs: dict[str, float] = {}
    for edge in graph.edges:
        if edge.from_activity == activity:
            probs[edge.to_activity] = edge.probability
    return probs


def _blend_probs(
    transition_probs: dict[str, float],
    hourly_probs: dict[str, float],
    transition_weight: float = 0.7,
) -> dict[str, float]:
    """Blend transition probabilities with time-of-day priors.

    Uses weighted average: 70% transition + 30% time-of-day.
    """
    all_activities = set(transition_probs.keys()) | set(hourly_probs.keys())
    if not all_activities:
        return {}

    blended: dict[str, float] = {}
    hourly_weight = 1.0 - transition_weight

    for act in all_activities:
        t_prob = transition_probs.get(act, 0.0)
        h_prob = hourly_probs.get(act, 0.0)
        blended[act] = t_prob * transition_weight + h_prob * hourly_weight

    # Normalize to sum to 1
    total = sum(blended.values())
    if total > 0:
        blended = {k: v / total for k, v in blended.items()}

    return blended


def _pick_activity(probs: dict[str, float], rng_value: float) -> str:
    """Pick an activity given probabilities and a random value in [0, 1).

    Uses the rng_value to select from the cumulative distribution.
    """
    if not probs:
        return "idle"

    cumulative = 0.0
    for activity, prob in sorted(probs.items()):
        cumulative += prob
        if rng_value < cumulative:
            return activity

    # Floating point edge case — return the last activity
    return sorted(probs.keys())[-1]


def propagate_intervention(
    graph: CausalGraph,
    baseline_states: list[LifeState],
    intervention_states: list[LifeState],
    rng: _RNG | None = None,
) -> list[LifeState]:
    """Use the causal graph to propagate ripple effects of an intervention.

    If the intervention changes activity at 8am from 'browsing' to 'coding',
    use transition probabilities to predict what happens at 9am, 10am, etc.
    Don't just substitute -- predict the cascade.

    Only propagates AFTER the last directly-modified bucket to avoid
    overwriting the user's explicit intervention.
    """
    if not baseline_states or not intervention_states:
        return list(intervention_states) if intervention_states else []

    result = copy.deepcopy(intervention_states)

    # Find the last bucket that was changed by the intervention
    last_changed_idx = -1
    for i in range(len(result)):
        if i < len(baseline_states) and result[i].primary_activity != baseline_states[i].primary_activity:
            last_changed_idx = i

    if last_changed_idx < 0:
        # No changes detected — nothing to propagate
        return result

    # Propagate from the bucket after the last changed one
    for i in range(last_changed_idx + 1, len(result)):
        prev_activity = result[i - 1].primary_activity
        hour = result[i].timestamp.hour

        # Get transition probabilities from the previous activity
        trans_probs = _get_transition_probs(graph, prev_activity)
        hourly_probs = graph.hourly_priors.get(hour, {})

        if not trans_probs and not hourly_probs:
            # No data — keep the baseline activity
            continue

        blended = _blend_probs(trans_probs, hourly_probs)
        if not blended:
            continue

        # Use RNG to pick (or deterministic if no rng provided)
        if rng is not None:
            rng_val = rng.random()
        else:
            # Deterministic: pick the highest probability activity
            rng_val = -1.0  # Will never trigger cumulative check
            best_act = max(blended, key=lambda k: blended[k])
            result[i].primary_activity = best_act
            continue

        result[i].primary_activity = _pick_activity(blended, rng_val)

    return result


class _RNG:
    """Minimal RNG wrapper to allow injection for testing/seeding."""

    def __init__(self, random_func):
        self._random = random_func

    def random(self) -> float:
        return self._random()
