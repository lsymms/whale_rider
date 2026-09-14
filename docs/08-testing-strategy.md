# Testing strategy

## Principles and layers

Test arithmetic and state transitions deterministically using fake adapters, a virtual clock, and synthetic/redacted fixtures. Separate schema/contract tests from provider availability checks. Live smoke tests use read operations and deliberate TEST messages only, never brokerage orders.

Unit tests cover exact decimals, rules, identity, windows, position diffs and risk. Integration tests use the real database and mocked transports. Contract tests validate provider fixtures. Browser tests exercise critical workflows. Replay tests share the production engine with external sends disabled. OCR/AI evaluation uses held-out versioned data.

## Matrix

| Area | Failure cases | Expected result |
| --- | --- | --- |
| Adapter | Decimal strings, fractional shares, option units, absent fields, batches | Accurate units; invalid payload quarantined |
| Polling | Quotas, 429, retries, pages, lost boundary, slow contract | Budgets respected; cadence/gaps visible |
| Identity | Duplicate packet, identical real trades, overlapping pages, no ID | No false collapse; ambiguity flagged |
| Corrections | Cancel/revise a triggering execution | Recompute and retract linked evidence as supported |
| Rules | Below/equal/above threshold; edit/pause/clone; revision race | Exact boundaries, immutable history, atomic activation |
| Windows | Out-of-order, late, session reset, gap/warm-up | No lookahead or continuity claims across gaps |
| Telegram | Success, timeout after acceptance, 429, 400, 401/403, crash | Correct retry/unknown/expired/dead states |
| Positions | Shorts, fractions, legs, adjusted contracts, incomplete reads | Correct signs; no duplicate legs or accidental zeroing |
| OCR | Crops, themes, signs, decimals, ambiguous dates | Draft only; unresolved required fields block commit |
| Import race | API refresh mid-review, duplicate commit, undo after edit | Conflict/rebase or idempotency; unrelated edits preserved |
| Exposure | Unknown Greeks, conventions, net/gross, signed holdings | Units correct; incomplete never appears zero |
| Sizing | Funds, open orders, leg mismatch, zero allowable quantity | Reject invalid/unsupported candidates |
| AI | Invented number/ID, invalid JSON, injection, timeout | Reject/abstain; no side effects |
| UI/security | Keyboard, zoom, narrow screen, SSE reconnect, CSRF | Accessible controls and authenticated state changes |
| Operations | Crash, disk full, backup damage, SMB runtime path | Explicit failure and tested recovery |

## Golden arithmetic fixtures

1. 80,000 stock shares × $150 = $12,000,000.
2. 250 contracts × $5.20 ×100 = $130,000 premium.
3. +100 shares and +2 calls at delta 0.55/multiplier 100 = +210 delta shares.
4. At $150 underlying: $31,500 delta dollars; trim 50 shares → $24,000.
5. Add one put at delta −0.30: $27,000 delta dollars.
6. Standard 150/155 call debit vertical at $2: $200 debit/$300 maximum expiry gain before costs.
7. Missing/zero OI: ratio unavailable, never infinite.
8. Identical economic prints remain separate unless reliable identity proves duplication.
9. A partial screenshot missing a put retains the put.
10. A stale candidate is rejected even if model prose claims freshness.

Property tests: premium scales with quantity; candidates never exceed validated capacity; duplicate idempotency keys have one effect; permitted batch boundaries do not alter replay results.

## Provider checks

Capture minimal redacted fixtures with SDK version, endpoint, timestamp precision, pagination, identity, feed scope, units and delay. Rerun on SDK upgrades.

During a valid session verify an active stock subscription, time semantics and reconnect. An illiquid option may have no trades despite healthy polling; check poll heartbeat separately. Confirm actual OPRA authorization and observed delay. Sandbox evidence does not establish production real-time performance.

Telegram integration uses a deliberately configured test destination. Exercise rate/error cases with a fake transport rather than flooding a real chat.

## OCR evaluation

Start with ≥100 representative deidentified/synthetic images across desktop/mobile, light/dark, scaling, crop edges, accounts, grouped legs and shorts. Hold out ≥30 images and never use them as prompt examples. Add corrected failures to future evaluation versions.

Measure exact-match symbol, signed quantity, expiry, strike and right; row precision/recall; unresolved/correction rate; review time. Slice by source/theme/crop so easy examples do not hide failures.

Initial quality target: ≥98% critical-field exact match in the in-scope held-out set, plus zero unreviewed commits. Report sample sizes and confidence intervals. This is a usability gate, not proof of future perfect extraction. Improve extraction/review if unmet; manual confirmation remains mandatory.

## AI evaluation

Use ≥100 contexts, half valid comparisons and half abstention/adversarial cases: stale balances, unresolved shorts, missing Greeks, contradictory flow, wide spreads, unsupported strategy, incomplete holdings, malicious screenshot text and policy/version changes.

Require zero accepted critical violations in the evaluated set: wrong arithmetic, invented evidence, unsupported strategy, stale actionable output or side-effect tools. Target ≥95% first-pass schema validity; remaining cases repair once or abstain. Human-review ≥30 responses for useful uncertainty, clarity and exposure relevance. Trading return alone cannot evaluate grounding or safety.

## Replay and observation

Replay normalized events with a virtual clock and fake delivery using the same engine; preserve evidence and state transitions. Freeze rule versions before held-out days.

Observe ≥5 complete active sessions, including open/midday/close. Review trigger volume, suppression, gaps, freshness, queue delay and duplicate ambiguity. Paper outcomes use bid/ask, fees/slippage and explicit hypothetical fills. Avoid lookahead, future open interest and cherry-picked successful signals. This verifies behavior, not a trading edge.

## Performance and resilience

Record actual OS/hardware/storage/model placement; reference target is 4 CPU cores, 16GB RAM and local SSD.

- 500 events/sec for 30 min: p95 receipt-to-alert persistence <250ms, no unexplained loss of committed events.
- 2,000 events/sec for 60 s: bounded memory, visible degradation, no crash.
- Low-volume Telegram: p95 receipt-to-API acceptance <3s on healthy network, excluding provider/poll delay.
- Six-option nominal 10s cycle: publish measured p50/p95 and completeness; pagination/429 must not silently violate scope.
- Kill process after commit/before send acknowledgement: recover outbox with bounded ambiguity.
- Restart during OCR: preserve draft, discard duplicate late results.
- Network outage 2 min: stale status and no expired-alert flood after recovery.
- Disk full/write failure: visible monitoring pause; no false sent state.
- Restore encrypted backup into a fresh native directory; verify integrity, rules, snapshots and delivery state.

## Workflow acceptance and release report

Complete setup → create/preview rule → trigger synthetic TEST → inspect delivery → upload screenshot → correct identity → commit partial update → compare valid alternatives → change positions and observe invalidation → pause notifications.

Release evidence includes commands/results, capability report, pinned versions, cadence/coverage measurements, OCR/AI metrics, replay findings, limitations and restore evidence. Passing documentation checks in this repository does not mean these future application tests have passed.
