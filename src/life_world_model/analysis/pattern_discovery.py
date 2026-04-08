from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import date
from statistics import mean

from life_world_model.types import LifeState, Pattern


def compare_patterns(
    old_patterns: list[Pattern], new_patterns: list[Pattern]
) -> list[Pattern]:
    """Return patterns in new_patterns that are not in old_patterns (by name)."""
    old_names = {p.name for p in old_patterns}
    return [p for p in new_patterns if p.name not in old_names]


def decay_pattern_confidence(
    patterns: list[Pattern],
    reference_date: date,
    half_life: float = 14.0,
) -> list[Pattern]:
    """Apply temporal decay to pattern confidence based on last_seen date.

    Formula: decayed_confidence = confidence * e^(-0.693 * days_since / half_life)
    Patterns below 0.1 confidence after decay are marked stale (category -> "stale").
    """
    result: list[Pattern] = []
    for p in patterns:
        if p.last_seen is None:
            result.append(p)
            continue

        days_since = (reference_date - p.last_seen).days
        if days_since < 0:
            # Pattern last seen in the future relative to reference — no decay
            result.append(p)
            continue

        decay_factor = math.exp(-0.693 * days_since / half_life)
        decayed = p.confidence * decay_factor

        if decayed < 0.1:
            # Mark as stale
            result.append(
                Pattern(
                    name=p.name,
                    category="stale",
                    description=p.description,
                    evidence=p.evidence,
                    confidence=round(decayed, 4),
                    days_observed=p.days_observed,
                    first_seen=p.first_seen,
                    last_seen=p.last_seen,
                )
            )
        else:
            result.append(
                Pattern(
                    name=p.name,
                    category=p.category,
                    description=p.description,
                    evidence=p.evidence,
                    confidence=round(decayed, 4),
                    days_observed=p.days_observed,
                    first_seen=p.first_seen,
                    last_seen=p.last_seen,
                )
            )

    return result


def discover_patterns(
    multi_day_states: dict[date, list[LifeState]],
    reference_date: date | None = None,
) -> list[Pattern]:
    """Run all detectors and return discovered patterns.

    If reference_date is provided, applies confidence decay based on how recently
    each pattern was last observed.
    """
    patterns: list[Pattern] = []
    patterns.extend(detect_routines(multi_day_states))
    patterns.extend(detect_productivity_correlations(multi_day_states))
    patterns.extend(detect_circadian_rhythm(multi_day_states))
    patterns.extend(detect_context_switching_cost(multi_day_states))
    patterns.extend(detect_time_sinks(multi_day_states))

    if reference_date is not None:
        patterns = decay_pattern_confidence(patterns, reference_date)

    return patterns


def detect_routines(multi_day_states: dict[date, list[LifeState]]) -> list[Pattern]:
    """Find activities that repeat at the same hour on >60% of observed days."""
    if not multi_day_states:
        return []

    total_days = len(multi_day_states)
    if total_days == 0:
        return []

    # Count how many days each (hour, activity) pair appears
    pair_days: dict[tuple[int, str], set[date]] = defaultdict(set)
    for day, states in multi_day_states.items():
        for state in states:
            hour = state.timestamp.hour
            pair_days[(hour, state.primary_activity)].add(day)

    all_dates = sorted(multi_day_states.keys())
    patterns: list[Pattern] = []
    for (hour, activity), days_set in pair_days.items():
        count = len(days_set)
        pct = count / total_days
        if pct > 0.6:
            patterns.append(
                Pattern(
                    name=f"{activity}_at_{hour}",
                    category="routine",
                    description=(
                        f"{activity} occurs at {hour}:00 on {pct:.0%} of days "
                        f"({count}/{total_days} days observed)."
                    ),
                    evidence={
                        "hour": hour,
                        "activity": activity,
                        "frequency": round(pct, 3),
                        "days_observed": count,
                    },
                    confidence=pct,
                    days_observed=count,
                    first_seen=all_dates[0],
                    last_seen=all_dates[-1],
                )
            )
    return patterns


