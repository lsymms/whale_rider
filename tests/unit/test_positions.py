from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.domain.positions import ImportRow, ImportSource, Position, PositionSnapshot, VersionConflict, reconcile_import
from backend.domain.positions.models import ChangeKind


NOW = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)


def position(instrument_id: str, quantity: str, **changes: object) -> Position:
    values: dict[str, object] = {
        "instrument_id": instrument_id,
        "underlying": "NVDA",
        "asset_type": "stock",
        "quantity": Decimal(quantity),
        "observed_at": NOW,
        "underlying_price": Decimal("150"),
    }
    values.update(changes)
    return Position(**values)  # type: ignore[arg-type]


def snapshot(*positions: Position, version: int = 12) -> PositionSnapshot:
    return PositionSnapshot("demo", version, NOW, ImportSource.MANUAL, positions)


def test_partial_ocr_import_preserves_omitted_holdings_and_records_reviewed_update() -> None:
    current = snapshot(position("NVDA", "100"), position("AMD", "25", underlying="AMD"))
    result = reconcile_import(
        current,
        (ImportRow(position("NVDA", "150"), "NVDA"),),
        expected_version=12,
        source=ImportSource.OCR,
        observed_at=NOW,
    )
    assert result.snapshot.version == 13
    assert [(item.instrument_id, item.quantity) for item in result.snapshot.positions] == [("AMD", Decimal("25")), ("NVDA", Decimal("150"))]
    assert result.changes[0].kind is ChangeKind.UPDATED


def test_explicit_close_is_distinct_from_omission() -> None:
    current = snapshot(position("NVDA", "100"), position("AMD", "25", underlying="AMD"))
    result = reconcile_import(
        current,
        (ImportRow(None, "NVDA", explicit_close=True),),
        expected_version=12,
        source=ImportSource.MANUAL,
        observed_at=NOW,
    )
    assert [item.instrument_id for item in result.snapshot.positions] == ["AMD"]
    assert result.changes == (result.changes[0],)
    assert result.changes[0].kind is ChangeKind.CLOSED


def test_complete_api_read_can_clear_absent_holdings_but_other_sources_cannot() -> None:
    current = snapshot(position("NVDA", "100"), position("AMD", "25", underlying="AMD"))
    result = reconcile_import(
        current,
        (ImportRow(position("NVDA", "100"), "NVDA"),),
        expected_version=12,
        source=ImportSource.API,
        observed_at=NOW,
        complete=True,
    )
    assert [item.instrument_id for item in result.snapshot.positions] == ["NVDA"]
    assert result.changes[-1].instrument_id == "AMD"
    assert result.changes[-1].kind is ChangeKind.CLOSED
    with pytest.raises(ValueError, match="API"):
        reconcile_import(current, (), expected_version=12, source=ImportSource.OCR, observed_at=NOW, complete=True)


def test_stale_review_is_rejected_and_never_overwrites_current_book() -> None:
    with pytest.raises(VersionConflict, match="expected 11, current 12"):
        reconcile_import(snapshot(position("NVDA", "100")), (), expected_version=11, source=ImportSource.OCR, observed_at=NOW)


def test_import_rows_and_positions_reject_ambiguous_or_invalid_values() -> None:
    with pytest.raises(ValueError, match="either a position or an explicit close"):
        ImportRow(None, "NVDA")
    with pytest.raises(ValueError, match="nonzero"):
        position("NVDA", "0")
