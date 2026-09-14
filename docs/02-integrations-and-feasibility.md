# Integrations and feasibility

Verified against public primary documentation on **2026-09-14**. These are documentary findings, not tests of the user's key. All proposed internal schemas elsewhere are application contracts, not copied Webull payloads.

## What the existing OpenAPI key enables us to investigate

Webull uses an App Key and App Secret for signed requests over HTTPS; account authentication may also involve an access token/2FA. Use the official SDK's supported authentication path and keep 2FA enabled. The authentication overview and broader overview differ in how they describe token requirements, so verify the actual account configuration. [Authentication](https://developer.webull.com/apis/docs/authentication/overview/)

Market-data entitlements are separate from desktop/mobile subscriptions. Webull lists Nasdaq Basic/TotalView for stock data and OPRA Real-Time Non-display for options. Sandbox may be delayed. Verify the plan's coverage, automated processing rights, personal display, and intended Telegram delivery before enabling a shared destination. [Market data overview](https://developer.webull.com/apis/docs/market-data-api/overview/)

## Capability matrix

| Requirement | Documentary evidence | Design treatment |
| --- | --- | --- |
| Stock reported executions | Stock tick endpoint and market streaming | Use stream after verifying trade units and timestamp meaning |
| Options reported executions | Option tick endpoint exists | Poll a bounded universe; do not assume a full-market feed |
| Option bid/ask | Option snapshots document best bid/ask | Snapshot context is not necessarily the quote at execution |
| Contract discovery | Static option contract query exists | Resolve identity, expiry, strike, type, multiplier/deliverable before calculations |
| Current account positions | Trading account API supports positions and balances | Poll read endpoints; fall back to reviewed manual/OCR positions |
| Options streaming | Current streaming guide omits options | Unverified; keep disabled until tested and documented |
| Greeks, IV, open interest | Not established by the accessible option response schema | Nullable capabilities; no fabricated values |
| Trade IDs, exchange codes, condition/correction flags | Must inspect actual endpoint/SDK schemas | Gate advanced attribution and correction handling |
| Market-wide coverage / historical completeness | Not established | Show exact monitored universe and interval gaps |
| Institutional identity, opening/closing intent | Not established by market ticks | Never assert these from a large print |

