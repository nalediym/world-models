"""Monte Carlo simulation engine.

Instead of one deterministic outcome, samples from behavioral variance
to produce a distribution of possible scores for a given intervention.
"""

from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from life_world_model.analysis.causal import (
    CausalGraph,
    _RNG,
    build_causal_graph,
    propagate_intervention,
)
from life_world_model.config import Settings
from life_world_model.goals.engine import load_goals
from life_world_model.scoring.formula import decay_weight, score_day
from life_world_model.simulation.engine import apply_intervention, parse_intervention
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import LifeState


@dataclass
class MonteCarloResult:
    intervention: str
    num_simulations: int
    mean_score: float
    median_score: float
    std_dev: float
    p5_score: float  # 5th percentile (worst case)
    p95_score: float  # 95th percentile (best case)
    confidence: float  # % of simulations that improved over baseline
    baseline_score: float
    score_distribution: list[float] = field(default_factory=list)


def _percentile(sorted_data: list[float], pct: float) -> float:
    """Compute percentile from sorted data using linear interpolation."""
    if not sorted_data:
        return 0.0
    if len(sorted_data) == 1:
        return sorted_data[0]

    # Use the nearest-rank method with interpolation
    k = (pct / 100.0) * (len(sorted_data) - 1)
    f = math.floor(k)
    c = math.ceil(k)

    if f == c:
        return sorted_data[int(k)]

    # Linear interpolation
    d0 = sorted_data[f]
    d1 = sorted_data[c]
    return d0 + (d1 - d0) * (k - f)


