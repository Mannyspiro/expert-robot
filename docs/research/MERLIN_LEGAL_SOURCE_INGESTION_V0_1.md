# Merlin Legal Source Ingestion — Adapter Contract v0.1

## Implemented contract

`python/merlin/legal_source_ingestion.py` provides:
- an explicit allowlist for official federal and Arizona legal-source hosts;
- GovInfo bulk-index candidate generation for the Federal Register, CFR, U.S. Code, Statutes at Large, public laws and congressional collections;
- Arizona Administrative Register source candidates;
- bounded capture manifests with retrieval timestamp, canonical and final URLs, byte length, SHA-256, parser version and permitted-use decision;
- fail-closed URL validation for non-HTTPS, unknown hosts, embedded credentials, custom ports and off-allowlist redirect targets;
- metadata-only default retention, with retained bytes allowed only when policy and permitted-use metadata explicitly authorize it.

This is a deterministic adapter contract and manifest builder. It is not yet a network downloader, parser, or complete corpus ingestion. Network retrieval must run in isolated Avrea workers, apply timeouts and response-size limits, verify final redirect hosts, and store content only when permitted.

## Federal source acquisition

GovInfo exposes an API for package discovery and retrieval, and bulk XML for the Federal Register, annual CFR, eCFR, Statutes at Large, statutory compilations, bill text and status. The API uses an api.data.gov key. Prefer public bulk indexes for broad ingestion where they provide adequate metadata; use API package retrieval for targeted queries and incremental updates. Keep the API key in the secret manager and never write it into job logs or source manifests.

Official references:
- https://www.govinfo.gov/developers
- https://www.govinfo.gov/bulkdata/
- https://github.com/usgpo/api
- https://www.archives.gov/federal-register/cfr/about.html

## Arizona source acquisition

Use the Arizona Secretary of State's authenticated Administrative Register as the rulemaking-history source. Its weekly issues include proposed, final, emergency and exempt rulemaking, notices, guidance notices and a cumulative index. The Secretary of State identifies the authenticated electronic Register as official; it also specifies commercial-use terms. Therefore, default to metadata and links until the intended use is reviewed.

Use Arizona Legislature sources for statutes and session laws; preserve session-law chapter and effective-date records separately from the current codified section. Use Arizona Courts' official opinions and court-rule sources for judicial and procedural materials.

Official references:
- https://azsos.gov/rules/arizona-administrative-register
- https://apps.azsos.gov/public_services/register/2026/contents.htm
- https://www.azleg.gov/
- https://www.azcourts.gov/opinions
- https://www.azcourts.gov/rules

## Next network milestone

1. Configure a GovInfo API key as a managed secret.
2. Build Avrea jobs that retrieve only allowlisted indexes/packages.
3. Add XML parsers pinned to published schemas and parser versions.
4. Persist metadata and permitted artifacts in Merlin's canonical registry.
5. Add incremental update feeds and sitemap checkpoints.
6. Add Arizona Register issue and rulemaking-docket extraction.
7. Add historical version resolution and source-to-source amendment links.
8. Send extracted provisions and candidate claims to CACE for independent review.

## Acceptance gates

- Every captured artifact has exact URL, timestamp, content type, byte count and digest.
- Redirects cannot escape the host allowlist.
- No secrets are logged or stored in manifests.
- No source bytes are retained without a positive permitted-use decision.
- A failed or partial acquisition is recorded as a failed/partial job, not silently omitted.
- Parser output includes parser and schema versions.
- Ingestion does not promote legal claims to independently verified.
