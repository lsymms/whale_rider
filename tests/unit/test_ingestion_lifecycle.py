from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from backend.workers.ingestion import OptionContract
from backend.workers.ingestion_lifecycle import IngestionLifecycle


@dataclass
class StockResult:
    appended_events: int = 2


@dataclass
class OptionResult:
    polled_contracts: int = 1


class FakeOperations:
    def __init__(self): self.calls = []
    def consume_stock_batch(self, symbols, max_messages): self.calls.append(("stock", tuple(symbols), max_messages)); return StockResult()
    def poll_options(self, contracts): self.calls.append(("options", tuple(item.instrument_id for item in contracts))); return OptionResult()


def test_lifecycle_has_no_startup_calls_and_stop_blocks_future_cycles():
    operations = FakeOperations()
    lifecycle = IngestionLifecycle(operations, now=lambda: datetime(2026, 9, 15, 14, 30, tzinfo=UTC))
    assert lifecycle.status().state == "stopped" and operations.calls == []
    started = lifecycle.start(["nvda", "NVDA"], [OptionContract("NVDA-C", "NVDA")])
    assert started.stock_symbols == ("NVDA",) and operations.calls == []
    running = lifecycle.run_once([OptionContract("NVDA-C", "NVDA")], max_stock_messages=5)
    assert running.last_stock == {"appended_events": 2} and operations.calls == [("stock", ("NVDA",), 5), ("options", ("NVDA-C",))]
    assert lifecycle.stop().state == "stopped"
    with pytest.raises(ValueError, match="not running"):
        lifecycle.run_once([])


def test_start_requires_explicit_injected_operations_and_valid_scope():
    with pytest.raises(ValueError, match="not configured"):
        IngestionLifecycle().start(["NVDA"], [])
    with pytest.raises(ValueError, match="at least one"):
        IngestionLifecycle(FakeOperations()).start([], [])