def detect_productivity_correlations(
    multi_day_states: dict[date, list[LifeState]],
) -> list[Pattern]:
    """Find activities that frequently precede productive or scattered buckets."""
    if not multi_day_states:
        return []

    # Build transition counts from consecutive bucket pairs
    transition_counts: Counter[tuple[str, str]] = Counter()
    for states in multi_day_states.values():
        for i in range(len(states) - 1):
            a = states[i].primary_activity
            b = states[i + 1].primary_activity
            transition_counts[(a, b)] += 1

    if not transition_counts:
        return []

    # Count outgoing transitions per activity
    outgoing_totals: Counter[str] = Counter()
    for (a, _b), count in transition_counts.items():
        outgoing_totals[a] += count

    all_dates = sorted(multi_day_states.keys())
    patterns: list[Pattern] = []

    # Positive correlates: activities that precede "coding" or high session_depth
    # Also check transitions to high session_depth buckets
    high_depth_transitions: Counter[str] = Counter()
    high_switch_transitions: Counter[str] = Counter()
    for states in multi_day_states.values():
        for i in range(len(states) - 1):
            a = states[i].primary_activity
            b_state = states[i + 1]
            if b_state.session_depth is not None and b_state.session_depth >= 2:
                high_depth_transitions[a] += 1
            if b_state.context_switches is not None and b_state.context_switches >= 5:
                high_switch_transitions[a] += 1

    # Report standard A->B transitions with sample_size >= 5
    for (a, b), count in transition_counts.most_common():
        if count < 5:
            continue
        total = outgoing_totals[a]
        prob = count / total
        if prob >= 0.3:  # Only report meaningful correlations
            patterns.append(
                Pattern(
                    name=f"{a}_precedes_{b}",
                    category="correlation",
                    description=(
                        f"{a} precedes {b} {prob:.0%} of the time "
                        f"({count} of {total} transitions)."
                    ),
                    evidence={
                        "precursor": a,
                        "outcome": b,
                        "probability": round(prob, 3),
                        "sample_size": count,
                    },
                    confidence=prob,
                    days_observed=len(multi_day_states),
                    first_seen=all_dates[0],
                    last_seen=all_dates[-1],
                )
            )

    # Positive: activities preceding high session_depth
    for activity, count in high_depth_transitions.items():
        if count < 5:
            continue
        total = outgoing_totals[activity]
        prob = count / total
        patterns.append(
            Pattern(
                name=f"{activity}_precedes_deep_focus",
                category="correlation",
                description=(
                    f"{activity} precedes deep focus (session_depth >= 2) "
                    f"{prob:.0%} of the time ({count} instances)."
                ),
                evidence={
                    "precursor": activity,
                    "outcome": "deep_focus",
                    "probability": round(prob, 3),
                    "sample_size": count,
                },
                confidence=prob,
                days_observed=len(multi_day_states),
                first_seen=all_dates[0],
                last_seen=all_dates[-1],
            )
        )

    # Negative: activities preceding high context switches
    for activity, count in high_switch_transitions.items():
        if count < 5:
            continue
        total = outgoing_totals[activity]
        prob = count / total
        patterns.append(
            Pattern(
                name=f"{activity}_precedes_scattered",
                category="correlation",
                description=(
                    f"{activity} precedes scattered buckets (context_switches >= 5) "
                    f"{prob:.0%} of the time ({count} instances)."
                ),
                evidence={
                    "precursor": activity,
                    "outcome": "scattered",
                    "probability": round(prob, 3),
                    "sample_size": count,
                },
                confidence=prob,
                days_observed=len(multi_day_states),
                first_seen=all_dates[0],
                last_seen=all_dates[-1],
            )
        )

    return patterns


def detect_circadian_rhythm(
    multi_day_states: dict[date, list[LifeState]],
) -> list[Pattern]:
    """Find peak focus hours and scattered hours based on averages."""
    if not multi_day_states:
        return []

    # Collect per-hour values
    switches_by_hour: dict[int, list[int]] = defaultdict(list)
    dwell_by_hour: dict[int, list[float]] = defaultdict(list)

    for states in multi_day_states.values():
        for state in states:
            hour = state.timestamp.hour
            if state.context_switches is not None:
                switches_by_hour[hour].append(state.context_switches)
            if state.dwell_seconds is not None:
                dwell_by_hour[hour].append(state.dwell_seconds)

    if not switches_by_hour and not dwell_by_hour:
        return []

    avg_switches: dict[int, float] = {
        h: mean(vals) for h, vals in switches_by_hour.items() if vals
    }
    avg_dwell: dict[int, float] = {
        h: mean(vals) for h, vals in dwell_by_hour.items() if vals
    }

    # Hours present in both metrics
    common_hours = set(avg_switches.keys()) & set(avg_dwell.keys())
    if not common_hours:
        # Fall back to whichever metric we have
        if avg_switches:
            sorted_hours = sorted(avg_switches.keys(), key=lambda h: avg_switches[h])
            peak_hours = sorted_hours[:3]
            scattered_hours = sorted_hours[-3:]
        elif avg_dwell:
            sorted_hours = sorted(avg_dwell.keys(), key=lambda h: -avg_dwell[h])
            peak_hours = sorted_hours[:3]
            scattered_hours = sorted_hours[-3:]
        else:
            return []
    else:
        # Rank hours: peak = low switches + high dwell
        # Use normalized scoring: lower switch rank + higher dwell rank = better
        switch_sorted = sorted(common_hours, key=lambda h: avg_switches[h])
        dwell_sorted = sorted(common_hours, key=lambda h: -avg_dwell[h])

        switch_rank = {h: i for i, h in enumerate(switch_sorted)}
        dwell_rank = {h: i for i, h in enumerate(dwell_sorted)}

        combined_rank = {h: switch_rank[h] + dwell_rank[h] for h in common_hours}
        ranked_hours = sorted(common_hours, key=lambda h: combined_rank[h])

        peak_hours = ranked_hours[:3]
        scattered_hours = ranked_hours[-3:]

    all_dates = sorted(multi_day_states.keys())
    return [
        Pattern(
            name="circadian_rhythm",
            category="rhythm",
            description=(
                f"Peak focus hours: {peak_hours}. "
                f"Most scattered hours: {scattered_hours}."
            ),
            evidence={
                "peak_hours": peak_hours,
                "scattered_hours": scattered_hours,
                "avg_switches_by_hour": {
                    str(h): round(v, 2) for h, v in sorted(avg_switches.items())
                },
                "avg_dwell_by_hour": {
                    str(h): round(v, 2) for h, v in sorted(avg_dwell.items())
                },
            },
            confidence=0.7,
            days_observed=len(multi_day_states),
            first_seen=all_dates[0],
            last_seen=all_dates[-1],
        )
    ]


