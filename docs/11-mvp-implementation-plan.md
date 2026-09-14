# MVP implementation plan

The complete MVP includes **stock and option alerts, Telegram, rule management, API/manual/screenshot positions, AI OCR, deterministic exposure, and AI trade suggestions**. This is a build plan; the production app is not implemented by this design package.

## Sequence and effort

Estimate for one experienced engineer: **24–37 engineering days**, plus subscription/access wait and at least five market sessions of observation, which may overlap hardening. Re-estimate after M0. Options completeness and model integration are the main uncertainties.

Critical path: access proof → normalized data/quality → alerts/outbox → complete positions/exposure → validated AI → end-to-end/release evidence. UI follows stable contracts. Configure credentials locally when needed.

## M0: Prove access and contracts — 2–3 days

| Task | Deliverable | Acceptance |
| --- | --- | --- |
| P00.1 Select backend host and native storage path | Local deployment configuration | Runtime uses native filesystem, even if docs stay on W: |
| P00.2 Use existing key/secret | Protected credentials and read-only probe | Classify auth/token/access result |
| P00.3 Verify stock and OPRA access | Redacted capability report and fixtures | Parse stock and option ticks/snapshots with verified time/units |
| P00.4 Test option retrieval/cadence | Six-contract cycle and overlap/pagination report | Completeness bounds and actual latency recorded |
| P00.5 Validate instruments/accounts | Metadata and positions/balance fixtures | Identity, sign, multiplier/deliverable and completeness known |

Proposed files: `backend/adapters/webull/probe.py`, `capabilities.py`, `tests/fixtures/webull/`, redacted `docs/capability-report.md`.

Exit G0: minimum data contracts are understood. Configure the intended OPRA subscription if absent and rerun. If complete timely option retrieval is impossible, narrow scope or resolve the data source before advertising the full MVP. A subscription confirmation alone is insufficient.

## M1: Local foundation — 2–3 days

| Task | Deliverable | Acceptance |
| --- | --- | --- |
| P01.1 Package service/UI | FastAPI and React/TypeScript, pinned lockfiles | One command starts loopback app and compiled UI |
| P01.2 Storage/migrations | SQLite schema and single writer | Restart retains data; invalid runtime path rejected |
| P01.3 Authentication/secrets | Local session, CSRF/origin checks, vault | No secrets in bundle, logs or regular database fields |
| P01.4 Domain contracts | Typed events/rules/positions/alerts | Invalid types/units rejected with stable errors |
| P01.5 Offline mode | Fake adapters and virtual clock | Replay makes no external calls or production sends |

Files: `backend/app.py`, `backend/api/`, `backend/storage/`, `backend/domain/contracts.py`, `migrations/`, `frontend/src/`, `tests/fakes/`.

Exit: clean installation starts app, migrates local storage and passes meaningful contract tests.

## M2: Ingestion and alert engine — 4–6 days

| Task | Deliverable | Acceptance |
| --- | --- | --- |
| P02.1 Stock stream | Subscription, batches, heartbeat and reconnect | Quotes never treated as trades; gaps visible |
| P02.2 Option polling | Pinned universe, quotas, overlap/pages | Actual cycle displayed; no silent truncation/eviction |
| P02.3 Normalize/journal | Decimal units, provenance, time and offset | Golden calculations and recovery tests pass |
| P02.4 Identity/windows | Dedup, reorder, correction and gap handling | Identical legitimate prints preserved; ambiguous clusters disabled |
| P02.5 Rules | A01–A04 and health notices, cooldown/escalation | Correct boundaries and replay isolation |
| P02.6 Scope UI | Monitoring/capability views | Oversized universe exposes achievable delay |

Files: `backend/adapters/webull/market.py`, `backend/workers/ingestion.py`, `backend/domain/alerts/`, `frontend/src/pages/Overview.tsx`, `tests/replay/`.

Exit G1/G2: stream/poll fixtures produce explainable alerts and selected option scope meets its stated contract. Notional option alerts do not need invented side inference.

## M3: Telegram and alert management — 3–4 days

| Task | Deliverable | Acceptance |
| --- | --- | --- |
| P03.1 Durable outbox | Lease/retry/expiry/unknown states | Crash and ambiguous-timeout tests pass |
| P03.2 Telegram | Destination/topic configuration and TEST action | Deliberate test received; token URLs redacted |
| P03.3 Noise budget | Group cap, priority, digest, quiet hours | Bursts capped; expired trades do not flood |
| P03.4 Rule UI/API | CRUD, immutable revisions and dry-run | Pause/duplicate/archive and conflict handling work |
| P03.5 History/details | Evidence and delivery timeline | Trace notification to rule and event facts |

Files: `backend/adapters/telegram/`, `backend/workers/delivery.py`, `backend/api/rules.py`, `frontend/src/pages/Rules.tsx`, `History.tsx`.

