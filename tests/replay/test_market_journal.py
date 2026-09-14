from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.domain.market import EventKind, IngestResult, Journal, NormalizedMarketEvent, Provenance, SourceMode, normalize_execution


NOW = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)


def provenance(event_id: str | None, *, reliable: bool = False) -> Provenance:
    return Provenance("webull", SourceMode.REPLAY, NOW, NOW + timedelta(seconds=1), "hash-" + (event_id or "none"), event_id, reliable)


def payload(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "instrument_id": "NVDA", "underlying": "NVDA", "asset_type": "stock", "event_time": "2026-09-14T14:30:00Z",
        "quantity": "10000", "price": "100.25", "quantity_unit": "shares",
    }
    value.update(changes)
    return value


def test_normalization_preserves_decimal_units_time_and_provenance() -> None:
    event = normalize_execution(payload(), provenance("trade-1", reliable=True))
    assert event.quantity == Decimal("10000") and event.price == Decimal("100.25")
    assert event.notional == Decimal("1002500")
    assert event.quantity_unit == "shares" and event.provenance.source_mode is SourceMode.REPLAY
    assert event.event_time.tzinfo is not None and event.provenance.received_at > event.event_time


def test_reliable_execution_id_is_deduplicated_but_identical_unreliable_prints_remain() -> None:
    journal = Journal()
    reliable = normalize_execution(payload(), provenance("trade-1", reliable=True))
    assert journal.append(reliable)[0] is IngestResult.APPENDED
    assert journal.append(reliable)[0] is IngestResult.DEDUPLICATED
    first = normalize_execution(payload(), provenance(None))
    second = normalize_execution(payload(), provenance(None))
    assert journal.append(first)[1].offset == 2
    assert journal.append(second)[1].offset == 3
    assert len(journal.replay()) == 3


def test_correction_references_original_offset_and_unknown_reference_is_visible() -> None:
    journal = Journal()
    journal.append(normalize_execution(payload(), provenance("trade-1", reliable=True)))
    correction = journal.append(
        NormalizedMarketEvent(
            EventKind.CORRECTION, "NVDA", "NVDA", "stock", NOW + timedelta(seconds=2), provenance("corr-1"), correction_of_provider_event_id="trade-1"
        )
    )[1]
    assert correction.corrected_offset == 1


def test_gap_is_replayable_and_marks_continuity_break() -> None:
    journal = Journal()
    gap = journal.record_gap(instrument_id="NVDA", underlying="NVDA", asset_type="stock", start=NOW, end=NOW + timedelta(seconds=30), reason="provider_disconnect", provenance=provenance(None))
    assert gap.kind is EventKind.GAP and gap.offset == 1 and gap.gap_reason == "provider_disconnect"
    assert journal.replay(after_offset=1) == ()


def test_rejects_float_and_wrong_units_before_journaling() -> None:
    with pytest.raises(ValueError, match="decimal string"):
        normalize_execution(payload(price=100.25), provenance("trade"))
    with pytest.raises(ValueError, match="shares"):
        normalize_execution(payload(quantity_unit="contracts"), provenance("trade"))