def detect_context_switching_cost(
    multi_day_states: dict[date, list[LifeState]],
) -> list[Pattern]:
    """Measure how many buckets it takes to recover deep focus after high switching."""
    if not multi_day_states:
        return []

    recovery_times: list[int] = []

    for states in multi_day_states.values():
        for i, state in enumerate(states):
            if state.context_switches is not None and state.context_switches > 5:
                # Count buckets until next session_depth >= 2
                for j in range(i + 1, len(states)):
                    if (
                        states[j].session_depth is not None
                        and states[j].session_depth >= 2
                    ):
                        recovery_times.append(j - i)
                        break

    if len(recovery_times) < 3:
        return []

    avg_recovery = mean(recovery_times)
    all_dates = sorted(multi_day_states.keys())
    return [
        Pattern(
            name="context_switching_recovery",
            category="trigger",
            description=(
                f"After high context switching (>5), it takes an average of "
                f"{avg_recovery:.1f} buckets ({avg_recovery * 15:.0f} minutes) "
                f"to regain deep focus (sample: {len(recovery_times)} instances)."
            ),
            evidence={
                "avg_recovery_buckets": round(avg_recovery, 2),
                "avg_recovery_minutes": round(avg_recovery * 15, 1),
                "sample_size": len(recovery_times),
            },
            confidence=min(0.9, len(recovery_times) / 20),
            days_observed=len(multi_day_states),
            first_seen=all_dates[0],
            last_seen=all_dates[-1],
        )
    ]


def detect_time_sinks(
    multi_day_states: dict[date, list[LifeState]],
) -> list[Pattern]:
    """Flag activities with high total hours but low dwell and high switching."""
    if not multi_day_states:
        return []

    # Group by primary_activity (or domain for browsing)
    activity_stats: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "dwell_values": [], "switch_values": []}
    )

    for states in multi_day_states.values():
        for state in states:
            # Use domain as key for browsing activity, otherwise primary_activity
            if state.primary_activity == "browsing" and state.domain:
                key = f"browsing:{state.domain}"
            else:
                key = state.primary_activity

            activity_stats[key]["count"] += 1
            if state.dwell_seconds is not None:
                activity_stats[key]["dwell_values"].append(state.dwell_seconds)
            if state.context_switches is not None:
                activity_stats[key]["switch_values"].append(state.context_switches)

    if not activity_stats:
        return []

    # Calculate scores
    scored: list[tuple[str, float, float, float, float]] = []
    for activity, stats in activity_stats.items():
        total_hours = stats["count"] * 15 / 60  # Each bucket is 15 minutes
        avg_dwell = mean(stats["dwell_values"]) if stats["dwell_values"] else 0.0
        avg_switches = mean(stats["switch_values"]) if stats["switch_values"] else 0.0
        score = total_hours * (avg_switches / max(avg_dwell, 1))
        scored.append((activity, total_hours, avg_dwell, avg_switches, score))

    # Top 3 by score
    scored.sort(key=lambda x: -x[4])
    top_sinks = scored[:3]

    all_dates = sorted(multi_day_states.keys())
    patterns: list[Pattern] = []
    for activity, total_hours, avg_dwell, avg_switches, score in top_sinks:
        if score <= 0:
            continue
        patterns.append(
            Pattern(
                name=f"time_sink_{activity}",
                category="time_sink",
                description=(
                    f"{activity}: {total_hours:.1f}h total, "
                    f"avg dwell {avg_dwell:.0f}s, avg switches {avg_switches:.1f}. "
                    f"Sink score: {score:.2f}."
                ),
                evidence={
                    "activity": activity,
                    "total_hours": round(total_hours, 2),
                    "avg_dwell": round(avg_dwell, 2),
                    "avg_switches": round(avg_switches, 2),
                    "score": round(score, 4),
                },
                confidence=min(0.8, score / 10),
                days_observed=len(multi_day_states),
                first_seen=all_dates[0],
                last_seen=all_dates[-1],
            )
        )

    return patterns
