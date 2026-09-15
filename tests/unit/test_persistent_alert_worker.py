from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.adapters.telegram import TelegramAdapter
from backend.domain.market import Journal, Provenance, SourceMode, normalize_execution
from backend.domain.notifications import DeliveryState
from backend.storage import Database, RuleStore, SqliteOutbox
from backend.workers.alert_evaluation import PersistentAlertWorker
from backend.workers.delivery import DeliveryWorker


NOW = datetime(2026, 9, 15, 14, 30, tzinfo=timezone.utc)


def database(tmp_path: Path) -> Database:
    value = Database(tmp_path / "runtime" / "whale-rider.sqlite3")
    value.migrate()
    return value


def stock_event(event_id: str = "trade-1"):
    return normalize_execution(
        {"instrument_id": "NVDA", "underlying": "NVDA", "asset_type": "stock", "event_time": NOW.isoformat(), "quantity": "10000", "quantity_unit": "shares", "price": "100"},
        Provenance("fixture", SourceMode.REPLAY, NOW, NOW, "hash-" + event_id, event_id, True),
    )


def rule() -> dict[str, object]:
    return {"template": "A01", "asset_type": "stock", "universe": ["NVDA"], "minimum_quantity": "10000", "minimum_notional": "1000000", "cooldown_seconds": 60, "destination_id": "test-chat", "expires_after_seconds": 120}


def test_persisted_active_rule_enqueues_once_and_cooldown_prevents_second_delivery(tmp_path: Path) -> None:
    db = database(tmp_path)
    RuleStore(db).create("large-nvda", rule())
    outbox = SqliteOutbox(db)
    worker = PersistentAlertWorker(RuleStore(db), outbox)
    journal = Journal()
    _, appended = journal.append(stock_event())
    first = worker.process_replay(journal, now=NOW)
    assert first[0].notification is not None and first[0].notification.state is DeliveryState.PENDING
    assert "intent unknown" in first[0].notification.text
    second = worker.process_event(appended, now=NOW + timedelta(seconds=1))
    assert second[0].notification is None and second[0].outcome is not None and second[0].outcome.code.value == "duplicate"
    restarted = PersistentAlertWorker(RuleStore(db), outbox)
    replayed_after_restart = restarted.process_event(appended, now=NOW + timedelta(seconds=2))
    assert replayed_after_restart[0].notification is not None
    assert replayed_after_restart[0].notification.notification_id == first[0].notification.notification_id
    assert outbox.lease_next(NOW) is not None
    assert outbox.lease_next(NOW) is None


def test_offline_fake_telegram_delivery_retries_then_sends(tmp_path: Path) -> None:
    db = database(tmp_path)
    RuleStore(db).create("large-nvda", rule())
    outbox = SqliteOutbox(db)
    worker = PersistentAlertWorker(RuleStore(db), outbox)
    journal = Journal()
    _, event = journal.append(stock_event())
    worker.process_event(event, now=NOW)
    attempts: list[str] = []

    def transport(destination: str, text: str) -> str:
        attempts.append(destination)
        if len(attempts) == 1:
            raise OSError("offline")
        return "fake-message-1"

    adapter = TelegramAdapter(transport, test_destination_id="test-chat", test_delivery_enabled=True, live_delivery_enabled=True)
    delivery = DeliveryWorker(outbox, adapter)  # type: ignore[arg-type]
    retry = delivery.deliver_one(NOW)
    assert retry is not None and retry.state is DeliveryState.RETRY_WAIT
    sent = delivery.deliver_one(NOW + timedelta(seconds=60))
    assert sent is not None and sent.state is DeliveryState.SENT and sent.external_message_id == "fake-message-1"
    assert attempts == ["test-chat", "test-chat"]


def test_gap_and_paused_rules_never_enqueue(tmp_path: Path) -> None:
    db = database(tmp_path)
    store = RuleStore(db)
    store.create("large-nvda", rule())
    store.pause("large-nvda")
    outbox = SqliteOutbox(db)
    worker = PersistentAlertWorker(store, outbox)
    journal = Journal()
    gap = journal.record_gap(instrument_id="NVDA", underlying="NVDA", asset_type="stock", start=NOW, end=NOW + timedelta(seconds=2), reason="fixture_gap", provenance=Provenance("fixture", SourceMode.REPLAY, NOW, NOW, "gap"))
    assert worker.process_event(gap, now=NOW)[0].skipped_reason == "gap_not_evaluable"
    _, event = journal.append(stock_event())
    paused = worker.process_event(event, now=NOW)
    assert paused[0].skipped_reason == "rule_inactive"
    assert outbox.lease_next(NOW) is None
