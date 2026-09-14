# Capability report runbook

The capability report is a local diagnostic for the configured Webull environment. It performs the existing read-only allowlisted checks: account-list authentication, one stock snapshot request, and one option snapshot request. It does not query orders, place or preview orders, change positions, or send Telegram traffic by default.

Run it through the local service workflow only after a valid Webull token is available. The report records capability states, HTTP status, provider code, and a shape-only evidence hash. It intentionally excludes account identifiers, balances, position data, raw provider responses, app secrets, and access tokens.

Treat `stock_snapshot: unavailable / MARKET_DATA_NOT_SUBSCRIBED` and `option_snapshot: unavailable / MARKET_DATA_NOT_SUBSCRIBED` as entitlement evidence, not as an authentication failure. Subscribe to the intended stock and OPRA non-display services before claiming real-time monitoring coverage, then rerun the report.

Telegram output is opt-in. A caller must explicitly set `send_telegram_test=True` and inject the configured guarded Telegram adapter plus its configured TEST destination. The only possible Telegram message from this workflow is labeled `Whale Rider capability TEST`; it contains capability state summaries and no account or credential values. The adapter rejects alert delivery unless its separate live-delivery setting is explicitly enabled.

For a release record, retain the redacted JSON report with the date, Webull environment, SDK/runtime version, observed entitlement state, and any recovery action. Do not attach `.env`, raw responses, screenshots with account identifiers, or bot tokens.
