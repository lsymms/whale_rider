"""A small crash-safe local notification outbox using atomic JSON replacement."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path


class DeliveryKind(StrEnum):
    TEST = "test"
    ALERT = "alert"


class DeliveryState(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    SENT = "sent"
    RETRY_WAIT = "retry_wait"
    UNKNOWN = "unknown"
    EXPIRED = "expired"
    DEAD = "dead"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class Notification:
    notification_id: str
    idempotency_key: str
    kind: DeliveryKind
    destination_id: str
    text: str
    created_at: datetime
    expires_at: datetime
    state: DeliveryState = DeliveryState.PENDING
    attempts: int = 0
    due_at: datetime | None = None
    lease_until: datetime | None = None
    external_message_id: str | None = None
    last_error: str | None = None

    def __post_init__(self) -> None:
        if not self.notification_id or not self.idempotency_key or not self.destination_id:
            raise ValueError("notification, idempotency, and destination IDs are required")
        if not self.text.strip():
            raise ValueError("notification text is required")
        created, expires = _utc(self.created_at), _utc(self.expires_at)
        if expires <= created:
            raise ValueError("expiry must be after creation")
        object.__setattr__(self, "created_at", created)
        object.__setattr__(self, "expires_at", expires)
        if self.due_at is not None:
            object.__setattr__(self, "due_at", _utc(self.due_at))
        if self.lease_until is not None:
            object.__setattr__(self, "lease_until", _utc(self.lease_until))


class DurableOutbox:
    """Single-process local persistence; a database outbox can replace this API later."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._items: dict[str, Notification] = {}
        self._load()

    def enqueue(self, item: Notification) -> Notification:
        existing = next((value for value in self._items.values() if value.idempotency_key == item.idempotency_key), None)
        if existing is not None:
            return existing
        self._items[item.notification_id] = item
        self._persist()
        return item

    def get(self, notification_id: str) -> Notification:
        return self._items[notification_id]

    def lease_next(self, now: datetime, lease_for: timedelta = timedelta(seconds=30)) -> Notification | None:
        now = _utc(now)
        changed = self._expire(now)
        candidates = []
        for item in self._items.values():
            if item.state == DeliveryState.LEASED and item.lease_until is not None and item.lease_until <= now:
                item = replace(item, state=DeliveryState.UNKNOWN, lease_until=None, last_error="lease expired before acknowledgement")
                self._items[item.notification_id] = item
                changed = True
            if item.state in {DeliveryState.PENDING, DeliveryState.RETRY_WAIT} and (item.due_at is None or item.due_at <= now):
                candidates.append(item)
        if candidates:
            selected = min(candidates, key=lambda item: (item.due_at or item.created_at, item.created_at, item.notification_id))
            leased = replace(selected, state=DeliveryState.LEASED, lease_until=now + lease_for, attempts=selected.attempts + 1)
            self._items[leased.notification_id] = leased
            self._persist()
            return leased
        if changed:
            self._persist()
        return None

    def mark_sent(self, notification_id: str, external_message_id: str) -> Notification:
        item = self.get(notification_id)
        if item.state != DeliveryState.LEASED:
            raise ValueError("only a leased notification can be sent")
        updated = replace(item, state=DeliveryState.SENT, lease_until=None, external_message_id=external_message_id, last_error=None)
        self._items[notification_id] = updated
        self._persist()
        return updated

    def mark_failure(self, notification_id: str, classification: str, error: str, now: datetime) -> Notification:
        item = self.get(notification_id)
        if item.state != DeliveryState.LEASED:
            raise ValueError("only a leased notification can fail")
        now = _utc(now)
        if classification == "timeout_after_send":
            state, due = DeliveryState.UNKNOWN, None
        elif classification == "transient":
            state, due = DeliveryState.RETRY_WAIT, now + timedelta(seconds=min(60 * 2 ** max(item.attempts - 1, 0), 900))
        else:
            state, due = DeliveryState.DEAD, None
        updated = replace(item, state=state, due_at=due, lease_until=None, last_error=error[:500])
        self._items[notification_id] = updated
        self._persist()
        return updated

    def _expire(self, now: datetime) -> bool:
        changed = False
        for identifier, item in list(self._items.items()):
            if item.state not in {DeliveryState.SENT, DeliveryState.DEAD, DeliveryState.EXPIRED} and item.expires_at <= now:
                self._items[identifier] = replace(item, state=DeliveryState.EXPIRED, lease_until=None)
                changed = True
        return changed

    def _load(self) -> None:
        if not self.path.exists():
            return
        records = json.loads(self.path.read_text(encoding="utf-8"))
        self._items = {record["notification_id"]: self._decode(record) for record in records}

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        records = [self._encode(item) for item in self._items.values()]
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(records, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        os.replace(temporary, self.path)

    @staticmethod
    def _encode(item: Notification) -> dict[str, object]:
        result = {field: getattr(item, field) for field in item.__dataclass_fields__}
        for key, value in result.items():
            if isinstance(value, (datetime, StrEnum)):
                result[key] = value.isoformat() if isinstance(value, datetime) else value.value
        return result

    @staticmethod
    def _decode(record: dict[str, object]) -> Notification:
        for field in ("created_at", "expires_at", "due_at", "lease_until"):
            if record.get(field) is not None:
                record[field] = datetime.fromisoformat(str(record[field]))
        record["kind"] = DeliveryKind(str(record["kind"]))
        record["state"] = DeliveryState(str(record["state"]))
        return Notification(**record)  # type: ignore[arg-type]
