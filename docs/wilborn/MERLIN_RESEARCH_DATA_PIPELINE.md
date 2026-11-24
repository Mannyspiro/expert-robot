# Merlin public research ingestion and analysis milestone

## Implemented
A bounded ingestion contract for **already-fetched** UTF-8 public text from a fixed HTTPS hostname allowlist. Inputs receive SHA-256 identities, byte limits and duplicate suppression. Deterministic analysis reports counts, source hosts and hashes, with zero verified claims by default.

## Explicit non-capabilities
This code does **not scrape websites**, follow links, crawl, bypass access restrictions, execute JavaScript, call external services, classify PII, verify claims, train weights, or connect to Merlin's live research registry. URL validation is an input contract, **not an SSRF defense** for an HTTP client. Before implementing actual fetches, require DNS/IP egress policy, redirect checks, robots/terms compliance, timeouts, rate limits, bounded pagination, source attribution, and legal/privacy review.

## Next ranked milestones
1. Connect an approved fetch provider with network-level allowlisting and no access to private IPs or metadata endpoints.
2. Add structured CSV/JSON extraction with typed schemas, units, missingness and independent cross-source checks.
3. Add citation-grounded claims, uncertainty and contradiction detection.
4. Link evidence identities to Merlin's canonical task registry and reproducible research ledger.

No real Wilborn customer records are used. Synthetic demo data, public research evidence and verified production records remain separate data classes.