def _manual_stdev(values: list[float]) -> float:
    """Compute sample standard deviation without numpy/scipy."""
    if len(values) < 2:
        return 0.0
    avg = sum(values) / len(values)
    variance = sum((x - avg) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def _load_multi_day_states(
    store: SQLiteStore,
    settings: Settings,
    lookback_days: int = 30,
    reference_date: date | None = None,
) -> dict[date, list[LifeState]]:
    """Load LifeStates for multiple recent days."""
    from life_world_model.pipeline.bucketizer import build_life_states

    ref = reference_date or date.today()
    result: dict[date, list[LifeState]] = {}

    for days_ago in range(lookback_days):
        d = ref - timedelta(days=days_ago)
        events = store.load_raw_events_for_date(d)
        if events:
            states = build_life_states(events, bucket_minutes=settings.bucket_minutes)
            if states:
                result[d] = states

    return result


def _weighted_sample_day(
    multi_day_states: dict[date, list[LifeState]],
    reference_date: date,
    rng: random.Random,
    half_life: float = 14.0,
) -> tuple[date, list[LifeState]]:
    """Pick a random historical day weighted toward recent days.

    Uses temporal decay weighting: more recent days are more likely to be picked.
    """
    if not multi_day_states:
        raise ValueError("No historical days available for sampling")

    dates = sorted(multi_day_states.keys(), reverse=True)
    weights: list[float] = []

    for d in dates:
        days_ago = (reference_date - d).days
        if days_ago < 0:
            days_ago = 0
        weights.append(decay_weight(float(days_ago), half_life))

    # Weighted random selection
    total_weight = sum(weights)
    if total_weight == 0:
        # Fallback to uniform
        idx = rng.randint(0, len(dates) - 1)
    else:
        r = rng.random() * total_weight
        cumulative = 0.0
        idx = 0
        for i, w in enumerate(weights):
            cumulative += w
            if r <= cumulative:
                idx = i
                break

    chosen_date = dates[idx]
    return chosen_date, multi_day_states[chosen_date]


def _add_behavioral_noise(
    states: list[LifeState],
    graph: CausalGraph,
    rng: random.Random,
) -> list[LifeState]:
    """Add Gaussian noise to behavioral metrics based on observed variance.

    Perturbs context_switches, session_depth, and dwell_seconds within
    the observed standard deviation for each activity type.
    """
    result = copy.deepcopy(states)

    for state in result:
        activity = state.primary_activity
        variance = graph.activity_variance.get(activity, {})

        if state.context_switches is not None and "context_switches" in variance:
            sigma = variance["context_switches"]
            noise = rng.gauss(0, sigma * 0.5)  # Half-sigma noise for stability
            state.context_switches = max(0, round(state.context_switches + noise))

        if state.session_depth is not None and "session_depth" in variance:
            sigma = variance["session_depth"]
            noise = rng.gauss(0, sigma * 0.5)
            state.session_depth = max(1, round(state.session_depth + noise))

        if state.dwell_seconds is not None and "dwell_seconds" in variance:
            sigma = variance["dwell_seconds"]
            noise = rng.gauss(0, sigma * 0.3)  # Smaller noise for dwell
            state.dwell_seconds = max(0.0, state.dwell_seconds + noise)

    return result


def monte_carlo_simulate(
    store: SQLiteStore,
    settings: Settings,
    intervention_text: str,
    num_simulations: int = 100,
    baseline_date: date | None = None,
    seed: int | None = None,
) -> MonteCarloResult:
    """Run N simulations with stochastic variation.

    For each simulation:
    1. Pick a random historical day as baseline (weighted toward recent days)
    2. Apply the intervention
    3. Use the causal graph to propagate ripple effects
    4. Add noise from behavioral variance (per bucket sigma)
    5. Score the result

    Returns the distribution of outcomes.
    """
    rng = random.Random(seed)
    intervention = parse_intervention(intervention_text)
    goals = load_goals()

    ref_date = baseline_date or date.today()

    # Load historical data
    multi_day_states = _load_multi_day_states(
        store, settings, lookback_days=30, reference_date=ref_date,
    )

    if not multi_day_states:
        return MonteCarloResult(
            intervention=intervention_text,
            num_simulations=num_simulations,
            mean_score=0.0,
            median_score=0.0,
            std_dev=0.0,
            p5_score=0.0,
            p95_score=0.0,
            confidence=0.0,
            baseline_score=0.0,
            score_distribution=[],
        )

    # Build causal graph from all historical data
    graph = build_causal_graph(multi_day_states)

    # Compute average baseline score across sampled days
    baseline_scores: list[float] = []
    for d, states in multi_day_states.items():
        result = score_day(states, goals)
        baseline_scores.append(result["total"])
    avg_baseline = sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0.0

    # Run simulations
    simulated_scores: list[float] = []
    improved_count = 0

    for _ in range(num_simulations):
        # 1. Pick a random historical day
        chosen_date, baseline_states = _weighted_sample_day(
            multi_day_states, ref_date, rng,
        )

        # Score this particular baseline
        baseline_result = score_day(baseline_states, goals)
        this_baseline_score = baseline_result["total"]

        # 2. Apply the intervention
        intervened_states = apply_intervention(baseline_states, intervention)

        # 3. Use causal graph to propagate ripple effects
        causal_rng = _RNG(rng.random)
        propagated_states = propagate_intervention(
            graph, baseline_states, intervened_states, rng=causal_rng,
        )

        # 4. Add behavioral noise
        noisy_states = _add_behavioral_noise(propagated_states, graph, rng)

        # 5. Score
        sim_result = score_day(noisy_states, goals)
        sim_score = sim_result["total"]
        simulated_scores.append(sim_score)

        if sim_score > this_baseline_score:
            improved_count += 1

    # Compute statistics
    sorted_scores = sorted(simulated_scores)
    n = len(sorted_scores)

    mean_score = sum(sorted_scores) / n if n > 0 else 0.0
    median_score = _percentile(sorted_scores, 50.0)
    std = _manual_stdev(sorted_scores)
    p5 = _percentile(sorted_scores, 5.0)
    p95 = _percentile(sorted_scores, 95.0)
    confidence = improved_count / num_simulations if num_simulations > 0 else 0.0

    return MonteCarloResult(
        intervention=intervention_text,
        num_simulations=num_simulations,
        mean_score=round(mean_score, 4),
        median_score=round(median_score, 4),
        std_dev=round(std, 4),
        p5_score=round(p5, 4),
        p95_score=round(p95, 4),
        confidence=round(confidence, 4),
        baseline_score=round(avg_baseline, 4),
        score_distribution=sorted_scores,
    )


def monte_carlo_simulate_from_data(
    multi_day_states: dict[date, list[LifeState]],
    intervention_text: str,
    num_simulations: int = 100,
    baseline_date: date | None = None,
    seed: int | None = None,
) -> MonteCarloResult:
    """Run Monte Carlo simulation directly from pre-loaded LifeState data.

    Convenience function that skips the store/settings loading. Useful for
    testing and when data is already in memory.
    """
    rng = random.Random(seed)
    intervention = parse_intervention(intervention_text)
    goals = load_goals()

    ref_date = baseline_date or (max(multi_day_states.keys()) if multi_day_states else date.today())

    if not multi_day_states:
        return MonteCarloResult(
            intervention=intervention_text,
            num_simulations=num_simulations,
            mean_score=0.0,
            median_score=0.0,
            std_dev=0.0,
            p5_score=0.0,
            p95_score=0.0,
            confidence=0.0,
            baseline_score=0.0,
            score_distribution=[],
        )

    graph = build_causal_graph(multi_day_states)

    baseline_scores: list[float] = []
    for d, states in multi_day_states.items():
        result = score_day(states, goals)
        baseline_scores.append(result["total"])
    avg_baseline = sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0.0

    simulated_scores: list[float] = []
    improved_count = 0

    for _ in range(num_simulations):
        chosen_date, baseline_states = _weighted_sample_day(
            multi_day_states, ref_date, rng,
        )

        baseline_result = score_day(baseline_states, goals)
        this_baseline_score = baseline_result["total"]

        intervened_states = apply_intervention(baseline_states, intervention)
        causal_rng = _RNG(rng.random)
        propagated_states = propagate_intervention(
            graph, baseline_states, intervened_states, rng=causal_rng,
        )
        noisy_states = _add_behavioral_noise(propagated_states, graph, rng)

        sim_result = score_day(noisy_states, goals)
        sim_score = sim_result["total"]
        simulated_scores.append(sim_score)

        if sim_score > this_baseline_score:
            improved_count += 1

    sorted_scores = sorted(simulated_scores)
    n = len(sorted_scores)

    mean_score = sum(sorted_scores) / n if n > 0 else 0.0
    median_score = _percentile(sorted_scores, 50.0)
    std = _manual_stdev(sorted_scores)
    p5 = _percentile(sorted_scores, 5.0)
    p95 = _percentile(sorted_scores, 95.0)
    confidence = improved_count / num_simulations if num_simulations > 0 else 0.0

    return MonteCarloResult(
        intervention=intervention_text,
        num_simulations=num_simulations,
        mean_score=round(mean_score, 4),
        median_score=round(median_score, 4),
        std_dev=round(std, 4),
        p5_score=round(p5, 4),
        p95_score=round(p95, 4),
        confidence=round(confidence, 4),
        baseline_score=round(avg_baseline, 4),
        score_distribution=sorted_scores,
    )


def format_monte_carlo_report(result: MonteCarloResult) -> str:
    """Format the Monte Carlo result for terminal display."""
    lines: list[str] = []

    lines.append(f"\u2501\u2501\u2501 MONTE CARLO SIMULATION ({result.num_simulations} runs) \u2501\u2501\u2501")
    lines.append(f'Intervention: "{result.intervention}"')
    lines.append(f"Baseline: {result.baseline_score:.1%}")
    lines.append("")
    lines.append("Distribution:")
    lines.append(f"  Worst case (5th pctl):  {result.p5_score:.1%}")
    lines.append(f"  Median:                 {result.median_score:.1%}")
    lines.append(f"  Mean:                   {result.mean_score:.1%}")
    lines.append(f"  Best case (95th pctl):  {result.p95_score:.1%}")
    lines.append(f"  Std dev:                \u00b1{result.std_dev:.1%}")
    lines.append("")
    lines.append(
        f"Confidence: {result.confidence:.0%} of simulations improved over baseline"
    )

    # ASCII histogram
    if result.score_distribution:
        lines.append("")
        lines.append(_ascii_histogram(result.score_distribution))

    return "\n".join(lines)


def _ascii_histogram(scores: list[float], num_bins: int = 10, width: int = 30) -> str:
    """Generate an ASCII histogram of score distribution."""
    if not scores:
        return ""

    min_score = min(scores)
    max_score = max(scores)

    # Handle edge case where all scores are the same
    if max_score == min_score:
        return f"  [{min_score:.1%}] {'█' * width} ({len(scores)})"

    bin_width = (max_score - min_score) / num_bins
    bins: list[int] = [0] * num_bins

    for s in scores:
        idx = min(int((s - min_score) / bin_width), num_bins - 1)
        bins[idx] += 1

    max_count = max(bins) if bins else 1
    lines: list[str] = []

    for i, count in enumerate(bins):
        low = min_score + i * bin_width
        bar_len = round(count / max_count * width) if max_count > 0 else 0
        bar = "\u2588" * bar_len + "\u2591" * (width - bar_len)
        lines.append(f"  {low:5.1%} |{bar}| {count}")

    return "\n".join(lines)
