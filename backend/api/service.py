"""In-memory API facade used until repository storage is added for these records."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from backend.domain.positions import ImportRow, ImportSource, Position, PositionSnapshot, VersionConflict, reconcile_import
from backend.domain.risk import calculate_exposure
from backend.workers.capabilities import CapabilityProbeRunner


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class ImportDraft:
    import_id: str
    account_id: str
    source: ImportSource
    expected_version: int
    rows: tuple[ImportRow, ...]
    review_required: bool
    observed_at: datetime


class LocalApiService:
    """A side-effect-free facade: no Webull, AI, or Telegram calls are made here."""

    def __init__(self, capability_runner: CapabilityProbeRunner | None = None) -> None:
        self._snapshots: dict[str, PositionSnapshot] = {}
        self._drafts: dict[str, ImportDraft] = {}
        self._capability_runner = capability_runner or CapabilityProbeRunner()
        self._capability_report: dict[str, object] | None = None

    def capabilities(self) -> dict[str, object]:
        if self._capability_report is not None:
            return self._capability_report
        return {
            "generated_at": utc_now().isoformat(),
            "source": "local_fallback",
            "capabilities": {
                "authentication": {"state": "unknown"},
                "stock_snapshot": {"state": "unknown"},
                "option_snapshot": {"state": "unknown"},
            },
        }

    def refresh_capabilities(self) -> dict[str, object]:
        self._capability_report = self._capability_runner.run()
        return self._capability_report

    def current_snapshot(self, account_id: str) -> PositionSnapshot:
        try:
            return self._snapshots[account_id]
        except KeyError as error:
            raise KeyError("position snapshot not found") from error

    def create_draft(self, payload: dict[str, object]) -> ImportDraft:
        account_id = required_text(payload, "account_id")
        source = ImportSource(str(payload.get("source", "ocr")))
        current = self._snapshots.get(account_id) or PositionSnapshot(account_id, 0, utc_now(), ImportSource.MANUAL, ())
        expected_version = int(payload.get("expected_position_version", current.version))
        rows, review_required = parse_rows(payload.get("rows"), default_observed_at=utc_now())
        draft = ImportDraft(str(uuid4()), account_id, source, expected_version, rows, review_required, utc_now())
        self._drafts[draft.import_id] = draft
        return draft

    def update_draft(self, import_id: str, payload: dict[str, object]) -> ImportDraft:
        draft = self._drafts[import_id]
        rows, review_required = parse_rows(payload.get("rows"), default_observed_at=draft.observed_at)
        updated = ImportDraft(draft.import_id, draft.account_id, draft.source, draft.expected_version, rows, review_required, draft.observed_at)
        self._drafts[import_id] = updated
        return updated

    def commit_draft(self, import_id: str) -> PositionSnapshot:
        draft = self._drafts[import_id]
        if draft.review_required:
            raise ValueError("draft has unresolved review fields")
        current = self._snapshots.get(draft.account_id) or PositionSnapshot(draft.account_id, 0, draft.observed_at, ImportSource.MANUAL, ())
        result = reconcile_import(current, draft.rows, expected_version=draft.expected_version, source=draft.source, observed_at=utc_now())
        self._snapshots[draft.account_id] = result.snapshot
        return result.snapshot

    def exposure(self, account_id: str) -> dict[str, object]:
        report = calculate_exposure(self.current_snapshot(account_id))
        return {
            "snapshot_version": report.snapshot_version,
            "is_complete": report.is_complete,
            "by_underlying": [
                {
                    "underlying": item.underlying,
                    "known_delta_shares": decimal_text(item.known_delta_shares),
                    "gross_known_delta_shares": decimal_text(item.gross_known_delta_shares),
                    "net_delta_dollars": decimal_text(item.net_delta_dollars),
                    "gross_delta_dollars": decimal_text(item.gross_delta_dollars),
                    "is_complete": item.is_complete,
                    "unknown_instrument_ids": list(item.unknown_instrument_ids),
                }
                for item in report.by_underlying
            ],
        }

    def suggestions(self, account_id: str) -> dict[str, object]:
        snapshot = self.current_snapshot(account_id)
        exposure = calculate_exposure(snapshot)
        if not exposure.is_complete:
            return {"status": "abstain", "reason": "exposure_incomplete", "snapshot_version": snapshot.version, "candidates": []}
        candidates: list[dict[str, object]] = [{"id": "hold", "action": "hold", "snapshot_version": snapshot.version}]
        for position in snapshot.positions:
            if position.asset_type == "stock":
                quantity = abs(position.quantity) / Decimal("2")
                if quantity > 0:
                    candidates.append({
                        "id": f"reduce-{position.instrument_id}", "action": "reduce",
                        "instrument_id": position.instrument_id,
                        "side": "sell" if position.quantity > 0 else "buy_to_cover",
                        "quantity": decimal_text(quantity), "snapshot_version": snapshot.version,
                    })
        return {"status": "deterministic_candidates", "snapshot_version": snapshot.version, "candidates": candidates}


def required_text(payload: dict[str, object], key: str) -> str:
    value = str(payload.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def parse_datetime(value: object, default: datetime) -> datetime:
    if value is None:
        return default
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return parsed.astimezone(UTC)


def parse_rows(value: object, *, default_observed_at: datetime) -> tuple[tuple[ImportRow, ...], bool]:
    if not isinstance(value, list):
        raise ValueError("rows must be a list")
    rows: list[ImportRow] = []
    needs_review = False
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError("each row must be an object")
        instrument_id = required_text(raw, "instrument_id")
        review_fields = raw.get("requires_review", [])
        if not isinstance(review_fields, list):
            raise ValueError("requires_review must be a list")
        needs_review = needs_review or bool(review_fields)
        if raw.get("explicit_close") is True:
            rows.append(ImportRow(None, instrument_id, explicit_close=True))
            continue
        position = Position(
            instrument_id=instrument_id,
            underlying=required_text(raw, "underlying"),
            asset_type=required_text(raw, "asset_type"),
            quantity=Decimal(required_text(raw, "quantity")),
            observed_at=parse_datetime(raw.get("observed_at"), default_observed_at),
            price=optional_decimal(raw.get("price")),
            underlying_price=optional_decimal(raw.get("underlying_price")),
            multiplier=optional_decimal(raw.get("multiplier")),
            delta=optional_decimal(raw.get("delta")),
        )
        rows.append(ImportRow(position, instrument_id))
    return tuple(rows), needs_review


def optional_decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")
