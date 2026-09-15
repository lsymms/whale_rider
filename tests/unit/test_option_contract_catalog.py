import json

import pytest

from backend.adapters.webull.contracts import ContractListError, OptionContractCatalog


def contracts() -> list[dict[str, object]]:
    return [
        {"provider_symbol": "AAPL260918C00155000", "underlying": "AAPL", "expiry": "2026-09-18", "right": "call", "strike": "155", "multiplier": "100", "operator_note": "do not emit"},
        {"provider_symbol": "AAPL260918P00145000", "underlying": "AAPL", "expiry": "2026-09-18", "right": "put", "strike": "145", "multiplier": "100", "account_id": "private"},
    ]


def test_operator_contracts_are_typed_and_bounded_for_probe_selection() -> None:
    catalog = OptionContractCatalog.from_operator_list(contracts())
    assert catalog.probe_symbols() == ("AAPL260918C00155000", "AAPL260918P00145000")
    assert catalog.probe_symbols(1) == ("AAPL260918C00155000",)
    report = catalog.redacted_dict()
    assert report["count"] == 2
    assert report["contracts"][0]["strike"] == "155"


def test_redacted_output_excludes_operator_private_source_fields() -> None:
    report = OptionContractCatalog.from_operator_list(contracts()).redacted_dict()
    encoded = json.dumps(report)
    assert "private" not in encoded
    assert "operator_note" not in encoded


@pytest.mark.parametrize("field,value", [
    ("provider_symbol", "AAPL?inject=true"),
    ("right", "straddle"),
    ("strike", "0"),
    ("multiplier", "0"),
])
def test_rejects_unsafe_or_invalid_contract_fields(field: str, value: object) -> None:
    values = contracts()[:1]
    values[0][field] = value
    with pytest.raises(ContractListError):
        OptionContractCatalog.from_operator_list(values)


def test_duplicate_symbol_and_unbounded_list_rejected() -> None:
    values = contracts()
    values[1]["provider_symbol"] = values[0]["provider_symbol"]
    with pytest.raises(ContractListError, match="unique"):
        OptionContractCatalog.from_operator_list(values)
    with pytest.raises(ValueError, match="positive"):
        OptionContractCatalog.from_operator_list(contracts()).probe_symbols(0)