Stock streaming uses MQTT with secure WebSocket available. The guide lists up to five connections per key, batches at up to three pushes/sec per connection, and requires resubscription after disconnect. Its stock tick example lacks a stable execution ID. Use one connection and preserve batch boundaries; message push rate is not a trade count guarantee. [Streaming guide](https://developer.webull.com/apis/docs/market-data-api/data-streaming-api/)

## Endpoint map

The current detailed references below take precedence over older tutorial paths. SDK package/version and concrete response models must be pinned after G0.

| Purpose | Method/path documented |
| --- | --- |
| Stock ticks | GET `/market-data/stocks/ticks/list` |
| Stock snapshot | GET `/market-data/stocks/snapshots/list` |
| Stock depth | GET `/market-data/stocks/depths/list` |
| Subscribe / unsubscribe | POST `/market-data/streaming/subscribe`, `/market-data/streaming/unsubscribe` |
| Option ticks | GET `/market-data/options/ticks/list` |
| Option snapshot | GET `/market-data/options/snapshots/list` |
| Option contracts | GET `/trading/instruments/options/contracts/list` |
| Accounts | GET `/trading/accounts/list` |
| Positions | GET `/trading/assets/positions/list` |
| Balances | GET `/trading/assets/balances/get` |

The option tick reference describes time-range retrieval in reverse chronological order. The snapshot reference describes current price, volume, and best bid/ask; the contract reference describes static identifiers. The accessible pages do not expose enough field detail to certify pagination, trade identifiers, multiplier, or Greeks. Capture redacted real responses during implementation. [Option ticks](https://developer.webull.com/apis/docs/reference/option-tick/), [option snapshots](https://developer.webull.com/apis/docs/reference/option-snapshot/), [contracts](https://developer.webull.com/apis/docs/reference/option-contract-list/), [stock endpoints](https://developer.webull.com/apis/docs/reference/stocks-market-data/), [accounts](https://developer.webull.com/apis/docs/trade-api/account/)

Production REST host: `https://api.webull.com`; sandbox: `https://api.sandbox.webull.com`. Choose endpoint mappings explicitly by environment. [Data API](https://developer.webull.com/apis/docs/market-data-api/data-api/)

## Options polling budget: practical consequence

The current rate-limit reference lists production stock/option tick and snapshot endpoints at 60 requests/60 seconds each; sandbox is 30/60 seconds. Counters are per endpoint/app key. The older Data API tutorial mentions 300/minute generally; use the detailed limits and verify server behavior. [Rate limits](https://developer.webull.com/apis/docs/rate-limits/)

Application policy: reserve 20% of each endpoint budget for recovery. For N contracts, one request per contract per cycle, P average pages per request, and usable budget B requests/minute:

`minimum_cycle_seconds = 60 × N × P / B`

With B=48 and P=1: six contracts need at least 7.5 seconds per cycle; 20 need 25 seconds; 100 need 125 seconds. Sandbox doubles these intervals. These are best-case request-budget calculations, not end-to-end guarantees. Do not assume batching until its actual schema and limits are verified.

MVP starts with six contracts and a nominal 10-second cycle, reducing scope or slowing refresh when pagination/retries increase cost. Tick and snapshot budgets are independent but time-aligned snapshots still cannot reconstruct missing historical quotes. Rank contracts by held positions, explicit pins, then active rule relevance; never silently evict a pinned contract. Show requested versus effective coverage.

For each contract: request overlapping time windows; walk supported pagination until the last saved boundary is covered; order by event time; deduplicate only with proven identity semantics; persist the boundary after commit. If an endpoint only returns the most recent capped records and cannot page back to the boundary, record a gap. Never advance a 'complete' watermark through unknown data. No new-contract backfill should generate urgent alerts for old events.

## G0 capability probe

Use the user's stored credentials locally. Do not ask for credentials in chat or put them in the preview.

1. Resolve environment and validate key/secret via a permitted read call.
2. List accounts and select one; test balances, positions, and required token flow.
3. Resolve a liquid stock and one currently listed supported option contract.
4. Fetch ticks and snapshots; record field types, quantity units, decimal encoding, timestamp units/timezone, pagination, and freshness.
5. Test stock subscription, batched payloads, heartbeat, resubscribe, and overlap with REST recovery.
6. Identify feed coverage and whether quotes are consolidated or venue-specific. Never call a quote NBBO without evidence.
7. Measure a six-contract polling cycle in active conditions. Record limits and truncation behavior.
8. Save a redacted report with capability values `verified / unavailable / unknown`, timestamp, SDK version, and evidence hashes.

No order placement is needed. Unknown capabilities disable dependent features rather than blocking unrelated work. Inaccessible options ticks block completion of the options MVP; an alternate licensed provider is a later explicit decision.

## Telegram

Use BotFather to obtain a bot token; add the bot to the chosen chat with send permission. Setup collects numeric chat ID and optional forum topic ID, resolves the destination title, shows a preview, and sends a test only when requested in the app. There is no public webhook requirement for outbound delivery. Optional later commands use long polling with authorized chat/user IDs and durable update offsets. [Bot FAQ](https://core.telegram.org/bots/faq)

Use `sendMessage` through backend HTTPS calls. Store returned message ID and `ok` result. Limit message text to 4096 characters, prefer plain text, and use structured fields for destination/topic. Honor `retry_after` on rate limiting. Bot API acceptance is not proof the user read a notification. [Bot API](https://core.telegram.org/bots/api)

App defaults: no more than one send/sec per chat; group budget 18/minute (below the documented 20/minute ceiling). Reserve two of those 18 slots for health/risk messages. Coalesce overflow into digests, expire urgent trade messages after 60 seconds, and show queue delay. Telegram's group limit makes a three-second delivery target impossible during bursts; report that honestly.

Telegram messages default to market event facts plus 'held underlying' relevance. Exact balances, holdings, screenshot images, and AI prompts are excluded unless the user deliberately enables a private exposure-summary mode. A localhost detail URL works only on the host machine; mobile messages include a searchable alert ID instead.

## AI integration

Provider-neutral `extract_positions(image, schema)` and `explain_candidates(context, schema)` adapters. Choose a configured vision-capable cloud provider or benchmarked local model. Credentials, model ID, API base URL, limits, and cloud disclosure controls are separate from Webull credentials. No provider is assumed from the user's OpenAPI key.
