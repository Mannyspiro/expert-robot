# Merlin public finance and Kalshi research v0.1

## Scope

This increment adds reusable, offline-first primitives for public financial
research. It does not fetch network data, authenticate to user accounts, place
orders, provide personalized investment advice, or change Merlin's authority.

## Reuse of existing infrastructure

- The existing economic source registry remains the source catalogue.
- AcademicSourceStore remains the public URL-discovery index.
- MerlinRegistry remains the content-addressed project artifact store.
- ResearchEvidenceRecorder remains the hypothesis/evidence/knowledge-graph bridge.
- This module adds a point-in-time data layer where historical release availability
  and revisions must be represented explicitly.

The next integration should write raw snapshot bytes to the canonical Merlin
artifact registry and record the returned artifact digest in CACE evidence.
This initial SQLite store is an isolated adapter prototype, not a second
canonical project registry.

## Point-in-time data contract

A raw source snapshot binds source ID and HTTPS URL; retrieved and published
timestamps; SHA-256 digest and byte length; and an affirmative terms-review flag.

A normalized observation binds source ID and raw snapshot digest; entity and
metric identifiers; period start/end; available_at timestamp (when the value
became publicly knowable); value, unit, currency and vintage.

Historical queries filter on available_at <= cutoff and select the latest
available vintage for each period. They must not use period end as a proxy for
publication time. A revision published after the backtest cutoff is excluded.

The prototype requires source terms review before retaining bytes. A production
connector must additionally retain provider version, query parameters, response
headers, retrieval identity, source license/terms, parser version, and CACE
receipt. API keys belong in the approved secret manager and never in source,
fixtures, logs or committed configuration.

## Source adapter rollout

Use the existing merlin-economic-data-source-registry.v1.json entries:
1. SEC EDGAR and XBRL company facts (submission and filing acceptance times).
2. FRED/ALFRED (series metadata and vintage dates; inspect original source).
3. BLS (release timestamps, seasonal-adjustment series and revisions).
4. BEA (release schedules and revised national/regional accounts).
5. Treasury rates and Federal Reserve Z.1.
6. EIA energy series, CFTC Commitments of Traders, Census and USAspending.

Implement adapters as pure parsers over captured responses first. Then run
network retrieval only in isolated Avrea jobs with rate limits, source terms
checks, bounded response sizes and reproducible receipts. Do not scrape
authenticated pages, evade access controls, or treat search snippets as source
evidence.

## BMC-inspired curriculum and public search

The curriculum spans macroeconomics, FX, fixed income, equities, commodities,
derivatives, portfolio management, market microstructure and prediction-market
probability. Search templates use ordinary public search operators and official
domains; they are discovery prompts, not authorization to bypass access controls.
Exclude credentials, private personal data, leaked material and restricted content.

## Kalshi research method

For a binary contract with YES ask ay, NO ask an, independent YES probability p,
and applicable per-contract fee f:

- YES net edge estimate = p - ay/100 - f.
- NO net edge estimate = (1-p) - an/100 - f.

Use executable asks, not last trades or displayed midpoint. Before promoting a
candidate, validate exact rules and settlement source, quote timestamp, depth,
fees, market status and event deadline. Estimate probability independently,
retain model uncertainty, and backtest calibration and net performance against
historical quotes and final settlements. The helper is a screening calculation
only: it does not model depth, slippage, tax, capital lockup, correlation,
probability uncertainty or settlement disputes.

## Acceptance criteria for production integration

- Every ingested release has raw bytes, source identity, retrieval timestamp,
  publication/availability timestamp, hash and terms metadata.
- Point-in-time queries reproduce historical values and exclude later revisions.
- Adapters have fixture-based parser tests and schema-drift tests.
- Kalshi comparisons use executable ask/depth and correct fee schedule.
- Forecasts are evaluated with Brier score, log loss, calibration curves and
  strictly out-of-sample backtests.
- Avrea records exact code, input, environment, runtime and output hashes.
- CACE independently verifies raw and transformed artifacts.
- Hermes dispatches only approved bounded research jobs; no trading endpoint or
  automatic order execution is introduced.
- Failed fetches, parse errors, rejected sources and failed tests retain logs
  and evidence artifacts.
