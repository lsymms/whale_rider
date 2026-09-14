"""Injectable model adapter for grounded explanation of deterministic candidates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from backend.domain.risk.candidates import Candidate
from backend.domain.risk.explanation_validation import ExplanationValidationError, ValidatedExplanation, validate_explanation_payload


@dataclass(frozen=True, slots=True)
class ExplanationRequest:
    run_id: str
    objective: str
    allowed_candidate_ids: tuple[str, ...]
    allowed_evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExplanationResult:
    status: str
    run_id: str
    explanation: ValidatedExplanation | None = None
    abstention_reason: str | None = None


class ExplanationProvider(Protocol):
    """A provider receives opaque IDs only, never broker credentials or order capabilities."""

    def explain(self, request: ExplanationRequest) -> Mapping[str, Any]: ...


class StructuredExplanationAdapter:
    def __init__(self, provider: ExplanationProvider) -> None:
        self._provider = provider

    def explain(self, *, run_id: str, objective: str, candidates: tuple[Candidate, ...], evidence_ids: tuple[str, ...]) -> ExplanationResult:
        if not run_id.strip() or not objective.strip():
            raise ValueError("run_id and objective are required")
        candidate_ids = tuple(candidate.candidate_id for candidate in candidates)
        if len(candidate_ids) != len(set(candidate_ids)) or not candidate_ids:
            raise ValueError("candidates must have at least one unique ID")
        if len(evidence_ids) != len(set(evidence_ids)) or not evidence_ids or any(not item.strip() for item in evidence_ids):
            raise ValueError("evidence_ids must be non-empty unique IDs")
        request = ExplanationRequest(run_id.strip(), objective.strip(), candidate_ids, evidence_ids)
        try:
            payload = self._provider.explain(request)
            explanation = validate_explanation_payload(payload, candidate_ids=frozenset(candidate_ids), evidence_ids=frozenset(evidence_ids))
        except ExplanationValidationError:
            return ExplanationResult("abstain", request.run_id, abstention_reason="invalid_model_response")
        except Exception:
            return ExplanationResult("abstain", request.run_id, abstention_reason="provider_unavailable")
        if explanation.status == "abstain":
            return ExplanationResult("abstain", request.run_id, explanation=explanation, abstention_reason=explanation.abstention_reason)
        return ExplanationResult("ranked", request.run_id, explanation=explanation)
