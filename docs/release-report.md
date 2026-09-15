# MVP release report

**Report date:** September 14, 2026.  
**Status:** local engineering MVP; not approved for unattended or live-trading operation.

## Implemented and testable locally

| Area | Present behavior | Limits |
| --- | --- | --- |
| Local service and UI | Loopback FastAPI service serves the built React dashboard and local REST routes. | No local authentication, background service, backup/restore, or production deployment evidence yet. |
| Alert rules | Decimal A01â€“A04 evaluation, replay journal, reliable-ID dedupe, corrections/gaps, and dry-run API. | No authenticated live stream/poller feeding the journal; alerts are not connected to a durable database/outbox route. |
| Webull access | Token helper and allowlisted read-only capability probe with redacted evidence. | Current stock/options probes showed market-data subscription unavailable; no cadence or OPRA coverage verification. |
| Telegram | Durable local JSON outbox state model, leases/retries, and an adapter that separates TEST from live delivery. | There is no scheduled worker or configured production route in the service. Live alert delivery remains disabled by default. |
| Positions and exposure | Versioned manual/OCR-style drafts, review block, partial-import preservation, deterministic delta exposure, and deterministic candidate suggestions. | State is currently in-memory through the API facade. OCR and account import have no persisted production workflow. |
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
- The full regression runner is supplied but has not been recorded as a clean end-to-end execution in this report. Its result should be captured before any local operator acceptance.
- The previous mapped-workspace virtual environment was unsuitable for dependable dependency execution: pytest was absent and package/import commands stalled. The new host-local runner addresses that environment issue.

## Required before an operator release

1. Run the full regression command and retain the output.
2. Verify Webull stock entitlement and OPRA real-time non-display access with measured field coverage/cadence using the redacted capability workflow.
3. Run one deliberately configured Telegram TEST from the local service and verify delivery timeline/retry behavior using fakes for rate/error cases.
4. Replace in-memory API state and JSON notification storage with migrations, a single-writer durable store, session/CSRF/origin protections, retention, backup, and restore tests.
5. Complete representative held-out OCR and AI evaluation sets, including incomplete positions, stale quotes, prompt injection, unsupported strategies, and policy/version invalidation.
6. Observe at least five active sessions with visible feed gaps, latency, alert noise, option coverage, and no unintended live delivery.

The implementation plan's G0â€“G6 acceptance gates remain the release authority. Passing the current local regression suite demonstrates deterministic behavior against fakes and fixtures; it does not demonstrate live market-data completeness or a trading edge.
