from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.domain.alerts.engine import AlertEngine, AlertRule, MarketEvent, OutcomeCode, RuleTemplate


NOW = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)


def event(event_id: str, **changes: object) -> MarketEvent:
    values: dict[str, object] = {
        "event_id": event_id, "instrument_id": "NVDA", "underlying": "NVDA", "asset_type": "stock",
        "event_type": "execution", "event_time": NOW, "quantity": Decimal("10000"), "price": Decimal("100"),
        "identity_reliable": True,
    }
    values.update(changes)
    return MarketEvent(**values)  # type: ignore[arg-type]


def rule(template: RuleTemplate, **changes: object) -> AlertRule:
    values: dict[str, object] = {
        "rule_id": f"rule-{template}", "template": template, "asset_type": "stock", "universe": frozenset({"NVDA"}),
        "minimum_quantity": Decimal("10000"), "minimum_notional": Decimal("1000000"),
    }
    values.update(changes)
    return AlertRule(**values)  # type: ignore[arg-type]


def test_a01_inclusive_threshold_and_execution_gate() -> None:
    engine = AlertEngine()
    assert engine.evaluate(rule(RuleTemplate.A01), event("one")).code is OutcomeCode.TRIGGERED
    assert engine.evaluate(rule(RuleTemplate.A01), event("quote", event_type="quote")).code is OutcomeCode.NOT_EXECUTION


def test_a02_uses_verified_multiplier_and_exact_decimal_premium() -> None:
    engine = AlertEngine()
    option_rule = rule(RuleTemplate.A02, asset_type="option", universe=frozenset({"NVDA-C"}), minimum_quantity=Decimal("100"), minimum_notional=Decimal("100000"))
    qualifying = event("option-one", asset_type="option", instrument_id="NVDA-C", quantity=Decimal("250"), price=Decimal("5.20"), price_multiplier=Decimal("100"), multiplier_verified=True)
    outcome = engine.evaluate(option_rule, qualifying)
    assert outcome.notional == Decimal("130000")
    assert outcome.code is OutcomeCode.TRIGGERED
    unknown = event("option-two", asset_type="option", instrument_id="NVDA-C", quantity=Decimal("250"), price=Decimal("5.20"))
    assert engine.evaluate(option_rule, unknown).code is OutcomeCode.UNKNOWN_MULTIPLIER


def test_reliable_duplicate_is_suppressed_but_distinct_identical_prints_are_preserved() -> None:
    engine = AlertEngine()
    current = rule(RuleTemplate.A01)
    assert engine.evaluate(current, event("provider-1")).code is OutcomeCode.TRIGGERED
    assert engine.evaluate(current, event("provider-1")).code is OutcomeCode.DUPLICATE
    assert engine.evaluate(current, event("same-economics", identity_reliable=False)).code is OutcomeCode.COOLDOWN


def test_a03_requires_reliable_identity_and_counts_distinct_events_in_window() -> None:
    engine = AlertEngine()
    repeated = rule(RuleTemplate.A03, minimum_notional=Decimal("3000000"), qualifying_minimum_notional=Decimal("1000000"))
    assert engine.evaluate(repeated, event("unreliable", identity_reliable=False)).code is OutcomeCode.IDENTITY_AMBIGUOUS
    for number in range(2):
        result = engine.evaluate(repeated, event(f"repeat-{number}", event_time=NOW + timedelta(seconds=number)))
        assert result.code is OutcomeCode.BELOW_THRESHOLD
    result = engine.evaluate(repeated, event("repeat-2", event_time=NOW + timedelta(seconds=2)))
    assert result.code is OutcomeCode.TRIGGERED
    assert result.event_count == 3


def test_cooldown_allows_only_strictly_larger_than_escalation_multiple() -> None:
    engine = AlertEngine()
    current = rule(RuleTemplate.A01)
    assert engine.evaluate(current, event("base")).code is OutcomeCode.TRIGGERED
    equal_escalation = event("equal", event_time=NOW + timedelta(seconds=1), quantity=Decimal("20000"), price=Decimal("100"))
    assert engine.evaluate(current, equal_escalation).code is OutcomeCode.COOLDOWN
    larger = event("larger", event_time=NOW + timedelta(seconds=2), quantity=Decimal("20001"), price=Decimal("100"))
    assert engine.evaluate(current, larger).code is OutcomeCode.TRIGGERED


def test_a04_is_held_underlying_enrichment_and_never_a_second_alert() -> None:
    engine = AlertEngine()
    held = rule(RuleTemplate.A04, held_underlyings=frozenset({"NVDA"}))
    outcome = engine.evaluate(held, event("held"))
    assert outcome.code is OutcomeCode.ENRICHED
    assert outcome.held_underlying and outcome.enrichment_only
    assert engine.evaluate(held, event("unheld", underlying="AMD")).code is OutcomeCode.NOT_HELD_UNDERLYING


def test_invalid_domain_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        event("bad-time", event_time=datetime(2026, 9, 14))
    with pytest.raises(ValueError, match="positive"):
        event("bad-price", price=Decimal("0"))
