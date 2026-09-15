"""Bounded read-only option polling and stock stream orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

from backend.adapters.webull.market import StockTickStream, normalize_webull_tick
from backend.domain.market import Journal, Provenance, SourceMode


@dataclass(frozen=True, slots=True)
class OptionContract:
    instrument_id: str
    underlying: str


@dataclass(frozen=True, slots=True)
class PollCoverage:
    requested_contracts: int
    polled_contracts: int
    skipped_contracts: int
    rate_limit_per_minute: int
    requested_cycle_seconds: float
    effective_cycle_seconds: float
    appended_events: int
    gaps_recorded: int


class OptionTickScheduler:
    def __init__(self, fetch_ticks: Callable[[OptionContract], Sequence[Mapping[str, Any]]], journal: Journal, now: Callable[[], datetime], *, rate_limit_per_minute: int = 48, requested_cycle_seconds: float = 10) -> None:
        if rate_limit_per_minute < 1 or requested_cycle_seconds <= 0:
            raise ValueError("positive polling limits are required")
        self._fetch, self._journal, self._now = fetch_ticks, journal, now
        self._limit, self._requested, self._cursor = rate_limit_per_minute, requested_cycle_seconds, 0
        self._last_success: dict[str, datetime] = {}

    def poll_cycle(self, contracts: Sequence[OptionContract]) -> PollCoverage:
        if not contracts:
            return PollCoverage(0, 0, 0, self._limit, self._requested, self._requested, 0, 0)
        effective = max(self._requested, 60 * len(contracts) / self._limit)
        permitted = max(1, int(self._limit * self._requested // 60))
        count = min(len(contracts), permitted)
        selected = [contracts[(self._cursor + index) % len(contracts)] for index in range(count)]
        self._cursor = (self._cursor + count) % len(contracts)
        appended = gaps = 0
        for contract in selected:
            now = self._now()
            try:
                ticks = self._fetch(contract)
            except OSError:
                start = self._last_success.get(contract.instrument_id, now)
                if now > start:
                    self._journal.record_gap(instrument_id=contract.instrument_id, underlying=contract.underlying, asset_type="option", start=start, end=now, reason="option_poll_failed", provenance=Provenance("webull", SourceMode.POLLED, None, now, f"poll-failure:{contract.instrument_id}"))
                    gaps += 1
                continue
            for tick in ticks:
                try:
                    event = normalize_webull_tick(tick, asset_type="option", received_at=now, source_mode=SourceMode.POLLED, instrument_id=contract.instrument_id, underlying=contract.underlying)
                except ValueError:
                    continue
                if self._journal.append(event)[0].value == "appended":
                    appended += 1
            self._last_success[contract.instrument_id] = now
        return PollCoverage(len(contracts), len(selected), len(contracts) - len(selected), self._limit, self._requested, effective, appended, gaps)


class IngestionWorker:
    def __init__(self, stock_stream: StockTickStream, option_scheduler: OptionTickScheduler) -> None:
        self.stock_stream, self.option_scheduler = stock_stream, option_scheduler

    def consume_stock_batch(self, symbols: Sequence[str], max_messages: int):
        return self.stock_stream.consume(symbols, max_messages=max_messages)

    def poll_options(self, contracts: Sequence[OptionContract]) -> PollCoverage:
        return self.option_scheduler.poll_cycle(contracts)
