"""Provider-neutral, append-only market event journal with explicit quality state."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Mapping


class SourceMode(StrEnum):
    LIVE = "live"
    POLLED = "polled"
    REPLAY = "replay"


class EventKind(StrEnum):
    EXECUTION = "execution"
    CORRECTION = "correction"
    GAP = "gap"


class IngestResult(StrEnum):
    APPENDED = "appended"
    DEDUPLICATED = "deduplicated"


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, float):
        raise ValueError(f"{field} must be supplied as a decimal string or integer")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{field} must be decimal") from error
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{field} must be finite and positive")
    return parsed


@dataclass(frozen=True, slots=True)
class Provenance:
    source: str
    source_mode: SourceMode
    provider_received_at: datetime | None
    received_at: datetime
    payload_hash: str
    provider_event_id: str | None = None
    identity_reliable: bool = False

    def __post_init__(self) -> None:
        if not self.source or not self.payload_hash:
            raise ValueError("source and payload_hash are required")
        object.__setattr__(self, "received_at", _aware(self.received_at, "received_at"))
        if self.provider_received_at is not None:
            object.__setattr__(self, "provider_received_at", _aware(self.provider_received_at, "provider_received_at"))
        if self.identity_reliable and not self.provider_event_id:
            raise ValueError("reliable identity requires provider_event_id")


@dataclass(frozen=True, slots=True)
class NormalizedMarketEvent:
    kind: EventKind
    instrument_id: str
    underlying: str
    asset_type: str
    event_time: datetime
    provenance: Provenance
    quantity: Decimal | None = None
    quantity_unit: str | None = None
    price: Decimal | None = None
    price_multiplier: Decimal | None = None
    correction_of_provider_event_id: str | None = None
    gap_start: datetime | None = None
    gap_end: datetime | None = None
    gap_reason: str | None = None
    offset: int | None = None
    corrected_offset: int | None = None

    def __post_init__(self) -> None:
        if not self.instrument_id or not self.underlying:
            raise ValueError("instrument_id and underlying are required")
        if self.asset_type not in {"stock", "option"}:
            raise ValueError("asset_type must be stock or option")
        object.__setattr__(self, "event_time", _aware(self.event_time, "event_time"))
        if self.kind is EventKind.EXECUTION:
            if self.quantity is None or self.price is None or self.quantity_unit is None:
                raise ValueError("execution requires quantity, quantity_unit, and price")
            expected_unit = "shares" if self.asset_type == "stock" else "contracts"
            if self.quantity_unit != expected_unit:
                raise ValueError(f"{self.asset_type} execution quantity must use {expected_unit}")
            if self.quantity <= 0 or self.price <= 0:
                raise ValueError("execution quantity and price must be positive")
            if self.asset_type == "option" and self.price_multiplier is not None and self.price_multiplier <= 0:
                raise ValueError("price_multiplier must be positive")
        elif self.kind is EventKind.CORRECTION:
            if not self.correction_of_provider_event_id:
                raise ValueError("correction requires correction_of_provider_event_id")
        elif self.kind is EventKind.GAP:
            if self.gap_start is None or self.gap_end is None or not self.gap_reason:
                raise ValueError("gap requires start, end, and reason")
            start, end = _aware(self.gap_start, "gap_start"), _aware(self.gap_end, "gap_end")
            if end <= start:
                raise ValueError("gap_end must be after gap_start")
            object.__setattr__(self, "gap_start", start)
            object.__setattr__(self, "gap_end", end)

    @property
    def notional(self) -> Decimal | None:
        if self.kind is not EventKind.EXECUTION or self.quantity is None or self.price is None:
            return None
        if self.asset_type == "option":
            return None if self.price_multiplier is None else self.quantity * self.price * self.price_multiplier
        return self.quantity * self.price


def normalize_execution(payload: Mapping[str, object], provenance: Provenance) -> NormalizedMarketEvent:
    """Validate provider-shaped data while preserving no raw payload values outside the event."""
    asset_type = str(payload.get("asset_type", ""))
    unit = "shares" if asset_type == "stock" else "contracts" if asset_type == "option" else ""
    raw_time = payload.get("event_time")
    if isinstance(raw_time, str):
        raw_time = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    if not isinstance(raw_time, datetime):
        raise ValueError("event_time must be an ISO timestamp")
    multiplier = payload.get("price_multiplier")
    return NormalizedMarketEvent(
        kind=EventKind.EXECUTION,
        instrument_id=str(payload.get("instrument_id", "")),
        underlying=str(payload.get("underlying", "")),
        asset_type=asset_type,
        event_time=raw_time,
        provenance=provenance,
        quantity=_decimal(payload.get("quantity"), "quantity"),
        quantity_unit=str(payload.get("quantity_unit", unit)),
        price=_decimal(payload.get("price"), "price"),
        price_multiplier=None if multiplier is None else _decimal(multiplier, "price_multiplier"),
    )


class Journal:
    """In-memory reference journal; callers can serialize its normalized entries durably."""

    def __init__(self) -> None:
        self._entries: list[NormalizedMarketEvent] = []
        self._reliable_ids: dict[str, int] = {}

    def append(self, event: NormalizedMarketEvent) -> tuple[IngestResult, NormalizedMarketEvent]:
        reliable_id = event.provenance.provider_event_id if event.kind is EventKind.EXECUTION and event.provenance.identity_reliable else None
        if reliable_id is not None and reliable_id in self._reliable_ids:
            return IngestResult.DEDUPLICATED, event
        corrected_offset = None
        if event.kind is EventKind.CORRECTION:
            corrected_offset = self._reliable_ids.get(event.correction_of_provider_event_id or "")
        appended = replace(event, offset=len(self._entries) + 1, corrected_offset=corrected_offset)
        self._entries.append(appended)
        if reliable_id is not None:
            self._reliable_ids[reliable_id] = appended.offset or 0
        return IngestResult.APPENDED, appended

    def record_gap(self, *, instrument_id: str, underlying: str, asset_type: str, start: datetime, end: datetime, reason: str, provenance: Provenance) -> NormalizedMarketEvent:
        _, event = self.append(NormalizedMarketEvent(EventKind.GAP, instrument_id, underlying, asset_type, start, provenance, gap_start=start, gap_end=end, gap_reason=reason))
        return event

    def replay(self, *, after_offset: int = 0, through_offset: int | None = None) -> tuple[NormalizedMarketEvent, ...]:
        return tuple(entry for entry in self._entries if entry.offset is not None and entry.offset > after_offset and (through_offset is None or entry.offset <= through_offset))
