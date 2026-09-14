from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_FLOOR
from enum import Enum

from backend.domain.positions.models import PositionSnapshot
from .policy import RiskPolicy


class Objective(str, Enum):
    REVIEW = "review"
    REDUCE_EXPOSURE = "reduce_exposure"
    PROTECT_DOWNSIDE = "protect_downside"
    PERMITTED_ENTRY = "permitted_entry"


class CandidateKind(str, Enum):
    HOLD = "hold"
    TRIM_STOCK = "trim_stock"
    REDUCE_OPTION = "reduce_option"
    PROTECTIVE_PUT = "protective_put"
    DEBIT_VERTICAL = "debit_vertical"


@dataclass(frozen=True, slots=True)
class Quote:
    quote_id: str
    instrument_id: str
    underlying: str
    observed_at: datetime
    bid: Decimal
    ask: Decimal
    multiplier: Decimal = Decimal("1")
    right: str | None = None
    strike: Decimal | None = None
    expiry: str | None = None
    available_contracts: int = 0

    def __post_init__(self) -> None:
        if not self.quote_id or not self.instrument_id or not self.underlying:
            raise ValueError("quote identity is required")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("quote time must be timezone-aware")
        if not all(value.is_finite() for value in (self.bid, self.ask, self.multiplier)) or self.bid < 0 or self.ask <= 0 or self.bid > self.ask:
            raise ValueError("quote bid/ask/multiplier is invalid")
        if self.multiplier <= 0 or self.available_contracts < 0:
            raise ValueError("quote multiplier and capacity are invalid")


@dataclass(frozen=True, slots=True)
class CandidateLeg:
    instrument_id: str
    quantity: int
    action: str


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    kind: CandidateKind
    legs: tuple[CandidateLeg, ...]
    incremental_cost: Decimal
    max_incremental_loss: Decimal
    position_version: int
    policy_version: int
    quote_ids: tuple[str, ...]
    valid_until: datetime
    reason: str


@dataclass(frozen=True, slots=True)
class CandidateSet:
    candidates: tuple[Candidate, ...]
    abstention_reason: str | None = None


def _floor(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


def _fresh_snapshot(snapshot: PositionSnapshot, policy: RiskPolicy, now: datetime) -> bool:
    return now - snapshot.observed_at <= policy.max_position_age


def _fresh(quote: Quote, policy: RiskPolicy, now: datetime) -> bool:
    return now - quote.observed_at <= policy.max_quote_age


def _candidate(
    candidate_id: str, kind: CandidateKind, legs: tuple[CandidateLeg, ...], cost: Decimal, loss: Decimal,
    snapshot: PositionSnapshot, policy: RiskPolicy, quote_ids: tuple[str, ...], now: datetime, reason: str,
) -> Candidate:
    return Candidate(candidate_id, kind, legs, cost, loss, snapshot.version, policy.version, quote_ids, now + policy.candidate_ttl, reason)


def generate_candidates(
    snapshot: PositionSnapshot,
    policy: RiskPolicy,
    quotes: tuple[Quote, ...],
    *,
    objective: Objective,
    now: datetime,
) -> CandidateSet:
    """Generate only fixed-size, policy-permitted manual-review candidates."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    hold = _candidate("hold", CandidateKind.HOLD, (), Decimal("0"), Decimal("0"), snapshot, policy, (), now, "Wait for a reviewed condition; no order is implied.")
    if not _fresh_snapshot(snapshot, policy, now):
        return CandidateSet((hold,), "Position snapshot is stale; actionable sizing is blocked.")
    quote_by_instrument = {quote.instrument_id: quote for quote in quotes if _fresh(quote, policy, now)}
    candidates: list[Candidate] = [hold]

    if objective is Objective.REDUCE_EXPOSURE:
        for position in snapshot.positions:
            if position.quantity <= 0:
                continue
            quantity = _floor(position.quantity * policy.trim_fraction)
            if quantity < 1:
                continue
            if position.asset_type == "stock" and "trim_stock" in policy.allowed_strategies:
                candidates.append(_candidate(f"trim:{position.instrument_id}", CandidateKind.TRIM_STOCK, (CandidateLeg(position.instrument_id, quantity, "sell"),), Decimal("0"), Decimal("0"), snapshot, policy, (), now, "Reduce an existing long stock position by the policy fraction."))
            if position.asset_type == "option" and "reduce_option" in policy.allowed_strategies:
                quote = quote_by_instrument.get(position.instrument_id)
                if quote is not None:
                    candidates.append(_candidate(f"reduce:{position.instrument_id}", CandidateKind.REDUCE_OPTION, (CandidateLeg(position.instrument_id, quantity, "sell_to_close"),), Decimal("0"), Decimal("0"), snapshot, policy, (quote.quote_id,), now, "Reduce an existing long option position by the policy fraction."))

    if objective is Objective.PROTECT_DOWNSIDE and "protective_put" in policy.allowed_strategies:
        for stock in (position for position in snapshot.positions if position.asset_type == "stock" and position.quantity > 0):
            for quote in quote_by_instrument.values():
                if quote.underlying != stock.underlying or quote.right != "put" or quote.available_contracts < 1:
                    continue
                debit = quote.ask * quote.multiplier
                quantity = min(_floor(stock.quantity / quote.multiplier), _floor(policy.max_incremental_loss / debit), _floor(policy.available_funds / debit), quote.available_contracts)
                if quantity >= 1:
                    candidates.append(_candidate(f"protect:{quote.instrument_id}", CandidateKind.PROTECTIVE_PUT, (CandidateLeg(quote.instrument_id, quantity, "buy_to_open"),), debit * quantity, debit * quantity, snapshot, policy, (quote.quote_id,), now, "Protect up to the existing long-share coverage allowed by policy and funds."))

    if objective is Objective.PERMITTED_ENTRY and "debit_vertical" in policy.allowed_strategies:
        option_quotes = tuple(quote for quote in quote_by_instrument.values() if quote.right in {"call", "put"} and quote.strike is not None and quote.expiry is not None)
        for long_leg in option_quotes:
            for short_leg in option_quotes:
                if long_leg.instrument_id == short_leg.instrument_id or (long_leg.underlying, long_leg.right, long_leg.expiry, long_leg.multiplier) != (short_leg.underlying, short_leg.right, short_leg.expiry, short_leg.multiplier):
                    continue
                width = abs(long_leg.strike - short_leg.strike) if long_leg.strike is not None and short_leg.strike is not None else Decimal("0")
                debit = (long_leg.ask - short_leg.bid) * long_leg.multiplier
                if width <= 0 or debit <= 0 or debit >= width * long_leg.multiplier or min(long_leg.available_contracts, short_leg.available_contracts) < 1:
                    continue
                quantity = min(_floor(policy.max_incremental_loss / debit), _floor(policy.available_funds / debit), long_leg.available_contracts, short_leg.available_contracts)
                if quantity >= 1:
                    candidates.append(_candidate(f"vertical:{long_leg.instrument_id}:{short_leg.instrument_id}", CandidateKind.DEBIT_VERTICAL, (CandidateLeg(long_leg.instrument_id, quantity, "buy_to_open"), CandidateLeg(short_leg.instrument_id, quantity, "sell_to_open")), debit * quantity, debit * quantity, snapshot, policy, (long_leg.quote_id, short_leg.quote_id), now, "Defined-risk debit vertical sized from policy, funds, and quote capacity."))
    return CandidateSet(tuple(candidates))
