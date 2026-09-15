from datetime import datetime, timedelta, timezone

from backend.adapters.webull.market import StockTickStream, StreamDisconnected
from backend.domain.market import EventKind, Journal
from backend.workers.ingestion import OptionContract, OptionTickScheduler


NOW = datetime(2026, 9, 15, 14, 30, tzinfo=timezone.utc)


def tick(identifier: str, **changes):
    item = {"event_type": "execution", "execution_id": identifier, "identity_reliable": True, "symbol": "NVDA", "event_time": NOW.isoformat(), "quantity": "100", "price": "150"}
    item.update(changes)
    return item


class FakeSession:
    def __init__(self, messages): self.messages, self.closed, self.heartbeats = list(messages), False, 0
    def receive(self, timeout_seconds):
        value = self.messages.pop(0) if self.messages else None
        if value == "disconnect": raise StreamDisconnected()
        return value
    def heartbeat(self): self.heartbeats += 1; return True
    def close(self): self.closed = True


def test_stock_stream_normalizes_batches_and_records_reconnect_gap():
    journal, clock = Journal(), iter([NOW, NOW + timedelta(seconds=1), NOW + timedelta(seconds=2), NOW + timedelta(seconds=3)])
    session = FakeSession([{ "events": [tick("s-1"), {"event_type": "quote"}] }, "disconnect"])
    report = StockTickStream(lambda _: session, journal, lambda: next(clock)).consume(["NVDA"], max_messages=2)
    assert report.appended_events == 1 and report.reconnect_required and report.gaps_recorded == 1 and session.closed
    assert [event.kind for event in journal.replay()] == [EventKind.EXECUTION, EventKind.GAP]


def test_option_scheduler_bounds_requests_rotates_scope_and_reports_coverage():
    journal = Journal()
    calls = []
    scheduler = OptionTickScheduler(lambda contract: calls.append(contract.instrument_id) or [tick(contract.instrument_id)], journal, lambda: NOW, rate_limit_per_minute=12, requested_cycle_seconds=10)
    contracts = [OptionContract(f"NVDA-C-{index}", "NVDA") for index in range(4)]
    first, second = scheduler.poll_cycle(contracts), scheduler.poll_cycle(contracts)
    assert first.polled_contracts == 2 and first.skipped_contracts == 2 and first.effective_cycle_seconds == 20
    assert calls == ["NVDA-C-0", "NVDA-C-1", "NVDA-C-2", "NVDA-C-3"]
    assert len(journal.replay()) == 4


def test_option_poll_failure_records_visible_gap_without_raising():
    journal = Journal(); contract = OptionContract("NVDA-C", "NVDA")
    values = iter([NOW, NOW + timedelta(seconds=10)])
    scheduler = OptionTickScheduler(lambda _: (_ for _ in ()).throw(OSError("offline")), journal, lambda: next(values), rate_limit_per_minute=60, requested_cycle_seconds=10)
    report = scheduler.poll_cycle([contract])
    assert report.gaps_recorded == 0
    scheduler._last_success[contract.instrument_id] = NOW
    report = scheduler.poll_cycle([contract])
    assert report.gaps_recorded == 1 and journal.replay()[0].kind is EventKind.GAP
