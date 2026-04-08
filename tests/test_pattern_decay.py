from __future__ import annotations

import math
from datetime import date

from life_world_model.analysis.pattern_discovery import (
    decay_pattern_confidence,
    discover_patterns,
)
from life_world_model.types import Pattern


def _make_pattern(
    name: str = "test_pattern",
    category: str = "routine",
    confidence: float = 0.8,
    last_seen: date | None = None,
    first_seen: date | None = None,
) -> Pattern:
    if last_seen is None:
        last_seen = date(2026, 4, 1)
    if first_seen is None:
        first_seen = date(2026, 3, 15)
    return Pattern(
        name=name,
        category=category,
        description=f"Test pattern {name}",
        evidence={"test": True},
        confidence=confidence,
        days_observed=7,
        first_seen=first_seen,
        last_seen=last_seen,
    )


class TestDecayFormula:
    def test_no_decay_at_same_date(self) -> None:
        """Pattern observed today should retain full confidence."""
        ref = date(2026, 4, 1)
        patterns = [_make_pattern(confidence=0.8, last_seen=ref)]
        result = decay_pattern_confidence(patterns, ref)
        assert len(result) == 1
        assert result[0].confidence == 0.8

    def test_half_confidence_at_half_life(self) -> None:
        """Confidence should halve after one half-life (14 days)."""
        last_seen = date(2026, 3, 18)
        ref = date(2026, 4, 1)  # 14 days later
        patterns = [_make_pattern(confidence=1.0, last_seen=last_seen)]
        result = decay_pattern_confidence(patterns, ref, half_life=14.0)
        assert len(result) == 1
        assert abs(result[0].confidence - 0.5) < 0.01

    def test_quarter_confidence_at_two_half_lives(self) -> None:
        """Confidence should be ~0.25 after two half-lives (28 days)."""
        last_seen = date(2026, 3, 4)
        ref = date(2026, 4, 1)  # 28 days later
        patterns = [_make_pattern(confidence=1.0, last_seen=last_seen)]
        result = decay_pattern_confidence(patterns, ref, half_life=14.0)
        assert len(result) == 1
        assert abs(result[0].confidence - 0.25) < 0.02

    def test_custom_half_life(self) -> None:
        """Custom half-life of 7 days: confidence halves in 7 days."""
        last_seen = date(2026, 3, 25)
        ref = date(2026, 4, 1)  # 7 days later
        patterns = [_make_pattern(confidence=1.0, last_seen=last_seen)]
        result = decay_pattern_confidence(patterns, ref, half_life=7.0)
        assert len(result) == 1
        assert abs(result[0].confidence - 0.5) < 0.01

    def test_exact_decay_formula(self) -> None:
        """Verify the exact formula: decayed = confidence * e^(-0.693 * days / half_life)."""
        last_seen = date(2026, 3, 22)
        ref = date(2026, 4, 1)  # 10 days
        original_confidence = 0.7
        expected = original_confidence * math.exp(-0.693 * 10 / 14.0)
        patterns = [_make_pattern(confidence=original_confidence, last_seen=last_seen)]
        result = decay_pattern_confidence(patterns, ref)
        assert abs(result[0].confidence - round(expected, 4)) < 0.001


class TestStaleMarking:
    def test_stale_below_threshold(self) -> None:
        """Patterns decaying below 0.1 should be marked stale."""
        # With confidence 0.2, after ~1.5 half-lives (21 days), should drop below 0.1
        # 0.2 * e^(-0.693 * 28 / 14) = 0.2 * 0.25 = 0.05
        last_seen = date(2026, 3, 4)
        ref = date(2026, 4, 1)  # 28 days
        patterns = [_make_pattern(confidence=0.2, last_seen=last_seen)]
        result = decay_pattern_confidence(patterns, ref)
        assert result[0].category == "stale"
        assert result[0].confidence < 0.1

    def test_not_stale_above_threshold(self) -> None:
        """Patterns above 0.1 after decay should keep their original category."""
        last_seen = date(2026, 3, 25)
        ref = date(2026, 4, 1)  # 7 days
        patterns = [_make_pattern(confidence=0.8, category="routine", last_seen=last_seen)]
        result = decay_pattern_confidence(patterns, ref)
        assert result[0].category == "routine"
        assert result[0].confidence >= 0.1

    def test_stale_preserves_name_and_evidence(self) -> None:
        """Stale patterns should retain their name and evidence for reference."""
        last_seen = date(2026, 2, 1)
        ref = date(2026, 4, 1)  # 59 days
        patterns = [_make_pattern(
            name="coding_at_9",
            confidence=0.3,
            last_seen=last_seen,
        )]
        result = decay_pattern_confidence(patterns, ref)
        assert result[0].name == "coding_at_9"
        assert result[0].evidence == {"test": True}
        assert result[0].category == "stale"


