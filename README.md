# Whale Rider

Design for a locally hosted stock and options flow alerting webapp, with Telegram delivery, screenshot-assisted position updates, and exposure-aware AI trade suggestions.

**Status:** design package, not a connected trading application. Examples and prototype data are synthetic. Prepared September 14, 2026 for a user who already has a Webull OpenAPI key.

## Start here

1. [Product and MVP](docs/01-product-and-mvp.md) — scope, priorities, acceptance, and release gates.
2. [Integrations and feasibility](docs/02-integrations-and-feasibility.md) — verified Webull capabilities, polling budget, Telegram, and unresolved checks.
3. [Architecture and data](docs/03-architecture-and-data.md) — local hosting, processing, storage, contracts, and internal API.
4. [Alert catalog](docs/04-alert-catalog.md) — stock/options rules, starter thresholds, explanations, and messages.
5. [Positions and AI OCR](docs/05-positions-and-ocr.md) — screenshot upload, review, reconciliation, and versioning.
6. [AI suggestions and exposure](docs/06-ai-and-risk.md) — candidate generation, risk calculations, examples, and abstention.
7. [Webapp layout and flows](docs/07-ux-and-flows.md) — screens, wireframes, interactions, and failure states.
8. [Testing strategy](docs/08-testing-strategy.md) — replay, integration, OCR/AI evaluation, performance, and release acceptance.
9. [Operations and delivery](docs/09-operations-and-roadmap.md) — secrets, recovery, milestones, and implementation backlog.
10. [Sources and decisions](docs/10-sources-and-decisions.md) — dated primary sources and capability verification checklist.

11. [MVP implementation plan](docs/11-mvp-implementation-plan.md) — ordered tasks, estimates, dependencies, and acceptance gates.

## Explore the design

Open [prototype/index.html](prototype/index.html) in a browser. The self-contained design preview demonstrates the dashboard, rule creation, OCR review, and trade suggestion flow. It uses synthetic data, makes no network requests, and does not accept credentials. See [prototype notes](prototype/README.md).

## Core decisions

- One user, one local service, one Telegram destination initially.
- Your existing OpenAPI key is the starting point; the matching secret and applicable account/data access are verified during implementation.
- Stock streaming plus a small, explicit options polling universe. Options streaming and market-wide options scanning are unverified.
- Show trade facts, inferred direction, coverage, freshness, and exposure together.
- Review OCR before changing positions; compute sizing and risk in deterministic code; use AI to explain validated candidates.
- Manual execution in Webull. Automated order placement is outside this design's MVP.
- This repository can remain on the mapped drive. The attached disk can hold runtime state through its native local host path.

## Files and verification

`docs/` is the specification; `examples/` contains synthetic JSON contracts; `prototype/` is the interactive preview. Run `node scripts/verify-design.cjs` to check local documentation links, JSON syntax, and preview JavaScript syntax.
## Webull access token helper

After setting `WEBULL_ENV`, `WEBULL_APP_KEY`, and `WEBULL_APP_SECRET` in the ignored `.env`, use `node scripts/webull-auth.cjs --dry-run` to see whether a token would be requested. Run `node scripts/webull-auth.cjs` to reuse an accepted token or create and save a replacement only when the value is blank or Webull returns `INVALID_TOKEN` from its read-only account-list API. The helper never prints a token and does not place or preview orders.

A production token starts as pending: complete the prompt in **Webull app → Menu → Messages → OpenAPI Notifications → Check Now**, then enter the SMS code within five minutes. Webull documents this lifecycle and the requirement to reuse active tokens in its [token guide](https://developer.webull.com/apis/docs/authentication/token/).

No production credentials, screenshots, account data, backend, or live API connection are included. This is a local Git repository; remote hosting is optional.

Validation results and limits: [design verification record](VERIFICATION.md).