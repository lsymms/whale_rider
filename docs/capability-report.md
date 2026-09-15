# Capability report runbook

The capability report is a local diagnostic for the configured Webull environment. It performs the existing read-only allowlisted checks: account-list authentication, one stock snapshot request, and one option snapshot request. It does not query orders, place or preview orders, change positions, or send Telegram traffic by default.

Run it through the local service workflow only after a valid Webull token is available. The report records capability states, HTTP status, provider code, and a shape-only evidence hash. It intentionally excludes account identifiers, balances, position data, raw provider responses, app secrets, and access tokens.

The production read-only probe completed stock and option snapshot checks on September 15, 2026. That verifies the authenticated endpoint path for the configured production token. It does not prove that either feed is real-time, complete, suited to the requested option universe, or able to sustain the stated cadence. Treat an `unavailable / MARKET_DATA_NOT_SUBSCRIBED` response as entitlement evidence rather than an authentication failure; treat a `verified` snapshot response as a point-in-time endpoint result, then measure actual event fields, delays, reconnects, and OPRA coverage before activating dependent rules.

## Nasdaq and OPRA entitlement check

Use a production token and an exact listed option symbol from the operator contract catalog. Do not use an underlying such as `AAPL` as proof of OPRA contract access.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-webull-entitlements.ps1 -OptionSymbol AAPL260918C00200000
```

The wrapper calls the existing allowlisted probe only: `GET /openapi/account/list`, one US-stock snapshot, and one US-option snapshot. It prints a minimal JSON summary with `nasdaq_basic_or_totalview` and `opra_realtime_nondisplay` states. It suppresses raw output and never prints `.env` values, account identifiers, provider payloads, access tokens, or secrets.

`snapshot_verified` means that particular snapshot endpoint returned a successful response with the supplied production credential. Confirm the actual Nasdaq Basic/TotalView and OPRA Real-Time Non-display plan in Webull, then collect in-market measurements of event/receipt time, field quality, delay, reconnect behavior, and option-cycle coverage. Only those measurements support enabling live stock or option rules.

Telegram output is opt-in. A caller must explicitly set `send_telegram_test=True` and inject the configured guarded Telegram adapter plus its configured TEST destination. The only possible Telegram message from this workflow is labeled `Whale Rider capability TEST`; it contains capability state summaries and no account or credential values. The adapter rejects alert delivery unless its separate live-delivery setting is explicitly enabled.

For a release record, retain the redacted JSON report with the date, Webull environment, SDK/runtime version, observed entitlement state, and any recovery action. Do not attach `.env`, raw responses, screenshots with account identifiers, or bot tokens.
