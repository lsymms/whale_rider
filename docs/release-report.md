# MVP release report

**Report date:** September 15, 2026.
**Status:** local engineering MVP; not approved for unattended or live-trading operation.

## Implemented and testable locally

| Area | Present behavior | Limits |
| --- | --- | --- |
| Local service and UI | Loopback FastAPI service serves the built React dashboard and local REST routes. | No local authentication, background service, backup/restore, or production deployment evidence yet. |
| Alert rules | Decimal A01â€“A04 evaluation, replay journal, reliable-ID dedupe, corrections/gaps, persistent rule revisions, SQLite outbox enqueueing, and dry-run API. | The live ingestion worker is not scheduled/supervised as a local service yet; alert history is not exposed in the UI. |
| Webull access | A production read-only capability probe completed authenticated account, stock snapshot, and option snapshot checks on September 15. The probe is allowlisted and emits only redacted status/evidence metadata. | Endpoint reachability does not prove real-time OPRA rights, tick semantics, complete universe coverage, or observed cadence. Those remain activation gates. |
| Telegram | SQLite outbox leases/retries plus a TEST-versus-live guarded adapter and offline fake-transport delivery coverage. | There is no configured/scheduled production delivery route in the running service. Live alert delivery remains disabled until an operator enables it deliberately. |
| Positions and exposure | Versioned manual/OCR-style drafts, review block, partial-import preservation, deterministic delta exposure, and deterministic candidate suggestions. | API-facade position drafts remain in-memory; account refresh/import persistence and UI history are incomplete. |
| AI | OpenRouter adapters, OCR normalization, deterministic candidate policy/sizing, and explanation validation are represented in code/tests. | No held-out OCR/AI evaluation set, cost controls, or production model run evidence is included in this release. |

No brokerage order, preview, cancel, account-write, or automatic trade execution path is implemented by this MVP.

## Regression command

Run from PowerShell:

```powershell
./scripts/run-regression.ps1
```

The runner installs Python packages in `%LOCALAPPDATA%\WhaleRider\regression\python-deps`, mirrors `frontend/` to `%LOCALAPPDATA%\WhaleRider\regression\frontend`, and runs `npm ci`, frontend tests/build, Python unit/replay/e2e tests, design validation, and JavaScript contract tests. This avoids using Python or npm dependency trees from the mapped workspace. Use `-KeepFrontendMirror` to retain the local UI build for inspection. The runner does not load `.env`, call Webull/OpenRouter, or send Telegram messages.

## Evidence recorded in this change

- Static source compilation and focused fake-adapter/domain tests passed while implementing each component.
- The production Webull probe was a read-only endpoint check. Its redacted result establishes that the stock and option snapshot requests completed; it did not ingest a live event, send Telegram, or submit a brokerage order.
- The full regression runner is supplied but its clean output should be retained before any local operator acceptance.
- The previous mapped-workspace virtual environment was unsuitable for dependable dependency execution: pytest was absent and package/import commands stalled. The new host-local runner addresses that environment issue.

## Required before an operator release

1. Run the full regression command and retain the output.
2. Measure Webull stock and OPRA real-time entitlement, event fields, reconnect behavior, option scope coverage, and p50/p95 cadence. The verified snapshot probe does not satisfy these measurements.
3. Add a supervised live-worker schedule and service lifecycle that starts/restarts ingestion and delivery, surfaces health/gaps, and does not create duplicate routes.
4. Add UI alert history, delivery status, and coverage/freshness views, then exercise them with browser recovery tests.
5. Run one deliberately configured Telegram TEST from the local service and verify delivery timeline/retry behavior using fakes for rate/error cases.
6. Replace in-memory API state with a single-writer durable store, then add session/CSRF/origin protections, retention, backup, and restore tests.
7. Complete representative held-out OCR and AI evaluation sets, including incomplete positions, stale quotes, prompt injection, unsupported strategies, and policy/version invalidation.
8. Observe at least five active sessions with visible feed gaps, latency, alert noise, option coverage, and no unintended live delivery.

The implementation plan's G0â€“G6 acceptance gates remain the release authority. Passing the current local regression suite demonstrates deterministic behavior against fakes and fixtures; it does not demonstrate live market-data completeness or a trading edge.
