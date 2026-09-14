from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    version: int
    max_incremental_loss: Decimal
    available_funds: Decimal
    max_position_age: timedelta = timedelta(seconds=60)
    max_quote_age: timedelta = timedelta(seconds=5)
    candidate_ttl: timedelta = timedelta(seconds=60)
    trim_fraction: Decimal = Decimal("0.5")
    allowed_strategies: frozenset[str] = frozenset({"trim_stock", "reduce_option", "protective_put", "debit_vertical"})

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("policy version must be positive")
        if not self.max_incremental_loss.is_finite() or self.max_incremental_loss <= 0:
            raise ValueError("max_incremental_loss must be positive")
        if not self.available_funds.is_finite() or self.available_funds < 0:
            raise ValueError("available_funds must be nonnegative")
        if not Decimal("0") < self.trim_fraction <= Decimal("1"):
            raise ValueError("trim_fraction must be in (0, 1]")
        if min(self.max_position_age, self.max_quote_age, self.candidate_ttl) <= timedelta(0):
            raise ValueError("freshness and expiry limits must be positive")
