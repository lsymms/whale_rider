"""Pure A01-A04 rule evaluation; no provider, storage, or delivery dependencies."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum


class RuleTemplate(StrEnum):
    A01 = "A01"  # Large stock execution
    A02 = "A02"  # Large option premium
    A03 = "A03"  # Repeated qualifying executions
    A04 = "A04"  # Held-underlying enrichment


class OutcomeCode(StrEnum):
    TRIGGERED = "triggered"
    ENRICHED = "enriched"
    NOT_EXECUTION = "not_execution"
    WRONG_ASSET = "wrong_asset"
    OUTSIDE_UNIVERSE = "outside_universe"
    BELOW_THRESHOLD = "below_threshold"
    UNKNOWN_MULTIPLIER = "unknown_multiplier"
    DUPLICATE = "duplicate"
    COOLDOWN = "cooldown"
    IDENTITY_AMBIGUOUS = "identity_ambiguous"
    NOT_HELD_UNDERLYING = "not_held_underlying"


ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class MarketEvent:
    """A normalized execution or quote. Decimal fields are never floats."""

    event_id: str
    instrument_id: str
    underlying: str
    asset_type: str
    event_type: str
    event_time: datetime
    quantity: Decimal
    price: Decimal
    session: str = "regular"
    price_multiplier: Decimal | None = None
    multiplier_verified: bool = False
    identity_reliable: bool = False

    def __post_init__(self) -> None:
        if not self.event_id or not self.instrument_id or not self.underlying:
            raise ValueError("event identity, instrument, and underlying are required")
        if self.asset_type not in {"stock", "option"}:
            raise ValueError("asset_type must be stock or option")
        if self.event_type not in {"execution", "quote"}:
            raise ValueError("event_type must be execution or quote")
        if self.event_time.tzinfo is None or self.event_time.utcoffset() is None:
            raise ValueError("event_time must be timezone-aware")
        if self.quantity <= ZERO or self.price <= ZERO:
            raise ValueError("quantity and price must be positive")
        if self.price_multiplier is not None and self.price_multiplier <= ZERO:
            raise ValueError("price_multiplier must be positive when supplied")

    @property
    def notional(self) -> Decimal | None:
        if self.asset_type == "stock":
            return self.quantity * self.price
        if not self.multiplier_verified or self.price_multiplier is None:
            return None
        return self.quantity * self.price * self.price_multiplier


@dataclass(frozen=True, slots=True)
class AlertRule:
    rule_id: str
    template: RuleTemplate
    asset_type: str
    universe: frozenset[str]
    minimum_quantity: Decimal
    minimum_notional: Decimal
    qualifying_minimum_notional: Decimal | None = None
    cooldown: timedelta = timedelta(seconds=60)
    rolling_window: timedelta = timedelta(seconds=60)
    repeated_count: int = 3
    held_underlyings: frozenset[str] = frozenset()
    escalation_multiple: Decimal = Decimal("2")
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise ValueError("rule_id is required")
        if self.asset_type not in {"stock", "option"}:
            raise ValueError("asset_type must be stock or option")
        if self.minimum_quantity <= ZERO or self.minimum_notional <= ZERO:
            raise ValueError("thresholds must be positive")
        if self.qualifying_minimum_notional is not None and self.qualifying_minimum_notional <= ZERO:
            raise ValueError("qualifying threshold must be positive")
        if self.cooldown < timedelta(0) or self.rolling_window <= timedelta(0):
            raise ValueError("cooldown cannot be negative and window must be positive")
        if self.repeated_count < 1 or self.escalation_multiple < Decimal("1"):
            raise ValueError("invalid repeated count or escalation multiple")


@dataclass(frozen=True, slots=True)
class AlertOutcome:
    code: OutcomeCode
    rule_id: str
    event_id: str
    notional: Decimal | None = None
    event_count: int = 0
    held_underlying: bool = False
    enrichment_only: bool = False

    @property
    def triggered(self) -> bool:
        return self.code in {OutcomeCode.TRIGGERED, OutcomeCode.ENRICHED}


class AlertEngine:
    """In-memory evaluator intended to be driven by a durable journal in the app layer."""

    def __init__(self) -> None:
        self._seen_reliable_ids: set[str] = set()
        self._last_alert: dict[tuple[str, str, str], tuple[datetime, Decimal]] = {}
        self._windows: dict[tuple[str, str, str], list[MarketEvent]] = defaultdict(list)

    def evaluate(self, rule: AlertRule, event: MarketEvent) -> AlertOutcome:
        if not rule.enabled or event.event_type != "execution":
            return self._outcome(OutcomeCode.NOT_EXECUTION, rule, event)
        if event.asset_type != rule.asset_type:
            return self._outcome(OutcomeCode.WRONG_ASSET, rule, event)
        if rule.universe and event.instrument_id not in rule.universe:
            return self._outcome(OutcomeCode.OUTSIDE_UNIVERSE, rule, event)
        if event.identity_reliable and event.event_id in self._seen_reliable_ids:
            return self._outcome(OutcomeCode.DUPLICATE, rule, event)
        if event.identity_reliable:
            self._seen_reliable_ids.add(event.event_id)
        notional = event.notional
        if notional is None:
            return self._outcome(OutcomeCode.UNKNOWN_MULTIPLIER, rule, event)
        if rule.template is RuleTemplate.A03 and not event.identity_reliable:
            return self._outcome(OutcomeCode.IDENTITY_AMBIGUOUS, rule, event, notional)
        qualifying_notional = rule.qualifying_minimum_notional or rule.minimum_notional
        if event.quantity < rule.minimum_quantity or notional < qualifying_notional:
            return self._outcome(OutcomeCode.BELOW_THRESHOLD, rule, event, notional)
        if rule.template is RuleTemplate.A03:
            return self._evaluate_repeated(rule, event, notional)
        if rule.template is RuleTemplate.A04:
            if event.underlying not in rule.held_underlyings:
                return self._outcome(OutcomeCode.NOT_HELD_UNDERLYING, rule, event, notional)
            return self._apply_cooldown(rule, event, notional, enrichment_only=True)
        return self._apply_cooldown(rule, event, notional)

    def _evaluate_repeated(self, rule: AlertRule, event: MarketEvent, notional: Decimal) -> AlertOutcome:
        key = (rule.rule_id, event.instrument_id, event.session)
        start = event.event_time - rule.rolling_window
        window = [item for item in self._windows[key] if start <= item.event_time <= event.event_time]
        window.append(event)
        self._windows[key] = window
        total = sum((item.notional or ZERO for item in window), ZERO)
        if len(window) < rule.repeated_count or total < rule.minimum_notional:
            return self._outcome(OutcomeCode.BELOW_THRESHOLD, rule, event, total, len(window))
        return self._apply_cooldown(rule, event, total, event_count=len(window))

    def _apply_cooldown(
        self, rule: AlertRule, event: MarketEvent, notional: Decimal, event_count: int = 1, enrichment_only: bool = False
    ) -> AlertOutcome:
        key = (rule.rule_id, event.instrument_id, event.session)
        previous = self._last_alert.get(key)
        if previous:
            last_time, last_notional = previous
            if event.event_time < last_time + rule.cooldown and notional <= last_notional * rule.escalation_multiple:
                return self._outcome(OutcomeCode.COOLDOWN, rule, event, notional, event_count)
        self._last_alert[key] = (event.event_time, notional)
        code = OutcomeCode.ENRICHED if enrichment_only else OutcomeCode.TRIGGERED
        return AlertOutcome(code, rule.rule_id, event.event_id, notional, event_count, enrichment_only, enrichment_only)

    @staticmethod
    def _outcome(
        code: OutcomeCode, rule: AlertRule, event: MarketEvent, notional: Decimal | None = None, event_count: int = 0
    ) -> AlertOutcome:
        return AlertOutcome(code, rule.rule_id, event.event_id, notional, event_count)
