from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.domain.positions.models import Position, PositionSnapshot


@dataclass(frozen=True, slots=True)
class UnderlyingExposure:
    underlying: str
    known_delta_shares: Decimal
    gross_known_delta_shares: Decimal
    net_delta_dollars: Decimal | None
    gross_delta_dollars: Decimal | None
    is_complete: bool
    unknown_instrument_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExposureReport:
    snapshot_version: int
    by_underlying: tuple[UnderlyingExposure, ...]
    is_complete: bool


def _delta_shares(position: Position) -> Decimal | None:
    if position.asset_type == "stock":
        return position.quantity
    if position.multiplier is None or position.delta is None:
        return None
    return position.quantity * position.multiplier * position.delta


def calculate_exposure(snapshot: PositionSnapshot) -> ExposureReport:
    """Calculate known delta exposure without treating unavailable Greeks as zero."""
    grouped: dict[str, list[Position]] = {}
    for position in snapshot.positions:
        grouped.setdefault(position.underlying, []).append(position)
    results: list[UnderlyingExposure] = []
    for underlying in sorted(grouped):
        positions = grouped[underlying]
        unknown: list[str] = []
        known_delta = Decimal("0")
        gross_known = Decimal("0")
        price: Decimal | None = None
        price_missing = False
        for position in positions:
            delta_shares = _delta_shares(position)
            if delta_shares is None:
                unknown.append(position.instrument_id)
                continue
            known_delta += delta_shares
            gross_known += abs(delta_shares)
            if position.underlying_price is None:
                price_missing = True
            elif price is None:
                price = position.underlying_price
            elif price != position.underlying_price:
                price_missing = True
        complete = not unknown and not price_missing and price is not None
        results.append(
            UnderlyingExposure(
                underlying=underlying,
                known_delta_shares=known_delta,
                gross_known_delta_shares=gross_known,
                net_delta_dollars=known_delta * price if complete else None,
                gross_delta_dollars=gross_known * price if complete else None,
                is_complete=complete,
                unknown_instrument_ids=tuple(sorted(unknown)),
            )
        )
    return ExposureReport(
        snapshot_version=snapshot.version,
        by_underlying=tuple(results),
        is_complete=all(item.is_complete for item in results),
    )
