# AI suggestions and current exposure

## Division of responsibility

Deterministic code generates a small set of permissible candidates, prices them conservatively, computes risk, and enforces the user's limits. The AI explains and ranks those already validated candidates using cited local evidence. An AI model never invents contract quotes, Greeks, balance, fill price, news, or risk arithmetic.

Every run can return **no action**. A run with missing required data returns a specific abstention reason and the next useful step. Recommendations are conditional decision support for manual review in Webull, with no order-submission capability.

## Required inputs

- Current reviewed positions, account alias/version, completeness, and independent timestamps.
- Equity, cash, available funds/buying power, options permissions, and open-order reservations where verified.
- Current tradable instruments and quotes with timestamps, sizes and feed scope.
- Fresh Greek/IV values with source and convention when an option calculation needs them.
- Relevant alerts, rule versions, observed/inferred facts, coverage and quality.
- User objective: reduce exposure, hedge, investigate an entry, or review portfolio.
- User limits: maximum incremental loss per idea, aggregate strategy risk, name concentration, allowed strategies, daily loss stop, maximum spread/slippage, and expiry restrictions.

Do not assume a Webull key is an AI-provider key. Settings support a separate provider credential or a local model endpoint.

## Exposure definitions

Use signed position quantity q, price multiplier m, underlying price S, contract delta δ, and gamma γ. Standard equity option examples below use m=100 only because their contract metadata is explicitly assumed standard.

- Stock delta shares = signed shares.
- Option delta shares = q × m × δ.
- Underlying delta dollars = S × (stock shares + sum(option delta shares)).
- Gross delta dollars = sum of absolute per-position delta dollars; net = signed sum.
- Gamma shares per $1 move = q × m × γ.
- Vega dollars per one volatility percentage point and theta dollars per day require provider unit normalization before summing.
- Name concentration reports both gross market value/equity and delta dollars/equity; these answer different questions.
- Unknown Greeks make delta exposure partial, not zero. Unknown equity makes concentration percentage unavailable.
- Short positions retain their sign; uncovered short options require risk treatment distinct from long premium.
- Pending orders are separate possible future exposures. A candidate must fit both current holdings and worst permitted open-order fill scenarios.

For scenario P&L, stock contribution = q × ΔS. Small-move option approximation = q × m × (δΔS + 0.5γΔS² + vegaΔIV + thetaΔt), with units normalized and explicitly labeled approximate. Use scenarios −3%, −1%, +1%, +3%, IV ±5 percentage points, and one day decay. Large moves/near expiry require validated full repricing or 'scenario unavailable'; do not present a local Greek approximation as a bounded loss guarantee.

Do not offset unrelated stock deltas as though they were the same underlying. Sector and beta exposure require dated classification/history and confidence. Estimated correlations do not release per-name risk limits.

## Supported candidate families

| Candidate | When it may be useful | Deterministic requirements |
| --- | --- | --- |
| Hold / wait | Ambiguous, stale or conflicting flow; no candidate improves objective | State missing confirmation and review trigger |
| Trim an existing stock holding | Concentration exceeds chosen limit or trader wants lower delta | Fresh signed quantity/price; avoid crossing through zero accidentally |
| Reduce an existing option position | Reduce near-expiry or concentrated exposure | Correct leg/strategy accounting, current quote; avoid leaving an uncovered short leg |
| Buy protective put | User holds long stock and seeks downside protection | Contract matching, cash, debit, expiry, coverage ratio, spread, delta where claiming exposure reduction |
| Buy stock / long call / long put | User opts into a directional entry after defined confirmation | Fresh funds, explicit loss budget, liquidity, applicable permissions and exposure limits |
| Defined-risk debit vertical | User permits spreads and seeks bounded incremental debit | Same underlying/right/expiry, verified strikes/multipliers/deliverables and ratio; whole strategy valid |
| Covered call or collar | Later capability for appropriate user objective | Verified coverage and exercise/assignment treatment; selling a call caps upside and is not equivalent to buying protection |
| Uncovered short options | Excluded from MVP candidate generator | Do not let model text bypass this constraint |

