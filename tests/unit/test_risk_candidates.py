from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.domain.positions import ImportSource, Position, PositionSnapshot
from backend.domain.risk import CandidateKind, Objective, Quote, RiskPolicy, generate_candidates, validate_candidate, validate_model_ranking


NOW = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)


def policy(**changes: object) -> RiskPolicy:
    values: dict[str, object] = {"version": 3, "max_incremental_loss": Decimal("500"), "available_funds": Decimal("1000")}
    values.update(changes)
    return RiskPolicy(**values)  # type: ignore[arg-type]


def book(*positions: Position, observed_at: datetime = NOW, version: int = 12) -> PositionSnapshot:
    return PositionSnapshot("demo", version, observed_at, ImportSource.MANUAL, positions)


def stock(quantity: str = "100") -> Position:
    return Position("NVDA", "NVDA", "stock", Decimal(quantity), NOW, underlying_price=Decimal("150"))


def option(instrument: str = "NVDA-155C", quantity: str = "4") -> Position:
    return Position(instrument, "NVDA", "option", Decimal(quantity), NOW, underlying_price=Decimal("150"), multiplier=Decimal("100"), delta=Decimal("0.5"))


def quote(instrument: str, *, right: str | None = None, strike: str | None = None, bid: str = "1.80", ask: str = "2.00", capacity: int = 10, age: timedelta = timedelta()) -> Quote:
    return Quote(f"q-{instrument}", instrument, "NVDA", NOW - age, Decimal(bid), Decimal(ask), Decimal("100") if right else Decimal("1"), right, Decimal(strike) if strike else None, "2026-10-16" if right else None, capacity)


def test_reduce_candidates_are_deterministically_sized_from_policy_not_model() -> None:
    candidates = generate_candidates(book(stock(), option()), policy(), (quote("NVDA-155C", right="call", strike="155"),), objective=Objective.REDUCE_EXPOSURE, now=NOW).candidates
    trim = next(item for item in candidates if item.kind is CandidateKind.TRIM_STOCK)
    reduce_option = next(item for item in candidates if item.kind is CandidateKind.REDUCE_OPTION)
    assert trim.legs[0].quantity == 50
    assert reduce_option.legs[0].quantity == 2
    assert not validate_model_ranking(candidates, (trim.candidate_id,), (999,)).valid
    assert validate_model_ranking(candidates, (trim.candidate_id, reduce_option.candidate_id)).valid


def test_stale_positions_return_hold_only_with_explicit_abstention() -> None:
    stale = book(stock(), observed_at=NOW - timedelta(seconds=61))
    result = generate_candidates(stale, policy(), (), objective=Objective.REDUCE_EXPOSURE, now=NOW)
    assert [item.kind for item in result.candidates] == [CandidateKind.HOLD]
    assert result.abstention_reason == "Position snapshot is stale; actionable sizing is blocked."


def test_protective_put_quantity_honors_coverage_risk_funds_and_quote_capacity() -> None:
    result = generate_candidates(book(stock("250")), policy(max_incremental_loss=Decimal("500"), available_funds=Decimal("450")), (quote("NVDA-145P", right="put", strike="145", ask="2.00", capacity=10),), objective=Objective.PROTECT_DOWNSIDE, now=NOW)
    protection = next(item for item in result.candidates if item.kind is CandidateKind.PROTECTIVE_PUT)
    assert protection.legs[0].quantity == 2  # $200 each, constrained by $450 funds.
    assert protection.incremental_cost == Decimal("400")
    assert protection.max_incremental_loss == Decimal("400")


def test_debit_vertical_requires_valid_whole_strategy_and_sizes_by_debit() -> None:
    valid_quotes = (quote("NVDA-150C", right="call", strike="150", ask="3.00", bid="2.90", capacity=8), quote("NVDA-155C", right="call", strike="155", ask="1.20", bid="1.00", capacity=8))
    result = generate_candidates(book(stock()), policy(), valid_quotes, objective=Objective.PERMITTED_ENTRY, now=NOW)
    vertical = next(item for item in result.candidates if item.kind is CandidateKind.DEBIT_VERTICAL)
    assert vertical.legs[0].quantity == 2  # ($3.00 - $1.00) * 100 = $200, risk budget is $500.
    assert vertical.max_incremental_loss == Decimal("400")
    bad_quotes = (quote("NVDA-150C", right="call", strike="150", ask="6.00", bid="5.90"), quote("NVDA-155C", right="call", strike="155", ask="1.20", bid="0.00"))
    assert all(item.kind is not CandidateKind.DEBIT_VERTICAL for item in generate_candidates(book(stock()), policy(), bad_quotes, objective=Objective.PERMITTED_ENTRY, now=NOW).candidates)


def test_validation_rechecks_versions_quote_freshness_policy_and_expiry() -> None:
    source_quote = quote("NVDA-155C", right="call", strike="155")
    candidate = next(item for item in generate_candidates(book(option()), policy(), (source_quote,), objective=Objective.REDUCE_EXPOSURE, now=NOW).candidates if item.kind is CandidateKind.REDUCE_OPTION)
    assert validate_candidate(candidate, book(option()), policy(), (source_quote,), now=NOW).valid
    assert not validate_candidate(candidate, book(option(), version=13), policy(), (source_quote,), now=NOW).valid
    assert not validate_candidate(candidate, book(option()), policy(version=4), (source_quote,), now=NOW).valid
    assert not validate_candidate(candidate, book(option()), policy(), (quote("NVDA-155C", right="call", strike="155", age=timedelta(seconds=6)),), now=NOW).valid
    assert not validate_candidate(candidate, book(option()), policy(), (source_quote,), now=NOW + timedelta(seconds=61)).valid
