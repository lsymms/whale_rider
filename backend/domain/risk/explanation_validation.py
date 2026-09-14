"""Pure validation for untrusted model explanation payloads."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class ExplanationValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ValidatedExplanation:
    status: str
    ranked_candidate_ids: tuple[str, ...] = ()
    supporting_evidence_ids: tuple[str, ...] = ()
    rationale: str | None = None
    counterevidence: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    abstention_reason: str | None = None


_FORBIDDEN_FIELDS = frozenset({"quantity", "quantities", "instrument", "instruments", "instrument_id", "instrument_ids", "legs", "amount", "amounts", "price", "prices", "sizing"})
_RANKED_FIELDS = frozenset({"status", "ranked_candidate_ids", "supporting_evidence_ids", "rationale", "counterevidence", "conditions", "uncertainties"})
_ABSTAIN_FIELDS = frozenset({"status", "abstention_reason", "uncertainties"})


def _short_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 1_000:
        raise ExplanationValidationError(f"{field} must be a non-empty string no longer than 1000 characters")
    return value.strip()


def _text_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 20:
        raise ExplanationValidationError(f"{field} must be a list with at most 20 entries")
    return tuple(_short_text(item, field) for item in value)


def _reject_forbidden_fields(value: object) -> None:
    if isinstance(value, Mapping):
        forbidden = {str(key).lower() for key in value} & _FORBIDDEN_FIELDS
        if forbidden:
            raise ExplanationValidationError(f"model output contains forbidden quantity or instrument fields: {', '.join(sorted(forbidden))}")
        for item in value.values():
            _reject_forbidden_fields(item)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_fields(item)


def validate_explanation_payload(payload: Mapping[str, Any], *, candidate_ids: frozenset[str], evidence_ids: frozenset[str]) -> ValidatedExplanation:
    if not isinstance(payload, Mapping):
        raise ExplanationValidationError("model response must be an object")
    _reject_forbidden_fields(payload)
    status = payload.get("status")
    if status == "abstain":
        if set(payload) != _ABSTAIN_FIELDS:
            raise ExplanationValidationError("abstention response has unsupported fields")
        return ValidatedExplanation(status="abstain", abstention_reason=_short_text(payload.get("abstention_reason"), "abstention_reason"), uncertainties=_text_list(payload.get("uncertainties"), "uncertainties"))
    if status != "ranked":
        raise ExplanationValidationError("status must be ranked or abstain")
    if set(payload) != _RANKED_FIELDS:
        raise ExplanationValidationError("ranked response has unsupported fields")
    ranked = _text_list(payload.get("ranked_candidate_ids"), "ranked_candidate_ids")
    evidence = _text_list(payload.get("supporting_evidence_ids"), "supporting_evidence_ids")
    if not ranked or len(set(ranked)) != len(ranked) or not set(ranked).issubset(candidate_ids):
        raise ExplanationValidationError("ranked candidates must be unique supplied candidate IDs")
    if not evidence or len(set(evidence)) != len(evidence) or not set(evidence).issubset(evidence_ids):
        raise ExplanationValidationError("supporting evidence must be unique supplied evidence IDs")
    return ValidatedExplanation(
        status="ranked", ranked_candidate_ids=ranked, supporting_evidence_ids=evidence,
        rationale=_short_text(payload.get("rationale"), "rationale"),
        counterevidence=_text_list(payload.get("counterevidence"), "counterevidence"),
        conditions=_text_list(payload.get("conditions"), "conditions"),
        uncertainties=_text_list(payload.get("uncertainties"), "uncertainties"),
    )