Exit: synthetic event→rule→database→configured Telegram TEST works. Actual delivery occurs only for enabled routes.

## M4: Positions, exposure and OCR — 5–8 days

| Task | Deliverable | Acceptance |
| --- | --- | --- |
| P04.1 Account/manual positions | Versioned holdings and balances | Incomplete reads never clear holdings |
| P04.2 Exposure | Signed delta/gross/net/completeness | Golden arithmetic and missing-data tests pass |
| P04.3 Image jobs | Limits, crop/redaction, encrypted assets/retention | Malicious/oversized inputs rejected |
| P04.4 Vision adapter | Strict extraction schema and provenance | Output is draft only; provider replaceable |
| P04.5 Review/diff UI | Corrections, explicit closes, atomic commit | Partial import retains unseen rows; stale-version conflict preserves draft |
| P04.6 Risk/freshness | A05–A07, dirty-state and invalidation | Unknown exposure not presented as complete |
| P04.7 OCR evaluation | Held-out metrics and workflow report | Extraction target met; zero unreviewed commits |

Files: `backend/domain/positions/`, `backend/domain/risk/exposure.py`, `backend/adapters/ai/vision.py`, `backend/workers/imports.py`, `frontend/src/pages/Positions.tsx`, `frontend/src/components/ImportReview.tsx`, `tests/evals/ocr/`.

Exit G3: upload representative screenshot, correct a field, review partial diff and commit without unintended changes. Manual-only input does not satisfy OCR scope.

## M5: AI suggestions — 4–6 days

| Task | Deliverable | Acceptance |
| --- | --- | --- |
| P05.1 Risk policy | Objectives, permissions and user limits | Missing required policy blocks entry sizing |
| P05.2 Candidate generator | Hold, trim, reduce, put protection and permitted long/debit entries | Fresh instruments, quotes and whole-strategy checks |
| P05.3 Deterministic sizing | Costs, funds, open orders, before/after exposure | Model cannot choose amounts; capacity enforced |
| P05.4 Explain candidates | Grounded structured AI response | Only supplied candidate/evidence IDs accepted |
| P05.5 Final validation | Version/freshness/policy checks and expiry | Changed inputs invalidate actionable cards |
| P05.6 Suggestion UI | Alternatives, uncertainties, conditions, save/dismiss | Useful no-action response; no trade button |
| P05.7 Evals | Valid/adversarial/stale cases | Zero accepted critical violations in evaluated set |

Files: `backend/domain/risk/candidates.py`, `validation.py`, `backend/adapters/ai/explanations.py`, `frontend/src/pages/Suggestions.tsx`, `tests/evals/suggestions/`.

Exit G4: grounded suggestions use the reviewed book with validated calculations. Missing Greeks cannot be invented; restrict affected quantitative features and record capability limits.

## M6: Hardening and acceptance — 4–7 days

| Task | Deliverable | Acceptance |
| --- | --- | --- |
| P06.1 Browser flows | Setup/rule/Telegram/OCR/suggestion/pause tests | Primary/recovery flows pass |
| P06.2 Performance/chaos | Load, disconnect, crash, rate/disk failures | Targets met or issues resolved and limitations explicit |
| P06.3 Security/retention | Secret scan, injection checks, origin controls, cleanup | No critical leaks or side effects |
| P06.4 Service/restore | Background startup, encrypted backup/runbooks | Fresh-directory restore succeeds |
| P06.5 Observation | ≥5 active sessions | Coverage/noise/gaps understood and documented |
| P06.6 Release package | Install, lockfiles, migration and evidence report | G0–G6 satisfied |

Files: `scripts/start.ps1`, `backup.ps1`, `restore.ps1`, `tests/e2e/`, `tests/resilience/`, `docs/release-report.md`.

## Suggested PR sequence

1. Access probe and redacted fixtures.
2. Local app, secret store, database and contracts.
3. Stock ingestion and journal.
4. Option scheduler, coverage and recovery.
5. Rule engine and replay.
6. Telegram outbox.
7. Rule editor, dashboard and history.
8. Versioned positions and exposure.
9. Screenshot extraction and review.
10. Candidate generation/policy/sizing.
11. AI validation and suggestions UI.
12. Background service, restore and integrated release tests.

Each PR states behavior, assumptions, fixture provenance and relevant validation. Resolve provider contracts before mixing them with financial risk logic.

## Definition of done

The user runs the app locally using the existing OpenAPI key and intended OPRA access, monitors a documented stock/options universe, manages rules, receives Telegram messages, reviews screenshot-extracted positions and inspects fresh exposure-aware AI suggestions. Restart, gaps, stale inputs and provider failures are visible. Meaningful financial/state tests pass. No secrets are committed and no brokerage orders are submitted by the app.

See [testing strategy](08-testing-strategy.md) and [operations](09-operations-and-roadmap.md) for detailed gates and recovery policy.
