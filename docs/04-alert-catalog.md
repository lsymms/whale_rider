# Alert catalog and rule engine

## Signal vocabulary

A **print** is a reported execution in the available feed. A **quote** is an offer to trade. A **cluster** is an application grouping of prints; it is not proof of one order or one participant.

Compute stock notional as price × shares. Compute option premium as option price × contracts × verified price multiplier. Underlying-equivalent face value (underlying price × deliverable shares × contracts) and delta-adjusted exposure are different measures; never label either 'premium'. Standard contracts often use 100, but adjusted contracts require explicit metadata.

Treat call/put, observed side, and directional interpretation as separate fields. Buying a put can hedge a long holding; selling a call may be covered. Open interest is not intraday volume or proof of direction/opening intent. [OIC: open interest and liquidity](https://www.optionseducation.org/referencelibrary/faq/general-information)

All thresholds below are configurable **synthetic starter settings** for replay calibration, not current trade recommendations or evidence of predictive power.

## MVP alert templates

| ID | Template and trigger | Needed data | Why a day trader might review it | Noise controls / interpretation |
| --- | --- | --- | --- | --- |
| A01 | Large stock print: shares ≥10,000 AND notional ≥$1m | Execution price/size/unit/time | Find a meaningful transaction near a watched price level | Watchlist; regular session; no assumed buy/sell |
| A02 | Large option premium: contracts ≥100 AND premium ≥$100k | Contract identity, multiplier, trade price/quantity | Notice concentrated activity at a strike/expiry | Separate expiry filters; no price×100 guess for unknown contracts |
| A03 | Repeated large prints: ≥3 qualifying prints in 60s, cumulative ≥$3m stock or $250k options | Reliable event identity and continuous window | Detect sustained activity rather than a single isolated report | Count distinct events, not MQTT messages; disable on identity ambiguity/gap |
| A04 | Held-underlying flow: A01/A02 matches a current holding's underlying | Reviewed positions plus market event | Prioritize something relevant to current exposure | Add relevance to the original alert; do not duplicate it as a second push |
| A05 | Exposure limit crossed: user concentration/delta/risk limit crossed | Fresh confirmed positions, prices, required Greeks | Prompt review of an existing risk condition | Trigger on threshold crossing; reset below a hysteresis band |
| A06 | Position or market data stale: exceeds configured policy | Heartbeat/poll status, observation times | Prevent decisions based on stale inputs | One transition notice; periodic digest; no fake trade alerts |
| A07 | Imminent expiry exposure: held option expires today or next session | Verified expiry/settlement metadata and positions | Draw attention to time-sensitive exposure | Distinguish clock-time expiry from a simple DTE integer |
| A08 | Delivery failure or uncovered instrument | Outbox and subscription states | Make silent failure visible | Dashboard immediately; Telegram only if destination still works |

A01 and A02 fire from executed-trade data only. A05–A08 are explicitly labeled risk/health notices.

## Enrichment and later alerts, capability gated

| ID | Template and sample trigger | Evidence prerequisites | Trading use / limitations |
| --- | --- | --- | --- |
| B01 | Ask-side/bid-side premium ≥$150k | Quote at or before trade, age ≤1s, valid market, known scope | Approximate aggressor; never label a polled current quote as execution-time evidence |
| B02 | Unusual contract volume: session contracts ≥1,000 and volume/prior OI ≥2 | Complete session volume and dated prior-session OI | Focus attention on unusual activity; OI=0/missing gives 'unavailable', not infinity |
| B03 | Sweep-like burst: ≥3 venues in ≤1s for same contract, ≥$200k | Venue IDs, high-resolution timestamps, reliable distinct executions and conditions | Indicates coordinated-looking activity only; not confirmed intermarket sweep orders |
| B04 | Flow plus price confirmation: large print then completed 1m bar closes above opening range/VWAP | Correctly constructed bars, trading calendar, sufficient history | Separate notification after confirmation; never backdate trigger to first print |
| B05 | Opposing flow on long exposure | Reliable side evidence, relevant option direction, current net exposure | Consider trim/hedge review; directional interpretation remains uncertain |
| B06 | Short-dated premium: ≥$100k and DTE ≤1 | Contract expiry, session calendar | Flag sensitivity to time and price; default high-noise tier with strict cap |
| B07 | Far OTM concentration: moneyness distance ≥5%, clustered premium | Underlying price aligned to trade, contract metadata | Notice speculative activity; avoid automatic chase suggestions |
| B08 | Stock block near VWAP/prior high/low within 0.2% | Trusted price levels and stock print | Review response at a level; a block may be delayed or tied to another position |
| B09 | Same-time stock and option activity | Temporal alignment, contract relationship, event identity | Display related observations; do not claim a stock-option strategy linkage |
| B10 | Footprint imbalance / auction imbalance | Entitled feed, verified field meanings and session timing | Separate context panel; these are not necessarily newly executed large trades |
| B11 | Relative size percentile ≥99.5 and notional floor | At least 20 comparable sessions with sufficient feed coverage | Normalize size by symbol/session; do not compare illiquid and liquid symbols blindly |
| B12 | Flow thesis invalidation | User-saved idea, defined level/time, live market evidence | Alert when the review condition fails; stop assumptions are not guaranteed fills |

Webull documents footprint and NOII endpoints with additional subscription requirements. Their availability does not establish options sweep identification. [Stock data reference](https://developer.webull.com/apis/docs/reference/stocks-market-data/)

## Rule structure

See the [synthetic rule example](../examples/alert-rule.json). MVP uses a small typed operator set: numeric gte/lte, membership, equals, time window, and AND. No user-supplied Python, JavaScript, SQL, or arbitrary expression evaluation.

Required fields: stable ID/revision, name, template, active state, asset scope, explicit universe, session policy, thresholds with units, freshness requirements, cooldown scope, severity, routing, and expiry. Optional filters include expiry range, calls/puts, underlying price floor, minimum liquidity, position relevance, and inference requirement.

Validate contradictory filters, negative thresholds, unavailable fields, unsupported instruments, excessive monitored scope, and limits outside application policy. Show a coverage/cadence estimate before activation. Saving a rule never silently activates an unavailable dependency.

Lifecycle: draft → validated → enabled → paused or archived. Edits create a new immutable revision. A new revision starts its aggregate state at activation, warms up for the full window, and retains prior evidence for historical explanation. Rule simulation evaluates historical/synthetic input without production delivery, position changes, or live cooldown mutations.

## Evaluation order

1. Verify normalized event is an execution and the event/contract is supported.
2. Apply source mode: live, polled, delayed, replay; never mix replay with live routing.
3. Filter universe, session and contract attributes.
4. Reject invalid price/quantity/multiplier and record a reason.
5. Apply freshness and interval-completeness policy.
6. Join eligible context (as-of quote, underlying, holdings, baseline) with independent age checks.
7. Evaluate threshold and optional rolling aggregate.
8. Determine observed facts, derived metrics, inference labels, relevance and severity.
9. Apply deduplication, family grouping, cooldown, escalation, quiet hours, and delivery budget.
10. Commit result/evidence/outbox atomically.

For a 60s rolling rule, retain distinct event contributions in [t−60s, t]. Allow a configurable 2s reorder buffer for streaming aggregates; delayed events older than the live freshness policy remain in history without urgent notifications. A gap invalidates a continuous-window rule until one full fresh window has accumulated.

Single-print rules may notify promptly without waiting for the aggregate reorder buffer. Polled rules use provider event time, not poll receipt time, and are labeled 'polled'. Recovered/backfilled events never masquerade as just-executed prints.

## Side classification

Only classify when a verified quote exists at or before the execution with a small maximum age and bid < ask. 'Near ask' and 'near bid' use an instrument-aware tick tolerance capped below half the spread, so classifications cannot overlap. Midspread, outside-market, zero/locked/crossed quote, stale quote, or uncertain feed scope yields unknown.

Provider side values are preserved with their exact documented meaning after verification; they are not silently promoted to participant intent. A newer snapshot can show 'current quote context' but cannot establish where the earlier trade executed relative to bid/ask.

## Noise and priority

- Default cooldown key: rule stable ID + instrument + session. Store evidence during cooldown.
- Escalate once if new notional exceeds twice the last notified size; update baseline and cooldown atomically.
- Avoid double-counting A04 as a new event; append the holding relevance to A01/A02.
- Correlated family grouping shares a Telegram message but keeps all triggered rule IDs.
- Quiet hours defer normal alerts to a digest or expire them; risk/health exceptions are a user policy.
- Rank severity lexicographically: system-critical, exposure-limit breach, held underlying, user priority, then size. Do not present rank as a probability of profit.
- Duplicate, suppressed, stale, gap-affected, and unsupported events have searchable reason codes.

## Example Telegram payloads

Synthetic stock event:

```text
WR-1042 | LARGE STOCK PRINT | POLLED/LIVE label
NVDA | 80,000 shares × $150.00 = $12,000,000
Executed 10:31:04.220 ET | received +0.6s
Observed trade; aggressor unknown
Relevant: held underlying
Rule: Large stock v3 | 20-symbol watchlist
Review: check price response and current exposure
```

Synthetic option event:

```text
WR-1043 | LARGE OPTION PREMIUM | POLLED
NVDA 2026-09-18 155 CALL
250 contracts × $5.20 × 100 = $130,000 premium
Trade 10:31:08 ET | observed 8s later
Side unknown; opening/closing unknown
6 contracts monitored | cycle 10s
Held underlying. Review current quote before acting.
```

Synthetic risk/AI review:

```text
WR-1044 | EXPOSURE REVIEW
NVDA flow matched an existing long exposure.
Validated alternatives available: hold / trim / protective put.
No automatic trade. Position snapshot v12; review in local app.
```

Specific quantities and account values in exposure messages require the private-summary setting. An AI explanation is optional and asynchronous: send the deterministic event first; do not make basic alerts depend on model latency.
