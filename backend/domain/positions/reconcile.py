from __future__ import annotations

from datetime import datetime
from .models import ChangeKind, ImportRow, ImportSource, PositionChange, PositionSnapshot, ReconciliationResult, VersionConflict


def reconcile_import(
    current: PositionSnapshot,
    rows: tuple[ImportRow, ...],
    *,
    expected_version: int,
    source: ImportSource,
    observed_at: datetime,
    complete: bool = False,
) -> ReconciliationResult:
    """Build the next immutable position book from reviewed import rows.

    Screenshot/manual omission preserves an existing holding. A complete API response
    may close omitted holdings; every other close must be explicitly reviewed.
    """
    if current.version != expected_version:
        raise VersionConflict(expected_version, current.version)
    if current.account_id == "":
        raise ValueError("current snapshot must have an account")
    if complete and source is not ImportSource.API:
        raise ValueError("only an API import can be marked complete")
    row_by_id = {row.instrument_id: row for row in rows}
    if len(row_by_id) != len(rows):
        raise ValueError("import contains duplicate instruments")

    old = {position.instrument_id: position for position in current.positions}
    next_positions = dict(old)
    changes: list[PositionChange] = []
    for instrument_id in sorted(row_by_id):
        row = row_by_id[instrument_id]
        before = old.get(instrument_id)
        if row.explicit_close:
            next_positions.pop(instrument_id, None)
            if before is not None:
                changes.append(PositionChange(instrument_id, ChangeKind.CLOSED, before, None))
            continue
        assert row.position is not None
        after = row.position
        next_positions[instrument_id] = after
        kind = ChangeKind.ADDED if before is None else ChangeKind.UNCHANGED if before == after else ChangeKind.UPDATED
        changes.append(PositionChange(instrument_id, kind, before, after))

    if complete:
        for instrument_id in sorted(set(old) - set(row_by_id)):
            before = old[instrument_id]
            next_positions.pop(instrument_id)
            changes.append(PositionChange(instrument_id, ChangeKind.CLOSED, before, None))

    snapshot = PositionSnapshot(
        account_id=current.account_id,
        version=current.version + 1,
        observed_at=observed_at,
        source=source,
        positions=tuple(sorted(next_positions.values(), key=lambda position: position.instrument_id)),
        complete=complete,
    )
    return ReconciliationResult(snapshot=snapshot, changes=tuple(changes))