For American-style options, expiry payoff alone does not eliminate early assignment, exercise timing, financing, or temporary stock exposure. MVP explanations include those execution considerations where a candidate has short legs. General option execution/liquidity context is grounded in the [OIC trade execution FAQ](https://www.optionseducation.org/referencelibrary/faq/trade-entry-execution).

## Sizing and validation

For a long option, max incremental premium loss = ask × multiplier × contracts + fees + slippage reserve. For a valid debit vertical at expiry, maximum incremental loss is total debit plus costs; maximum expiry gain is spread width × multiplier × contracts − debit − costs. Reject mismatched deliverables, ratios, expiries, and impossible debit/width values.

For stock, a stop-based risk estimate = shares × abs(entry−stop) + costs. Label this **planned stop risk**, not maximum possible loss; gaps and execution can exceed it. New positions require user-defined conditions and a risk model supported by the app.

Allowed quantity = floor(minimum of risk-budget capacity, funding capacity, concentration capacity, and liquidity/position capacity), computed for all candidate legs and outstanding orders. Quantity less than one means reject. For trims, cap at currently closable quantity and respect strategy dependencies.

Hard validator checks: current account version, instrument existence, market session, data age, finite signed decimals, permission, sufficient available funds, nonnegative quantities, units, quote validity, spread threshold, exposure limits, leg matching, and candidate expiry. A cloud/model timeout cannot waive any check.

## Synthetic worked example: exposure-aware alternatives

Assume an illustrative NVDA price of $150, account equity $100,000, +100 shares and +2 standard calls with delta +0.55. These are fictional values, not current quotes or a trade instruction.

Current delta shares = 100 + (2 × 100 × 0.55) = 210.
Current delta dollars = 210 × $150 = $31,500 (31.5% of illustrative equity).

| Alternative | Delta shares after | Delta dollars after | What it changes |
| --- | --- | --- | --- |
| Hold | 210 | $31,500 | Avoids action on uncertain flow; unchanged exposure |
| Sell 50 held shares | 160 | $24,000 | Reduces directional exposure by $7,500; sale proceeds are not profit |
| Buy 1 standard put, delta −0.30 | 180 | $27,000 | Reduces local delta by $4,500; costs premium and changes Greeks |

If the illustrative put ask is $2.00, debit is $200 plus costs; that is the put's incremental premium at risk, not the entire portfolio's maximum loss. At a $145 strike it protects 100 shares below that strike at expiry subject to premium and execution, while the long calls have their own payoff. Net delta changes as price/time/IV change.

An illustrative 150/155 call debit spread costing $2.00 has $200 debit and $300 maximum expiry gain per standard spread before costs. With an explicitly chosen $500 incremental risk budget, one could fit at most two before checking fees, slippage, exposure, funds and permissions; those checks may reduce quantity or reject it. A model cannot choose a larger quantity.

The UI shows the event's unknown intent and offers hold/trim/protection according to the selected objective. It does not conclude that an observed large call print means the user should add calls.

## AI request and response contract

See [synthetic suggestion contract](../examples/suggestion.json). Input includes opaque evidence IDs, sanitized position summary, deterministic candidate IDs and calculations, permitted output schema, source ages and quality, objective, and user policy version.

Output fields: run ID, ranked candidate IDs, concise rationale, supporting evidence IDs, counterevidence, conditions, invalidation, uncertainties, and abstention. Position/quote/risk amounts are displayed directly from deterministic candidate records; model prose cannot override them.

Candidate view also includes legs/quantities, proposed limit basis (not a guaranteed fill), incremental cost/risk, exposure before/after, scenario limitations, expiry, and reason for ranking. Any number in AI narrative must match a supplied calculation or be removed/rejected.

Pipeline: deterministic candidates → prevalidation → model explanation → strict schema parsing → evidence/number validation → final freshness/version validation → display. Permit one schema-repair retry, then show deterministic cards without prose or abstain.

## Freshness and invalidation

Default requirement: positions/balance observation ≤60s; quote age ≤5s for execution-oriented pricing. If options polling cannot meet this, fetch the candidate quote on demand within its separate rate budget; otherwise show an unpriced research idea and disable actionable sizing.

Invalidate if position version changes, quote exceeds its age limit, user policy changes, candidate expires, an input alert is corrected, or material price movement changes the risk result. Recalculation can restore validity through a new run; old cards retain an expired label in history. Unknown event/news context must be disclosed, never filled by model memory.

## AI isolation, budget, and evaluation

Treat OCR, event notes, imported labels and provider text as untrusted data. Fixed instructions prohibit following embedded commands. The AI worker has no broker credential, no Telegram credential, no arbitrary network tools, and no file access beyond an approved input asset.

Provider settings: model ID, timeout (15s suggestion / 30s OCR starting limits), maximum concurrency (one each), token/image limits, daily budget, cost estimate source and kill switch. Prices are configurable and checked against the chosen provider at implementation; no universal pricing is assumed. Cloud providers may have their own retention policies; 'locally hosted' describes the app, not all processing.

Cache by account version + quote IDs + candidate set + policy/model version. Only validated fresh results may be reused. Test schema validity, factual grounding, arithmetic agreement, unsafe strategy rejection and useful abstention separately from simulated trading outcomes.
