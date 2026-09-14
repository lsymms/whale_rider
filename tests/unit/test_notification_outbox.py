from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.adapters.telegram import DeliveryRejected, TelegramAdapter
from backend.domain.notifications import DeliveryKind, DeliveryState, DurableOutbox, Notification
from backend.workers.delivery import DeliveryWorker


NOW = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)


def notice(identifier: str = "n-1", kind: DeliveryKind = DeliveryKind.ALERT, **changes: object) -> Notification:
    values: dict[str, object] = {
        "notification_id": identifier, "idempotency_key": f"key-{identifier}", "kind": kind, "destination_id": "chat-1",
        "text": "synthetic message", "created_at": NOW, "expires_at": NOW + timedelta(minutes=5),
    }
    values.update(changes)
    return Notification(**values)  # type: ignore[arg-type]


def test_outbox_persists_idempotently_and_leases_once(tmp_path: Path) -> None:
    path = tmp_path / "outbox.json"
    outbox = DurableOutbox(path)
    saved = outbox.enqueue(notice())
    assert outbox.enqueue(notice("n-2", idempotency_key=saved.idempotency_key)) == saved
    reloaded = DurableOutbox(path)
    leased = reloaded.lease_next(NOW)
    assert leased is not None and leased.state is DeliveryState.LEASED and leased.attempts == 1
    assert DurableOutbox(path).get("n-1").state is DeliveryState.LEASED


def test_expired_notifications_are_never_leased(tmp_path: Path) -> None:
    outbox = DurableOutbox(tmp_path / "outbox.json")
    outbox.enqueue(notice(expires_at=NOW + timedelta(seconds=1)))
    assert outbox.lease_next(NOW + timedelta(seconds=1)) is None
    assert outbox.get("n-1").state is DeliveryState.EXPIRED


def test_timeout_is_unknown_and_network_failure_retries(tmp_path: Path) -> None:
    outbox = DurableOutbox(tmp_path / "outbox.json")
    outbox.enqueue(notice())
    leased = outbox.lease_next(NOW)
    assert leased is not None
    assert outbox.mark_failure(leased.notification_id, "timeout_after_send", "timed out", NOW).state is DeliveryState.UNKNOWN
    outbox.enqueue(notice("n-2"))
    leased = outbox.lease_next(NOW)
    assert leased is not None
    retry = outbox.mark_failure(leased.notification_id, "transient", "offline", NOW)
    assert retry.state is DeliveryState.RETRY_WAIT and retry.due_at == NOW + timedelta(seconds=60)


def test_test_and_live_delivery_have_separate_explicit_guards() -> None:
    calls: list[tuple[str, str]] = []
    adapter = TelegramAdapter(lambda destination, text: calls.append((destination, text)) or "42", test_destination_id="test-chat", test_delivery_enabled=True, live_delivery_enabled=False)
    with pytest.raises(DeliveryRejected):
        adapter.deliver(notice())
    with pytest.raises(DeliveryRejected):
        adapter.deliver(notice(kind=DeliveryKind.TEST))
    test_notice = notice(kind=DeliveryKind.TEST, destination_id="test-chat")
    assert adapter.deliver(test_notice) == "42"
    assert calls == [("test-chat", "synthetic message")]


def test_worker_never_calls_transport_for_disabled_live_delivery(tmp_path: Path) -> None:
    calls: list[str] = []
    outbox = DurableOutbox(tmp_path / "outbox.json")
    outbox.enqueue(notice())
    adapter = TelegramAdapter(lambda *_: calls.append("sent") or "42", test_destination_id="chat-1", test_delivery_enabled=True, live_delivery_enabled=False)
    result = DeliveryWorker(outbox, adapter).deliver_one(NOW)
    assert result is not None and result.state is DeliveryState.DEAD
    assert calls == []


def test_worker_delivers_explicit_test_only_with_fake_transport(tmp_path: Path) -> None:
    outbox = DurableOutbox(tmp_path / "outbox.json")
    outbox.enqueue(notice(kind=DeliveryKind.TEST, destination_id="test-chat"))
    adapter = TelegramAdapter(lambda *_: "telegram-123", test_destination_id="test-chat", test_delivery_enabled=True, live_delivery_enabled=False)
    result = DeliveryWorker(outbox, adapter).deliver_one(NOW)
    assert result is not None and result.state is DeliveryState.SENT and result.external_message_id == "telegram-123"
