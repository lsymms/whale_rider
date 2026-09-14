from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.adapters.ai.explanations import StructuredExplanationAdapter
from backend.domain.risk.candidates import Candidate, CandidateKind


NOW = datetime(2026, 9, 14, 14, 30, tzinfo=UTC)


def candidate(candidate_id: str) -> Candidate:
    return Candidate(candidate_id, CandidateKind.HOLD, (), Decimal("0"), Decimal("0"), 12, 3, (), NOW + timedelta(seconds=60), "deterministic hold")


class FakeProvider:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.request = None

    def explain(self, request):
        self.request = request
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def valid_response() -> dict[str, object]:
    return {
        "status": "ranked", "ranked_candidate_ids": ["hold", "trim-nvda"], "supporting_evidence_ids": ["event-1", "snapshot-12"],
        "rationale": "The supplied candidates preserve the reviewed constraints.", "counterevidence": ["Trade intent is unknown."],
        "conditions": ["Recalculate after a material input change."], "uncertainties": ["No model-provided market facts."],
    }


def test_adapter_sends_only_opaque_deterministic_ids_and_returns_grounded_ranking() -> None:
    provider = FakeProvider(valid_response())
    result = StructuredExplanationAdapter(provider).explain(run_id="run-1", objective="reduce exposure", candidates=(candidate("hold"), candidate("trim-nvda")), evidence_ids=("event-1", "snapshot-12"))
    assert provider.request.allowed_candidate_ids == ("hold", "trim-nvda")
    assert provider.request.allowed_evidence_ids == ("event-1", "snapshot-12")
    assert not hasattr(provider.request, "candidates")
    assert result.status == "ranked"
    assert result.explanation is not None
    assert result.explanation.ranked_candidate_ids == ("hold", "trim-nvda")


def test_unknown_candidate_or_evidence_returns_safe_abstention() -> None:
    payload = valid_response()
    payload["ranked_candidate_ids"] = ["invented-entry"]
    result = StructuredExplanationAdapter(FakeProvider(payload)).explain(run_id="run-1", objective="review", candidates=(candidate("hold"),), evidence_ids=("event-1",))
    assert result.status == "abstain"
    assert result.abstention_reason == "invalid_model_response"


def test_structured_quantity_or_instrument_fields_are_rejected_even_when_nested() -> None:
    payload = valid_response()
    payload["conditions"] = [{"quantity": 100}]  # type: ignore[list-item]
    result = StructuredExplanationAdapter(FakeProvider(payload)).explain(run_id="run-1", objective="review", candidates=(candidate("hold"), candidate("trim-nvda")), evidence_ids=("event-1", "snapshot-12"))
    assert result.status == "abstain"
    assert result.abstention_reason == "invalid_model_response"


def test_model_abstention_and_provider_failure_remain_safe() -> None:
    abstaining = StructuredExplanationAdapter(FakeProvider({"status": "abstain", "abstention_reason": "Insufficient evidence.", "uncertainties": ["Refresh positions."]}))
    result = abstaining.explain(run_id="run-1", objective="review", candidates=(candidate("hold"),), evidence_ids=("event-1",))
    assert result.status == "abstain"
    assert result.abstention_reason == "Insufficient evidence."
    unavailable = StructuredExplanationAdapter(FakeProvider(RuntimeError("network failure"))).explain(run_id="run-1", objective="review", candidates=(candidate("hold"),), evidence_ids=("event-1",))
    assert unavailable.status == "abstain"
    assert unavailable.abstention_reason == "provider_unavailable"