class TestDecayEdgeCases:
    def test_empty_patterns(self) -> None:
        """Empty list returns empty list."""
        result = decay_pattern_confidence([], date(2026, 4, 1))
        assert result == []

    def test_none_last_seen(self) -> None:
        """Patterns with no last_seen should pass through unchanged."""
        p = _make_pattern(confidence=0.7)
        p = Pattern(
            name=p.name,
            category=p.category,
            description=p.description,
            evidence=p.evidence,
            confidence=p.confidence,
            days_observed=p.days_observed,
            first_seen=p.first_seen,
            last_seen=None,
        )
        result = decay_pattern_confidence([p], date(2026, 4, 1))
        assert result[0].confidence == 0.7

    def test_future_last_seen(self) -> None:
        """Pattern last_seen in the future relative to reference has no decay."""
        last_seen = date(2026, 4, 10)
        ref = date(2026, 4, 1)
        patterns = [_make_pattern(confidence=0.8, last_seen=last_seen)]
        result = decay_pattern_confidence(patterns, ref)
        assert result[0].confidence == 0.8

    def test_multiple_patterns_mixed(self) -> None:
        """Multiple patterns with different ages get different decay amounts."""
        ref = date(2026, 4, 1)
        patterns = [
            _make_pattern(name="recent", confidence=0.8, last_seen=date(2026, 3, 31)),
            _make_pattern(name="old", confidence=0.8, last_seen=date(2026, 2, 15)),
        ]
        result = decay_pattern_confidence(patterns, ref)
        assert result[0].confidence > result[1].confidence
        assert result[0].category != "stale"  # recent should not be stale


class TestDiscoverPatternsWithDecay:
    def test_discover_without_reference_date(self) -> None:
        """discover_patterns without reference_date should not apply decay."""
        from datetime import datetime
        from life_world_model.types import LifeState

        days = [date(2026, 4, d) for d in range(1, 6)]
        multi_day: dict[date, list[LifeState]] = {}
        for day in days:
            multi_day[day] = [
                LifeState(
                    timestamp=datetime(day.year, day.month, day.day, 9, 0),
                    primary_activity="research",
                    secondary_activity=None,
                    domain=None,
                    event_count=5,
                    confidence=0.8,
                    sources=["chrome"],
                )
            ]
        patterns = discover_patterns(multi_day)
        # Should work the same as before
        assert any(p.name == "research_at_9" for p in patterns)

    def test_discover_with_reference_date_applies_decay(self) -> None:
        """discover_patterns with reference_date should decay confidence."""
        from datetime import datetime
        from life_world_model.types import LifeState

        # Data from 30 days ago — patterns will have last_seen from that period
        days = [date(2026, 3, d) for d in range(1, 6)]
        multi_day: dict[date, list[LifeState]] = {}
        for day in days:
            multi_day[day] = [
                LifeState(
                    timestamp=datetime(day.year, day.month, day.day, 9, 0),
                    primary_activity="research",
                    secondary_activity=None,
                    domain=None,
                    event_count=5,
                    confidence=0.8,
                    sources=["chrome"],
                )
            ]

        ref = date(2026, 4, 7)  # ~33 days after last_seen of date(2026, 3, 5)
        patterns = discover_patterns(multi_day, reference_date=ref)

        # Patterns should have decayed confidence
        for p in patterns:
            if p.name == "research_at_9":
                # Original confidence would be 1.0 (5/5 days), decayed by ~33 days
                assert p.confidence < 1.0
                break
