# Product and MVP

## Product intent

Whale Rider is a personal workstation for noticing unusually large reported executions, understanding their relevance to existing holdings, and reviewing possible responses. It runs locally and sends concise alerts to a configured Telegram chat while the browser is closed.

The user already has a **Webull OpenAPI key**. Initial setup uses that key; it does not require creating a new API application by default. The key's matching secret, environment, account permissions, and market-data subscriptions still need verification.

Assumptions: one adult user; US stocks, ETFs, and supported listed equity/ETF options; USD base currency; America/New_York display time; one account selected for actionable sizing; one Telegram destination. Multiple account records are supported in the model but cross-account collateral is never assumed. Index options are disabled until independently verified.

## Primary jobs

| Job | Required outcome |
| --- | --- |
| Notice a large transaction | Receive ticker/contract, size, dollar amount, event time, freshness, and evidence |
| Manage noise | Create, edit, pause, duplicate, archive, test, and snooze rules |
| Relate flow to holdings | Rank events on held underlyings and show matching exposures |
| Update positions from a screenshot | Extract, inspect, correct, and commit an explicit change set |
| Get possible responses | See do-nothing, reduce, hedge, or conditional entry candidates with before/after exposure |
| Trust the system | See data gaps, missing coverage, stale positions, and delivery failures immediately |

## Scope by release

| Capability | MVP | Later |
| --- | --- | --- |
| Webull | Capability probe, stock tick stream, bounded option tick polling, account read adapter | Additional entitled feeds and verified options streaming |
| Alerts | Large stock print, large option premium, repeated prints, held-underlying priority, freshness and exposure warnings | Calibrated unusual flow, sweep-like clusters, auction and footprint context |
| Rule management | AND filters, templates, dry-run, immutable versions, enable/pause/archive, cooldown, quiet hours | Nested Boolean expressions and reusable rule groups |
| Telegram | One destination, test button, outbox, retries, digest, send status | Authorized bot commands and callback actions |
| Positions | API refresh where permitted, manual rows, reviewed AI OCR, snapshots and conflict handling | Multi-broker CSV imports and strategy grouping assistance |
| AI | Provider interface, image extraction, validated explanations of bounded trade candidates | Calibrated ranking, local model benchmarking, richer scenarios |
| UI | Dashboard, Rules, Positions, Suggestions, History, Settings/Health | Advanced charting, mobile remote access |
| Trading | Manual action in Webull after review | Any order execution requires a separate design and scope decision |

AI and screenshot review are part of the MVP, not postponed beyond it. When AI is disabled or unavailable, alerts and manual position editing remain usable. A capability-limited stock-only build is an intermediate milestone, not completion of the requested stock-and-options MVP.

## MVP boundaries

The system observes reported trades in its subscribed/polled universe. It does not promise every market execution, identify institutions, determine opening versus closing intent, or guarantee profitable signals. A bid/ask comparison is an inference. Quotes, orders resting on a book, auction imbalance, and executed transactions have separate event types.

No public hosting, automatic brokerage orders, unattended OCR commits, or unrestricted AI tool execution. Screenshots update the app's representation of positions only; they never update the brokerage account.

## Defaults to validate through replay

- Stock watchlist: 20 symbols, held underlyings first.
- Options: six explicitly selected contracts initially, with a measured refresh interval; show coverage per contract.
- Regular session by default; premarket and after-hours stock rules require explicit session selection.
- Starter stock threshold: both 10,000 shares and $1,000,000 notional.
- Starter option threshold: both 100 contracts and $100,000 premium.
- Cooldown: 60 seconds per rule and instrument; stronger evidence may escalate.
- Positions fresh for actionable sizing: API observation or user reconfirmation within 60 seconds.
- Trade freshness: streaming event no older than 5 seconds; polled event threshold derived from the measured polling cycle and displayed separately.
- AI candidates expire after 60 seconds or immediately after material input changes.
- No new-risk sizing until the user supplies account equity, available funds, strategy permissions, and personal risk limits.

These are configurable engineering/product starting points, not established trading edges or universal risk limits.

## Acceptance gates

| Gate | Acceptance |
| --- | --- |
| G0: access feasibility | Save a redacted capability report from the actual key; prove tick units, timestamps, contract identification, and account reads |
| G1: alert integrity | Synthetic/replayed prints yield correct thresholds, deduplication, gaps, and delivery records; no quote-to-trade confusion |
| G2: options coverage | Demonstrate complete retrieval within the selected universe/cycle or label incomplete coverage and restrict affected rules |
| G3: positions | Every OCR import is reviewed; partial screenshots cannot silently erase holdings; API conflicts cannot silently overwrite edits |
| G4: AI | Every actionable candidate has deterministic validated exposure, sizing, data lineage, and expiry; invalid inputs lead to abstention |
| G5: operations | Restart restores rules and outbox; stale backlogs are expired; backup restoration succeeds; secrets stay out of Git and browser output |
| G6: user workflow | Complete setup, create a rule, receive a test, review OCR, inspect an exposure-aware candidate, and pause alerts |

Target performance on a specified test machine: p95 stock receipt-to-alert persistence under 250 ms at 500 normalized events/sec; p95 receipt-to-Telegram acceptance under 3 seconds in a low-volume healthy-network test. Provider latency, polling cycle, queue congestion, and mobile notification delay are measured separately.

## Success measures

Track actionable reviews per notification, mute/snooze rate, duplicate rate, unexplained missing alerts, position correction frequency, delivery acceptance latency, and invalid AI candidate rate. Track simulated outcomes separately with costs and uncertainty; notification volume and backtest return alone are not product success.
