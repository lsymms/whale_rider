"""Explicit lifecycle control for injected, read-only ingestion operations."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, Sequence

from .ingestion import OptionContract


class IngestionOperations(Protocol):
    def consume_stock_batch(self, symbols: Sequence[str], max_messages: int) -> Any: ...
    def poll_options(self, contracts: Sequence[OptionContract]) -> Any: ...


@dataclass(frozen=True, slots=True)
class IngestionStatus:
    state: str
    stock_symbols: tuple[str, ...]
    option_contracts: tuple[str, ...]
    started_at: datetime | None
    stopped_at: datetime | None
    last_stock: dict[str, Any] | None
    last_options: dict[str, Any] | None

    def view(self) -> dict[str, Any]:
        result = asdict(self)
        for key in ("started_at", "stopped_at"):
            if result[key] is not None:
                result[key] = result[key].isoformat()
        return result


class IngestionLifecycle:
    """Does not open a feed, spawn a thread, or contact Webull until run_once is called."""

    def __init__(self, operations: IngestionOperations | None = None, now: callable | None = None) -> None:
        self._operations, self._now = operations, now or (lambda: datetime.now(UTC))
        self._status = IngestionStatus("stopped", (), (), None, None, None, None)

    def status(self) -> IngestionStatus:
        return self._status

    def start(self, stock_symbols: Sequence[str], option_contracts: Sequence[OptionContract]) -> IngestionStatus:
        if self._operations is None:
            raise ValueError("ingestion operations are not configured")
        symbols = tuple(dict.fromkeys(symbol.strip().upper() for symbol in stock_symbols if symbol.strip()))
        if not symbols:
            raise ValueError("at least one stock symbol is required")
        ids = [contract.instrument_id for contract in option_contracts]
        if len(ids) != len(set(ids)):
            raise ValueError("option contract identifiers must be unique")
        self._status = IngestionStatus("running", symbols, tuple(ids), self._now(), None, None, None)
        return self._status

    def stop(self) -> IngestionStatus:
        self._status = IngestionStatus("stopped", self._status.stock_symbols, self._status.option_contracts, self._status.started_at, self._now(), self._status.last_stock, self._status.last_options)
        return self._status

    def run_once(self, option_contracts: Sequence[OptionContract], *, max_stock_messages: int = 25) -> IngestionStatus:
        if self._status.state != "running":
            raise ValueError("ingestion is not running")
        assert self._operations is not None
        stock = self._operations.consume_stock_batch(self._status.stock_symbols, max_stock_messages)
        options = self._operations.poll_options(option_contracts)
        self._status = IngestionStatus("running", self._status.stock_symbols, self._status.option_contracts, self._status.started_at, None, asdict(stock), asdict(options))
        return self._status
