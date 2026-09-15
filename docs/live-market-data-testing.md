# Live Market-Data Testing

This runbook verifies that the configured Webull OpenAPI credentials can read the market-data paths Whale Rider needs after Nasdaq Basic and OPRA Real-Time Non-display are enabled. The checks are read-only. They do not inspect orders, preview orders, submit orders, change positions, or send alert traffic.

## Preconditions

- `.env` contains `WEBULL_ENV=production`, `WEBULL_APP_KEY`, `WEBULL_APP_SECRET`, and a non-expired `WEBULL_ACCESS_TOKEN`.
- The Webull developer portal shows Nasdaq Basic and OPRA Real-Time Non-display active for this OpenAPI app.
- Use a currently listed option contract identifier from Webull for `-OptionSymbol`. Do not use an underlying ticker such as `AAPL` as proof of OPRA entitlement; that only proves the endpoint is reachable.

If the token is blank or expired, run:

```powershell
node scripts/webull-auth.cjs
```

Complete the Webull mobile approval prompt and SMS code when requested. The helper never prints the token.

## Test From The Webapp

1. Start Whale Rider:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

2. Open `http://127.0.0.1:8787`.
3. Go to `Settings`.
4. Click `Run capability probe`.
5. Confirm these rows:

| Row | Expected healthy result | What it proves |
| --- | --- | --- |
| Authentication | `verified` | The app can sign and authenticate read-only Webull requests. |
| Account read | `verified` | The access token can read the account-list endpoint used as the token health check. |
| Stock snapshots | `verified` | Nasdaq stock market-data snapshot access is working for the probe symbol. |
| Option snapshots | `verified` | OPRA option snapshot access is working for the exact option contract used by the backend probe. |

The Settings page intentionally shows only states, sanitized provider codes, and HTTP status summaries. It does not display balances, account identifiers, raw provider payloads, secrets, or signed URLs.

## Test From The CLI

Run the read-only probe with a real, currently listed option contract:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/probe-webull.ps1 -OptionSymbol AAPL260918C00200000
```

Replace `AAPL260918C00200000` with a valid option contract from the Webull OpenAPI format you want Whale Rider to monitor. The probe prints redacted JSON. A healthy entitlement check has:

- `capabilities.authentication.state` = `verified`
- `capabilities.account_read.state` = `verified`
- `capabilities.stock_snapshot.state` = `verified`
- `capabilities.option_snapshot.state` = `verified`

If the stock or option row is `unavailable` with a subscription-style code such as `MARKET_DATA_NOT_SUBSCRIBED`, the credentials authenticated correctly but the app or account is not entitled for that feed. Recheck the Webull developer portal subscription, wait for activation if it was just enabled, then rerun the probe.

## What This Does Not Prove

A verified snapshot proves point-in-time endpoint access. It does not yet prove:

- real-time delay characteristics during market hours,
- stock stream reconnect behavior,
- sustained option polling cadence,
- complete option-universe coverage,
- Greeks, implied volatility, open interest, or sweep identification,
- suitability for automatic trade execution.

Before enabling live alert delivery, collect at least one active-session observation record with heartbeat timing, observed event timestamps, option contract coverage, and stale-data behavior. Whale Rider should keep dependent rules disabled or dry-run-only when these measurements are missing.

## Troubleshooting

| Result | Likely meaning | Next action |
| --- | --- | --- |
| `TOKEN_REQUIRED` or `AUTHENTICATION_REQUIRED` | `.env` is missing a token or the token failed validation. | Run `node scripts/webull-auth.cjs`, complete Webull verification, and rerun. |
| `INVALID_TOKEN` | Webull rejected the configured access token. | Generate a replacement token with `scripts/webull-auth.cjs`. |
| `MARKET_DATA_NOT_SUBSCRIBED` | The endpoint authenticated but the feed entitlement is absent or inactive. | Confirm Nasdaq Basic or OPRA Real-Time Non-display in the Webull portal. |
| `unknown` with no provider code | The local app could not classify the response safely. | Save the redacted output and inspect backend logs without copying secrets. |

Keep `.env`, raw Webull responses, account IDs, balances, and screenshots with account identifiers out of Git and Telegram.
