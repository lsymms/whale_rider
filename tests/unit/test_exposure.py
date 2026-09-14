from datetime import datetime, timezone
from decimal import Decimal

from backend.domain.positions import ImportSource, Position, PositionSnapshot
from backend.domain.risk import calculate_exposure


NOW = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)


def snapshot(*positions: Position) -> PositionSnapshot:
    return PositionSnapshot("demo", 12, NOW, ImportSource.MANUAL, positions)


def stock(quantity: str) -> Position:
    return Position("NVDA", "NVDA", "stock", Decimal(quantity), NOW, underlying_price=Decimal("150"))


def option(instrument_id: str, quantity: str, delta: str | None, *, price: str | None = "150") -> Position:
    return Position(
        instrument_id, "NVDA", "option", Decimal(quantity), NOW,
        underlying_price=Decimal(price) if price is not None else None,
        multiplier=Decimal("100"), delta=Decimal(delta) if delta is not None else None,
    )


def test_signed_stock_and_option_delta_uses_decimal_contract_multiplier() -> None:
    report = calculate_exposure(snapshot(stock("100"), option("NVDA-155C", "2", "0.55"), option("NVDA-145P", "1", "-0.30")))
    nvda = report.by_underlying[0]
    assert nvda.known_delta_shares == Decimal("180")
    assert nvda.gross_known_delta_shares == Decimal("240")
    assert nvda.net_delta_dollars == Decimal("27000")
    assert nvda.gross_delta_dollars == Decimal("36000")
    assert nvda.is_complete and report.is_complete


def test_missing_option_greeks_marks_exposure_partial_never_zero() -> None:
    report = calculate_exposure(snapshot(stock("100"), option("NVDA-155C", "2", None)))
    nvda = report.by_underlying[0]
    assert nvda.known_delta_shares == Decimal("100")
    assert nvda.net_delta_dollars is None
    assert nvda.unknown_instrument_ids == ("NVDA-155C",)
    assert not nvda.is_complete and not report.is_complete


def test_missing_or_conflicting_underlying_prices_blocks_dollar_exposure() -> None:
    missing = calculate_exposure(snapshot(stock("100"), option("NVDA-155C", "2", "0.55", price=None))).by_underlying[0]
    conflicting = calculate_exposure(snapshot(stock("100"), option("NVDA-155C", "2", "0.55", price="151"))).by_underlying[0]
    assert missing.net_delta_dollars is None
    assert conflicting.net_delta_dollars is None
    assert not missing.is_complete and not conflicting.is_complete
