# Positions and AI OCR

## One canonical position book

Positions can come from Webull account reads, manual entry, or screenshots. All become versioned snapshots with account, capture/observation time, source, completeness, and lineage. A screenshot is a report of holdings at a point in time, not an order/fill stream and not proof of current buying power.

The API is the preferred routine source where verified. An OCR draft never silently wins over API data. Recency, confirmed account, and explicit reconciliation determine what is current. Keep balance data separate: OCR of a positions table does not infer cash, equity, or buying power.

## Capture-to-commit workflow

1. Select account alias and source (Webull desktop/mobile or generic table).
2. Paste, drag, or select PNG/JPEG/WebP. Enter or confirm screenshot capture time; upload time is not capture time.
3. Display the image locally, allow cropping and redaction, and disclose whether the configured model is local or cloud.
4. Validate magic bytes, pixel dimensions, 10MB file cap and 25-megapixel decoded cap; normalize orientation and strip metadata. Refuse unsupported/animated/polyglot/decompression-bomb input.
5. Create an import job and encrypted local asset; compute hash to detect duplicate imports.
6. Vision/OCR provider returns strict JSON, rows, raw text, bounding boxes, and per-field confidence/uncertainty. Optional text OCR provides a second extraction signal.
7. Resolve symbols/contracts deterministically against instrument metadata. Do not infer a missing call/put, year, strike, sign, or multiplier merely to complete a row.
8. Show image crop and editable row together; highlight conflicts and missing fields.
9. Show a before/after position diff and exposure preview based only on validated fields.
10. User confirms the intended changes; commit atomically against the expected current position version.
11. Recompute exposure; invalidate affected suggestions; record audit history and offer undo as a new version.

Cloud extraction uses only the cropped/redacted image after the user's provider choice. Redaction occurs before transmission. No account screenshot is sent to Telegram by default.

## Required and optional row fields

| Field | Rules |
| --- | --- |
| Account | Selected by user; corroborate any visible account marker without exposing full account ID |
| Asset type / symbol | Resolve canonical instrument; ambiguous lookup requires review |
| Signed quantity | Positive=long, negative=short; missing sign and ambiguous parentheses require review |
| Option right / expiry / strike | All required for options; preserve leading decimals and distinguish weekly/monthly dates |
| Multiplier / deliverable | From verified metadata; 100 is a candidate only for confirmed standard contracts |
| Average price | Optional; label per share/per option price versus total cost; no automatic division by 100 without units |
| Market value / P&L | Optional OCR fields used for consistency checks; not authoritative risk inputs |
| Capture time | User-confirmed timestamp with timezone |
| Visibility/completeness | partial image, full account declared, or unknown |
| Confidence/evidence | Per-field confidence, crop bounds, raw text, manual correction state |

Model confidence is not a calibrated probability. Every import requires review even if all fields claim high confidence. Strong syntactic/semantic validation and user correction outrank confidence scores.

## Partial screenshot semantics

Default mode is **update visible rows only**. Missing holdings remain unchanged. Never turn an absent row into zero quantity.

The diff shows New, Update, Unchanged, Conflict, and Explicit close separately. The user may declare a full-account snapshot, but closing previously held rows still requires explicit review of each proposed omission/zeroing. Collapsed spreads, offscreen rows, filters, hidden short signs, and paginated tables make full-account status uncertain.

An OCR row updates aggregate position quantity; it does not add to existing quantity unless the user is deliberately recording a transaction in a separate future feature. Re-importing the same screenshot must not double a holding.

## Conflicts and concurrency

Commit requires `expected_position_version` and an idempotency key. If an API refresh, another browser tab, or a manual edit changed the account while OCR ran, return 409 with a new diff. Preserve the OCR draft; do not overwrite either input.

A newer API snapshot replaces the canonical account book only after a complete successful retrieval and a reconciliation policy check. If it disagrees with a user-confirmed manual/OCR book, mark a conflict, keep the last reviewed version available, and pause actionable suggestions until resolved. Failed, partial, or stale API reads cannot zero the account.

Strategy group totals and their component legs must not both be counted. Rows with nonstandard deliverables or unresolved grouping can be displayed with 'exposure incomplete' and omitted from quantitative sizing; this blocks portfolio-wide new-risk recommendations.

## Review example

Existing NVDA row: +100 shares. Extracted screenshot: quantity 150, but confidence is low because the last digit is cropped. User corrects it to 100. A call row says '155 C 09/18' without a year: the app shows metadata matches and requires explicit selection. A previously held put is absent: it remains held under partial-update mode.

The preview displays:
- NVDA shares: 100 → 100, unchanged.
- NVDA selected call: 1 → 2, add one contract to the reported holding.
- Missing put: retained.
- Buying power: unchanged, source/account observation still required.

The audit stores the extracted values and user correction, while the active book uses only the committed resolved values.

## Freshness and reconciliation

Default API account refresh every 15 seconds during the active session, with adaptive rate limiting and manual refresh. Freshness policy is 60 seconds for actionable suggestions. Reconfirm a screenshot-derived book after trading; reconfirmation is recorded separately from the original image capture time.

If the user reports a new trade, an account event implies a fill, or a conflict arises, mark the book dirty immediately. Account/order events may trigger a refresh if supported; they do not substitute for a reconciled position snapshot.

A stale but readable position book remains visible for general context. The app states exactly which fields prevent sizing, such as 'Cash not verified' or 'Call delta unavailable', rather than presenting a complete-looking exposure total.

## Privacy, retention, and undo

Default raw-image retention: delete 24 hours after commit or 7 days after an abandoned draft; configurable shorter retention. Keep structured snapshots and audit history 90 days unless the user chooses otherwise. Deletion removes local image assets and thumbnails; encrypted backup retention is disclosed separately.

Undo creates a compensating snapshot based on the current book and shows a fresh diff. It must not revert unrelated later changes. Screenshot text is untrusted content: embedded instructions are treated as pixels/data, never as commands to the AI or application.
