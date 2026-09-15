"""SQLite repositories for immutable rule revisions and durable delivery state."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from backend.domain.notifications import DeliveryState, Notification
from backend.domain.notifications.outbox import DeliveryKind

from .database import Database


class RuleNotFound(KeyError):
    pass


class RuleConflict(ValueError):
    pass


def _time(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _read_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


@dataclass(frozen=True, slots=True)
class StoredRule:
    rule_id: str
    revision: int
    state: str
    paused_until: datetime | None
    payload: Mapping[str, Any]


class RuleStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, rule_id: str, payload: Mapping[str, Any]) -> StoredRule:
        if not rule_id:
            raise ValueError("rule_id is required")
        encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"))
        with self._database.connect() as connection:
            try:
                connection.execute("INSERT INTO alert_rules(rule_id, state, current_revision) VALUES (?, 'active', 1)", (rule_id,))
                connection.execute("INSERT INTO alert_rule_revisions(rule_id, revision, payload_json) VALUES (?, 1, ?)", (rule_id, encoded))
            except Exception as error:
                if "UNIQUE" in str(error).upper():
                    raise RuleConflict("rule_id already exists") from error
                raise
        return self.get(rule_id)

    def get(self, rule_id: str) -> StoredRule:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT r.rule_id, r.current_revision, r.state, r.paused_until, v.payload_json FROM alert_rules r JOIN alert_rule_revisions v ON v.rule_id=r.rule_id AND v.revision=r.current_revision WHERE r.rule_id=?",
                (rule_id,),
            ).fetchone()
        if row is None:
            raise RuleNotFound(rule_id)
        return StoredRule(row["rule_id"], row["current_revision"], row["state"], _read_time(row["paused_until"]), json.loads(row["payload_json"]))

    def list(self) -> tuple[StoredRule, ...]:
        with self._database.connect() as connection:
            ids = [row[0] for row in connection.execute("SELECT rule_id FROM alert_rules ORDER BY created_at, rule_id")]
        return tuple(self.get(rule_id) for rule_id in ids)

    def revise(self, rule_id: str, expected_revision: int, payload: Mapping[str, Any]) -> StoredRule:
        encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"))
        with self._database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT current_revision, state FROM alert_rules WHERE rule_id=?", (rule_id,)).fetchone()
            if row is None:
                raise RuleNotFound(rule_id)
            if row["state"] == "archived":
                raise RuleConflict("archived rules cannot be revised")
            if row["current_revision"] != expected_revision:
                raise RuleConflict(f"stale rule revision: expected {expected_revision}, current {row['current_revision']}")
            next_revision = expected_revision + 1
            connection.execute("INSERT INTO alert_rule_revisions(rule_id, revision, payload_json) VALUES (?, ?, ?)", (rule_id, next_revision, encoded))
            connection.execute("UPDATE alert_rules SET current_revision=?, updated_at=CURRENT_TIMESTAMP WHERE rule_id=?", (next_revision, rule_id))
        return self.get(rule_id)

    def pause(self, rule_id: str, until: datetime | None = None) -> StoredRule:
        with self._database.connect() as connection:
            result = connection.execute("UPDATE alert_rules SET state='paused', paused_until=?, updated_at=CURRENT_TIMESTAMP WHERE rule_id=? AND state != 'archived'", (_time(until) if until else None, rule_id))
        if result.rowcount != 1:
            if self._exists(rule_id):
                raise RuleConflict("archived rules cannot be paused")
            raise RuleNotFound(rule_id)
        return self.get(rule_id)

    def archive(self, rule_id: str) -> StoredRule:
        with self._database.connect() as connection:
            result = connection.execute("UPDATE alert_rules SET state='archived', paused_until=NULL, updated_at=CURRENT_TIMESTAMP WHERE rule_id=?", (rule_id,))
        if result.rowcount != 1:
            raise RuleNotFound(rule_id)
        return self.get(rule_id)

    def _exists(self, rule_id: str) -> bool:
        with self._database.connect() as connection:
            return connection.execute("SELECT 1 FROM alert_rules WHERE rule_id=?", (rule_id,)).fetchone() is not None


class SqliteOutbox:
    def __init__(self, database: Database) -> None:
        self._database = database

    def enqueue(self, item: Notification) -> Notification:
        with self._database.connect() as connection:
            existing = connection.execute("SELECT * FROM notification_outbox WHERE idempotency_key=?", (item.idempotency_key,)).fetchone()
            if existing is not None:
                return self._decode(existing)
            connection.execute(
                "INSERT INTO notification_outbox(notification_id,idempotency_key,kind,destination_id,text,created_at,expires_at,state,attempts,due_at,lease_until,external_message_id,last_error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (item.notification_id, item.idempotency_key, item.kind.value, item.destination_id, item.text, _time(item.created_at), _time(item.expires_at), item.state.value, item.attempts, _time(item.due_at) if item.due_at else None, _time(item.lease_until) if item.lease_until else None, item.external_message_id, item.last_error),
            )
        return item

    def get(self, notification_id: str) -> Notification:
        with self._database.connect() as connection:
            row = connection.execute("SELECT * FROM notification_outbox WHERE notification_id=?", (notification_id,)).fetchone()
        if row is None:
            raise KeyError(notification_id)
        return self._decode(row)

    def lease_next(self, now: datetime, lease_for: timedelta = timedelta(seconds=30)) -> Notification | None:
        now_value = _time(now)
        with self._database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("UPDATE notification_outbox SET state='expired', lease_until=NULL WHERE state NOT IN ('sent','dead','expired') AND expires_at <= ?", (now_value,))
            connection.execute("UPDATE notification_outbox SET state='unknown', lease_until=NULL, last_error='lease expired before acknowledgement' WHERE state='leased' AND lease_until <= ?", (now_value,))
            row = connection.execute("SELECT * FROM notification_outbox WHERE state IN ('pending','retry_wait') AND (due_at IS NULL OR due_at <= ?) AND expires_at > ? ORDER BY COALESCE(due_at, created_at), created_at, notification_id LIMIT 1", (now_value, now_value)).fetchone()
            if row is None:
                return None
            until = _time(now + lease_for)
            connection.execute("UPDATE notification_outbox SET state='leased', attempts=attempts+1, lease_until=? WHERE notification_id=?", (until, row["notification_id"]))
            row = connection.execute("SELECT * FROM notification_outbox WHERE notification_id=?", (row["notification_id"],)).fetchone()
        return self._decode(row)

    def mark_sent(self, notification_id: str, external_message_id: str) -> Notification:
        return self._transition(notification_id, "sent", external_message_id=external_message_id)

    def mark_failure(self, notification_id: str, classification: str, error: str, now: datetime) -> Notification:
        item = self.get(notification_id)
        if item.state is not DeliveryState.LEASED:
            raise ValueError("only a leased notification can fail")
        if classification == "timeout_after_send":
            return self._transition(notification_id, "unknown", error=error)
        if classification == "transient":
            due = now + timedelta(seconds=min(60 * 2 ** max(item.attempts - 1, 0), 900))
            return self._transition(notification_id, "retry_wait", error=error, due_at=due)
        return self._transition(notification_id, "dead", error=error)

    def _transition(self, notification_id: str, state: str, *, external_message_id: str | None = None, error: str | None = None, due_at: datetime | None = None) -> Notification:
        with self._database.connect() as connection:
            result = connection.execute("UPDATE notification_outbox SET state=?, lease_until=NULL, due_at=?, external_message_id=COALESCE(?, external_message_id), last_error=? WHERE notification_id=? AND state='leased'", (state, _time(due_at) if due_at else None, external_message_id, error[:500] if error else None, notification_id))
        if result.rowcount != 1:
            raise ValueError("only a leased notification can transition")
        return self.get(notification_id)

    @staticmethod
    def _decode(row: Any) -> Notification:
        return Notification(row["notification_id"], row["idempotency_key"], DeliveryKind(row["kind"]), row["destination_id"], row["text"], _read_time(row["created_at"]), _read_time(row["expires_at"]), DeliveryState(row["state"]), row["attempts"], _read_time(row["due_at"]), _read_time(row["lease_until"]), row["external_message_id"], row["last_error"])
