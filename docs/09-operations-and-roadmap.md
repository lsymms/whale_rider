# Operations and delivery

## Host and storage

Run one supervised local service serving the compiled UI; a Windows background service/task or equivalent host service handles restart. Docker is optional later.

The user confirms the storage is physically attached to the host. **Use that disk's native local path when the app runs on that host.** If this workstation reaches the disk through W:/SMB, use native local storage on the workstation or run the backend on the storage host. Physical attachment and the process's filesystem access path are separate deployment facts. Resolve the native path during setup.

Default binding is 127.0.0.1. A browser on another computer requires an explicit LAN deployment with authentication, TLS, firewall restrictions and reachable hostname. No public exposure by default.

## Setup and daily use

1. Install pinned dependencies and build the UI on the intended host.
2. Choose native runtime storage and validate filesystem/permissions/free space.
3. Configure local login and protected secret storage.
4. Add the existing Webull key, matching secret and applicable account authentication.
5. Probe capabilities; enable the intended OPRA Real-Time Non-display subscription if absent, then rerun.
6. Configure Telegram and deliberately send a test.
7. Configure AI provider/local endpoint, cloud-image preference and usage budget.
8. Select account, reconcile holdings/funds, set risk limits.
9. Review scope/cadence and enable starter rules.
10. Before each session check health/positions; reconcile after trading and review alert noise.

Internet is needed for Webull/Telegram and cloud AI if selected. Closing the browser does not stop monitoring; host sleep/shutdown does. Show premarket readiness and last-alive time. An external watchdog is a later feature because a failed host cannot report its own outage.

## Secrets and access

Use an OS credential vault or encrypted store with a master key outside Git/database. Separate Webull, Telegram and AI credentials. Never return saved secrets to the browser. Redact token-bearing Telegram URLs, headers, signed requests, account IDs and model payloads in logs.

Use local authentication, HTTP-only session cookies, CSRF/origin/host validation and login throttling. LAN access requires TLS/secure cookies. Custom AI URLs are deliberately configured allowlisted destinations; imported data cannot supply arbitrary request targets.

The Webull adapter allows reads, subscriptions and authentication only. Do not assume a provider read-only key scope exists; enforce the application's boundary even when the credential could trade.

## Retention and backups

Defaults: normalized ticks 24h with size cap; aggregates/alerts/positions/audit 90d; committed screenshots 24h; abandoned imports 7d. Raw capture is off unless needed and permitted. Show retention boundaries.

At 500 events/sec and an illustrative 300 bytes/event, payload alone is 12.96GB/day before indexes. Dense continuous capture needs measured storage capacity. Bound retention, prune, show pruning boundaries, and reserve free disk space.

Create consistent database backups, encrypt and verify them, then copy completed archives to the attached share if desired. Do not copy a changing database alone. Retain seven daily backups by default and test restoration; backup deletion policy is separate from live-image deletion.

Targets: committed state survives a process crash; storage-loss recovery point ≤24h with daily backup; practiced restore ≤30min. These are proposed targets, not measured results for this design.

## Health and recovery

Metrics: feed/poll heartbeat, event/report lag, per-contract cycle, gaps, scope failures, rule lag, intake backlog, identity ambiguity, outbox depth/oldest age, delivery errors, OCR unresolved rows, AI latency/cost/rejections, disk space and last backup.

- Authentication failure: preserve state; suspend affected reads and request local reauthentication.
- Missing entitlement: disable dependent rules; retain unrelated workflows.
- Reconnection: restore subscriptions, recover only supported gaps, warm up continuous windows.
- Telegram failure: local alerts persist, retries bounded, expired trade messages stay in history.
- AI failure: deterministic facts remain available; cancel stale queued work.
- Storage unavailable: stop writes/monitoring; never silently create a new blank database elsewhere.
- OCR conflict: preserve draft/current book and rebase through review.

## Roadmap and cost

M0 capability proof → M1 local foundation → M2 ingestion/rules → M3 Telegram/UI → M4 positions/exposure/OCR → M5 AI suggestions → M6 hardening and observation. The [detailed implementation plan](11-mvp-implementation-plan.md) supplies tasks and exit gates.

Costs are OpenAPI data subscriptions, optional AI use, host compute/storage and backups. Confirm prices in Webull's portal and the chosen AI provider at implementation; an existing key is not proof of included subscriptions.

If options polling cannot meet the desired scope/latency, narrow the universe, explicitly accept a slower mode, verify streaming, or consider another licensed feed. Full-market options surveillance is a separate scope/cost decision.
