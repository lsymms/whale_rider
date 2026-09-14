from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class ImportSource(str, Enum):
    API = "api"
    MANUAL = "manual"
    OCR = "ocr"


class ChangeKind(str, Enum):
    ADDED = "added"
    UPDATED = "updated"
    CLOSED = "closed"
    UNCHANGED = "unchanged"


class VersionConflict(ValueError):
    """Raised when a reviewed import targets an out-of-date position book."""

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(f"position snapshot version conflict: expected {expected}, current {actual}")
        self.expected = expected
        self.actual = actual


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class Position:
    instrument_id: str
    underlying: str
    asset_type: str
    quantity: Decimal
    observed_at: datetime
    price: Decimal | None = None
    underlying_price: Decimal | None = None
    multiplier: Decimal | None = None
    delta: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.instrument_id or not self.underlying:
            raise ValueError("instrument_id and underlying are required")
        if self.asset_type not in {"stock", "option"}:
            raise ValueError("asset_type must be stock or option")
        if not self.quantity.is_finite() or self.quantity == 0:
            raise ValueError("position quantity must be finite and nonzero")
        _require_aware(self.observed_at, "observed_at")
        for name, value in (("price", self.price), ("underlying_price", self.underlying_price), ("multiplier", self.multiplier), ("delta", self.delta)):
            if value is not None and not value.is_finite():
                raise ValueError(f"{name} must be finite")
        if self.price is not None and self.price <= 0:
            raise ValueError("price must be positive")
        if self.underlying_price is not None and self.underlying_price <= 0:
            raise ValueError("underlying_price must be positive")
        if self.asset_type == "option" and self.multiplier is not None and self.multiplier <= 0:
            raise ValueError("multiplier must be positive")
        if self.delta is not None and not Decimal("-1") <= self.delta <= Decimal("1"):
            raise ValueError("delta must be between -1 and 1")


@dataclass(frozen=True, slots=True)
class ImportRow:
    """A reviewed row. Omitted holdings are never interpreted as closures."""

    position: Position | None
    instrument_id: str
    explicit_close: bool = False

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("instrument_id is required")
        if self.explicit_close == (self.position is not None):
            raise ValueError("an import row must contain either a position or an explicit close")
        if self.position is not None and self.position.instrument_id != self.instrument_id:
            raise ValueError("import row instrument_id must match its position")


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    account_id: str
    version: int
    observed_at: datetime
    source: ImportSource
    positions: tuple[Position, ...]
    complete: bool = False

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("account_id is required")
        if self.version < 0:
            raise ValueError("version must be nonnegative")
        _require_aware(self.observed_at, "observed_at")
        ids = [position.instrument_id for position in self.positions]
        if len(ids) != len(set(ids)):
            raise ValueError("snapshot contains duplicate instruments")
        if self.complete and self.source is not ImportSource.API:
            raise ValueError("only a complete API read may clear omitted holdings")


@dataclass(frozen=True, slots=True)
class PositionChange:
    instrument_id: str
    kind: ChangeKind
    before: Position | None
    after: Position | None


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    snapshot: PositionSnapshot
    changes: tuple[PositionChange, ...]
