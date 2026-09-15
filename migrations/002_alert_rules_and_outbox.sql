CREATE TABLE IF NOT EXISTS alert_rules (
    rule_id TEXT PRIMARY KEY,
    state TEXT NOT NULL CHECK(state IN ('active', 'paused', 'archived')),
    current_revision INTEGER NOT NULL CHECK(current_revision >= 1),
    paused_until TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alert_rule_revisions (
    rule_id TEXT NOT NULL REFERENCES alert_rules(rule_id),
    revision INTEGER NOT NULL CHECK(revision >= 1),
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(rule_id, revision)
);

CREATE TABLE IF NOT EXISTS notification_outbox (
    notification_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK(kind IN ('test', 'alert')),
    destination_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    due_at TEXT,
    lease_until TEXT,
    external_message_id TEXT,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS notification_outbox_due_idx ON notification_outbox(state, due_at, created_at);
