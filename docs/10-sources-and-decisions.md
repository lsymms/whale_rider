# Sources and open decisions

Checked **September 14, 2026**. Source facts inform the design; architecture, thresholds, test targets and workflows are proposals. No authenticated Webull requests were made.

## Primary sources

| Source | Supports |
| --- | --- |
| [Market data overview](https://developer.webull.com/apis/docs/market-data-api/overview/) | OpenAPI entitlements, OPRA, app subscription separation, sandbox delay |
| [Authentication](https://developer.webull.com/apis/docs/authentication/overview/) | Key/secret signing and applicable token/2FA |
| [Streaming](https://developer.webull.com/apis/docs/market-data-api/data-streaming-api/) | Stock streaming and connection behavior; options omitted from listed categories |
| [Option ticks](https://developer.webull.com/apis/docs/reference/option-tick/) | Option trade retrieval |
| [Option snapshots](https://developer.webull.com/apis/docs/reference/option-snapshot/) | Current option price/best bid/ask |
| [Option contracts](https://developer.webull.com/apis/docs/reference/option-contract-list/) | Static contract lookup |
| [Stock data](https://developer.webull.com/apis/docs/reference/stocks-market-data/) | Stock ticks, quotes, bars, footprint and NOII |
| [Accounts](https://developer.webull.com/apis/docs/trade-api/account/) | Account, position and balance reads |
| [Positions reference](https://developer.webull.com/apis/docs/reference/account-position/) | Trading API position endpoint |
| [Rate limits](https://developer.webull.com/apis/docs/rate-limits/) | Endpoint-specific quotas |
| [Data API](https://developer.webull.com/apis/docs/market-data-api/data-api/) | REST environments; older generic quota text |
| [SDK](https://developer.webull.com/apis/docs/sdk/) | Official integration tools |
| [Change log](https://developer.webull.com/apis/docs/changelog/) | Recent contract changes |
| [Telegram Bot API](https://core.telegram.org/bots/api) | Messaging and response handling |
| [Telegram FAQ](https://core.telegram.org/bots/faq) | Setup, polling and messaging limits |
| [OIC general FAQ](https://www.optionseducation.org/referencelibrary/faq/general-information) | Open interest and liquidity interpretation |
| [OIC execution FAQ](https://www.optionseducation.org/referencelibrary/faq/trade-entry-execution) | Options execution context |
| [SQLite WAL](https://www.sqlite.org/wal.html) | Filesystem constraints |

The user's [OPRA page](https://developer.webull.com/apis/docs/market-data-api/overview/?utm_source=chatgpt.com) is the same overview. OPRA Real-Time Non-display is the intended subscription path; that does not establish options streaming, complete history or the key's current entitlement.

## Documentation uncertainty

Detailed quota tables differ from older generic tutorial text; use detailed references and measured behavior. Endpoint paths and schemas change. The September 2026 changelog includes order-query pagination updates: future open-order reservation reads must use current contracts. [Change log](https://developer.webull.com/apis/docs/changelog/)

Options streaming is unknown from reviewed material, not declared impossible. A snapshot does not establish historical execution-time NBBO. Accessible reference pages did not expose enough response detail to certify all fields; M0 must validate real SDK/response contracts.

## Decisions

| ID | Decision |
| --- | --- |
| D01 | Use existing OpenAPI key, confirmed by user |
| D02 | Use intended OPRA Non-display subscription path |
| D03 | One user/local app, manual brokerage execution |
| D04 | Runtime on attached disk through native host path; documentation stays here |
| D05 | Stock streaming and bounded option polling initially |
| D06 | Every OCR import reviewed and versioned |
| D07 | Deterministic sizing/exposure; AI explains validated candidates |
| D08 | Provider-neutral AI credentials separate from Webull |
| D09 | Show timing, coverage, missing data and inference |

## Open configuration and validation

| Item | Default / evidence needed | Stage |
| --- | --- | --- |
| Backend host and native attached-disk path | One host, native runtime directory | M0 |
| Matching secret and token flow | SDK authentication; no credentials in chat | M0 |
| Stock/OPRA access and feed/use rights | Capability-dependent activation, personal destination | M0 |
| Option identity/units/multiplier/time/pages/corrections | Unknown fields disable dependent calculations | M0 |
| Options streaming | Poll until verified | M0/later |
| Greeks/IV/OI | Nullable; never fabricated | M0/M4 |
| Symbols/contracts and latency | Proposed 20 stocks/six contracts, measured cadence | M2 |
| Telegram destination/topic/readers | One private destination; omit account amounts | M3 |
| AI provider/cloud images/budget | Off until configured; manual positions available | M4/M5 |
| Risk policy and account permissions | No new-risk sizing without required values | M5 |
| Open-order reservations | Block entries if available capacity is uncertain | M5 |

These are implementation decisions, not blockers to completing the design documentation.
