"""Offline bridge from normalized journal records to persistent alerts and outbox items."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from backend.domain.alerts import AlertEngine, AlertOutcome, AlertRule, MarketEvent, RuleTemplate
from backend.domain.market import EventKind, Journal, NormalizedMarketEvent
from backend.domain.notifications import DeliveryKind, Notification
from backend.storage import RuleStore, SqliteOutbox
from backend.storage.alerts import StoredRule


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    rule_id: str
    event_offset: int | None
    outcome: AlertOutcome | None
    notification: Notification | None
    skipped_reason: str | None = None


class PersistentAlertWorker:
    """Loads immutable active rules; it never invokes a network transport itself."""

    def __init__(self, rules: RuleStore, outbox: SqliteOutbox, engine: AlertEngine | None = None) -> None:
        self._rules = rules
        self._outbox = outbox
        self._engine = engine or AlertEngine()

    def process_replay(self, journal: Journal, *, after_offset: int = 0, now: datetime) -> tuple[EvaluationResult, ...]:
        return tuple(result for event in journal.replay(after_offset=after_offset) for result in self.process_event(event, now=now))

    def process_event(self, event: NormalizedMarketEvent, *, now: datetime) -> tuple[EvaluationResult, ...]:
        if event.kind is not EventKind.EXECUTION:
            return (EvaluationResult("", event.offset, None, None, skipped_reason=f"{event.kind.value}_not_evaluable"),)
        results: list[EvaluationResult] = []
        for stored in self._rules.list():
            if stored.state != "active" or (stored.paused_until is not None and stored.paused_until > now):
                results.append(EvaluationResult(stored.rule_id, event.offset, None, None, "rule_inactive"))
                continue
            try:
                rule, destination, expiry = build_rule(stored)
            except (KeyError, ValueError, ArithmeticError) as error:
                results.append(EvaluationResult(stored.rule_id, event.offset, None, None, f"invalid_rule:{error}"))
                continue
            outcome = self._engine.evaluate(rule, to_alert_event(event))
            # A04 only enriches the primary alert's evidence; creating a second
            # delivery here would violate the catalog's no-duplicate requirement.
            if not outcome.triggered or outcome.enrichment_only:
                results.append(EvaluationResult(stored.rule_id, event.offset, outcome, None))
                continue
            idempotency = f"alert:{stored.rule_id}:{stored.revision}:{event.provenance.source}:{event.provenance.provider_event_id or event.offset}"
            notification = Notification(
                notification_id=str(uuid5(NAMESPACE_URL, idempotency)),
                idempotency_key=idempotency,
                kind=DeliveryKind.ALERT,
                destination_id=destination,
                text=render_alert(stored, event, outcome),
                created_at=now,
                expires_at=now + expiry,
            )
            results.append(EvaluationResult(stored.rule_id, event.offset, outcome, self._outbox.enqueue(notification)))
        return tuple(results)


def build_rule(stored: StoredRule) -> tuple[AlertRule, str, timedelta]:
    value = stored.payload
    rule = AlertRule(
        rule_id=stored.rule_id,
        template=RuleTemplate(str(value["template"])),
        asset_type=str(value["asset_type"]),
        universe=frozenset(str(item) for item in value.get("universe", [])),
        minimum_quantity=Decimal(str(value["minimum_quantity"])),
        minimum_notional=Decimal(str(value["minimum_notional"])),
        qualifying_minimum_notional=Decimal(str(value["qualifying_minimum_notional"])) if value.get("qualifying_minimum_notional") is not None else None,
        cooldown=timedelta(seconds=int(value.get("cooldown_seconds", 60))),
        rolling_window=timedelta(seconds=int(value.get("rolling_window_seconds", 60))),
        repeated_count=int(value.get("repeated_count", 3)),
        held_underlyings=frozenset(str(item) for item in value.get("held_underlyings", [])),
        escalation_multiple=Decimal(str(value.get("escalation_multiple", "2"))),
    )
    destination = str(value["destination_id"]).strip()
    if not destination:
        raise ValueError("destination_id is required")
    expiry = timedelta(seconds=int(value.get("expires_after_seconds", 60)))
    if expiry <= timedelta(0):
        raise ValueError("expires_after_seconds must be positive")
    return rule, destination, expiry


def to_alert_event(event: NormalizedMarketEvent) -> MarketEvent:
    assert event.quantity is not None and event.price is not None
    event_id = event.provenance.provider_event_id or f"{event.provenance.source}:{event.provenance.payload_hash}:{event.offset}"
    return MarketEvent(
        event_id=event_id,
        instrument_id=event.instrument_id,
        underlying=event.underlying,
        asset_type=event.asset_type,
        event_type="execution",
        event_time=event.event_time,
        quantity=event.quantity,
        price=event.price,
        price_multiplier=event.price_multiplier,
        # A normalized multiplier is an explicit contract field, never a guessed 100.
        multiplier_verified=event.asset_type == "stock" or event.price_multiplier is not None,
        identity_reliable=event.provenance.identity_reliable,
    )


def render_alert(stored: StoredRule, event: NormalizedMarketEvent, outcome: AlertOutcome) -> str:
    quantity = format(event.quantity or Decimal("0"), "f")
    price = format(event.price or Decimal("0"), "f")
    notional = format(outcome.notional or Decimal("0"), "f")
    return "\n".join((
        f"WR-{event.offset or 0} | {stored.payload['template']} | {event.asset_type.upper()} EXECUTION",
        f"{event.underlying} | {quantity} {event.quantity_unit} x ${price} = ${notional}",
        f"Rule {stored.rule_id} v{stored.revision} | source {event.provenance.source_mode.value}",
        "Observed execution; intent unknown. Review in the local app.",
    ))
