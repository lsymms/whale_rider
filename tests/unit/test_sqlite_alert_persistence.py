from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.domain.notifications import DeliveryKind, DeliveryState, Notification
from backend.storage import Database, RuleConflict, RuleStore, SqliteOutbox


NOW = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)


def database(tmp_path: Path) -> Database:
    value = Database(tmp_path / "runtime" / "whale-rider.sqlite3")
    value.migrate()
    return value


def notice(identifier: str = "n-1") -> Notification:
    return Notification(identifier, f"key-{identifier}", DeliveryKind.ALERT, "chat", "synthetic", NOW, NOW + timedelta(minutes=5))


def test_rule_revisions_are_immutable_and_survive_restart(tmp_path: Path) -> None:
    first = RuleStore(database(tmp_path))
    created = first.create("r-1", {"template": "A01", "minimum_notional": "1000000"})
    revised = first.revise("r-1", 1, {"template": "A01", "minimum_notional": "2000000"})
    assert created.revision == 1 and created.payload["minimum_notional"] == "1000000"
    assert revised.revision == 2 and revised.payload["minimum_notional"] == "2000000"
    reloaded = RuleStore(database(tmp_path)).get("r-1")
    assert reloaded == revised
    with pytest.raises(RuleConflict, match="stale"):
        first.revise("r-1", 1, {"template": "A01"})


def test_pause_archive_and_dry_run_do_not_create_mutable_rule_state(tmp_path: Path) -> None:
    store = RuleStore(database(tmp_path))
    store.create("r-1", {"template": "A01"})
    assert store.pause("r-1", NOW + timedelta(minutes=1)).state == "paused"
    archived = store.archive("r-1")
    assert archived.state == "archived" and archived.paused_until is None
    with pytest.raises(RuleConflict, match="archived"):
        store.revise("r-1", archived.revision, {"template": "A02"})
    assert len(store.list()) == 1


def test_sqlite_outbox_recovers_lease_and_is_idempotent(tmp_path: Path) -> None:
    outbox = SqliteOutbox(database(tmp_path))
    saved = outbox.enqueue(notice())
    assert outbox.enqueue(Notification("other", saved.idempotency_key, DeliveryKind.ALERT, "chat", "other", NOW, NOW + timedelta(minutes=5))) == saved
    leased = outbox.lease_next(NOW, timedelta(seconds=1))
    assert leased is not None and leased.state is DeliveryState.LEASED and leased.attempts == 1
    reloaded = SqliteOutbox(database(tmp_path))
    assert reloaded.lease_next(NOW + timedelta(seconds=2)) is None
    assert reloaded.get("n-1").state is DeliveryState.UNKNOWN


def test_sqlite_outbox_retries_and_never_leases_expired_items(tmp_path: Path) -> None:
    outbox = SqliteOutbox(database(tmp_path))
    outbox.enqueue(notice())
    leased = outbox.lease_next(NOW)
    assert leased is not None
    retry = outbox.mark_failure(leased.notification_id, "transient", "offline", NOW)
    assert retry.state is DeliveryState.RETRY_WAIT and retry.due_at == NOW + timedelta(seconds=60)
    assert outbox.lease_next(NOW + timedelta(seconds=60)) is not None
    outbox.enqueue(Notification("expired", "expired-key", DeliveryKind.ALERT, "chat", "expired", NOW, NOW + timedelta(seconds=1)))
    assert outbox.lease_next(NOW + timedelta(minutes=10)) is None
    assert outbox.get("expired").state is DeliveryState.EXPIRED
