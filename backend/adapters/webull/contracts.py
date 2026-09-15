"""Typed, operator-provided option contracts for read-only probing and polling.

Webull contract discovery schemas must be verified against an entitled account before
an API discovery endpoint is enabled. This module therefore accepts an operator's
exact provider symbols and never invents OCC/Webull symbol encodings or calls HTTP.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping, Sequence


class ContractListError(ValueError):
    """Raised when an operator contract list is incomplete or unsafe for a query."""


_SYMBOL = re.compile(r"^[A-Za-z0-9._/-]+$")
_UNDERLYING = re.compile(r"^[A-Z.]{1,12}$")


@dataclass(frozen=True, slots=True)
class OptionContract:
    """A verified-by-operator contract identity; ``provider_symbol`` is not derived."""

    provider_symbol: str
    underlying: str
    expiry: date
    right: str
    strike: Decimal
    multiplier: Decimal | None = None

    def __post_init__(self) -> None:
        if not _SYMBOL.fullmatch(self.provider_symbol):
            raise ContractListError("provider_symbol contains unsupported query characters")
        if not _UNDERLYING.fullmatch(self.underlying):
            raise ContractListError("underlying must be uppercase letters or dots")
        if self.right not in {"call", "put"}:
            raise ContractListError("right must be call or put")
        if not self.strike.is_finite() or self.strike <= 0:
            raise ContractListError("strike must be finite and positive")
        if self.multiplier is not None and (not self.multiplier.is_finite() or self.multiplier <= 0):
            raise ContractListError("multiplier must be finite and positive")


@dataclass(frozen=True, slots=True)
class OptionContractCatalog:
    contracts: tuple[OptionContract, ...]

    def __post_init__(self) -> None:
        symbols = [contract.provider_symbol for contract in self.contracts]
        if not symbols:
            raise ContractListError("at least one contract is required")
        if len(symbols) != len(set(symbols)):
            raise ContractListError("provider_symbol values must be unique")

    @classmethod
    def from_operator_list(cls, values: Sequence[Mapping[str, object]]) -> "OptionContractCatalog":
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise ContractListError("contract list must be an array")
        return cls(tuple(_parse_contract(value) for value in values))

    def probe_symbols(self, limit: int = 6) -> tuple[str, ...]:
        """Return a bounded stable set of exact operator-entered symbols."""
        if limit < 1:
            raise ValueError("limit must be positive")
        return tuple(contract.provider_symbol for contract in self.contracts[:limit])

    def redacted_dict(self) -> dict[str, object]:
        """Safe output for logs/UI: contract metadata only, no operator source payload."""
        return {
            "count": len(self.contracts),
            "contracts": [
                {
                    "provider_symbol": contract.provider_symbol,
                    "underlying": contract.underlying,
                    "expiry": contract.expiry.isoformat(),
                    "right": contract.right,
                    "strike": format(contract.strike, "f"),
                    "multiplier": format(contract.multiplier, "f") if contract.multiplier is not None else None,
                }
                for contract in self.contracts
            ],
        }


def _parse_contract(value: Mapping[str, object]) -> OptionContract:
    if not isinstance(value, Mapping):
        raise ContractListError("each contract must be an object")
    try:
        strike = _decimal(value["strike"], "strike")
        multiplier_raw = value.get("multiplier")
        multiplier = _decimal(multiplier_raw, "multiplier") if multiplier_raw is not None else None
        return OptionContract(
            provider_symbol=_text(value, "provider_symbol"),
            underlying=_text(value, "underlying").upper(),
            expiry=date.fromisoformat(_text(value, "expiry")),
            right=_text(value, "right").lower(),
            strike=strike,
            multiplier=multiplier,
        )
    except KeyError as error:
        raise ContractListError(f"missing required contract field: {error.args[0]}") from error
    except (InvalidOperation, ValueError) as error:
        raise ContractListError(str(error)) from error


def _text(value: Mapping[str, object], key: str) -> str:
    text = str(value[key]).strip()
    if not text:
        raise ContractListError(f"{key} is required")
    return text


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, float):
        raise ContractListError(f"{field} must be a decimal string or integer")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ContractListError(f"{field} must be decimal") from error
    return number
