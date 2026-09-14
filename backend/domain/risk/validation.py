from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.domain.positions.models import PositionSnapshot
from .candidates import Candidate, CandidateKind, Quote
from .policy import RiskPolicy


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    reason: str | None = None


def validate_candidate(candidate: Candidate, snapshot: PositionSnapshot, policy: RiskPolicy, quotes: tuple[Quote, ...], *, now: datetime) -> ValidationResult:
    if candidate.position_version != snapshot.version:
        return ValidationResult(False, "Position snapshot changed.")
    if candidate.policy_version != policy.version:
        return ValidationResult(False, "Risk policy changed.")
    if now > candidate.valid_until:
        return ValidationResult(False, "Candidate expired.")
    quote_ids = {quote.quote_id for quote in quotes if now - quote.observed_at <= policy.max_quote_age}
    if not set(candidate.quote_ids).issubset(quote_ids):
        return ValidationResult(False, "Candidate quote is stale or unavailable.")
    if candidate.kind is not CandidateKind.HOLD and (not candidate.legs or candidate.max_incremental_loss > policy.max_incremental_loss or candidate.incremental_cost > policy.available_funds):
        return ValidationResult(False, "Candidate no longer satisfies deterministic policy limits.")
    return ValidationResult(True)


def validate_model_ranking(candidates: tuple[Candidate, ...], ranked_candidate_ids: tuple[str, ...], proposed_quantities: tuple[int, ...] = ()) -> ValidationResult:
    """Models may rank existing IDs only; quantities are fixed by the generator."""
    if proposed_quantities:
        return ValidationResult(False, "Model-proposed quantities are forbidden.")
    candidate_ids = {candidate.candidate_id for candidate in candidates}
    if len(ranked_candidate_ids) != len(set(ranked_candidate_ids)) or not set(ranked_candidate_ids).issubset(candidate_ids):
        return ValidationResult(False, "Model ranking references an unknown or duplicate candidate.")
    return ValidationResult(True)
