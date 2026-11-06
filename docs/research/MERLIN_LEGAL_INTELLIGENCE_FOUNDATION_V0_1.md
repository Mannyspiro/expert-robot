# Merlin Legal Intelligence — Foundation v0.1

**Status:** implementation foundation and research specification. This document is not a legal opinion, legal advice, or evidence that any live legal corpus has been completely ingested.

## Objective

Build a broad, academically deep legal research capability spanning legal foundations, constitutional law, jurisprudence, private law, criminal law, procedure, evidence, administrative law, business, employment, family, tax, intellectual property, environmental, insurance, health, international, comparative, remedies, professional responsibility and legal history.

Initial coverage:
1. United States federal law.
2. Arizona as the first complete state pilot.
3. Remaining 49 states and DC through a repeatable jurisdiction ingestion contract.
4. Tribal legal systems, treaties and jurisdictional relationships.
5. Comparative international legal systems, preserving local concepts rather than flattening them into U.S. categories.

## Required research dossier

Every subject dossier must contain:
- definition, purpose and policy rationale;
- historical origins and development;
- elements, tests, burdens and standards;
- exceptions, defenses and limitations;
- primary authority and source hierarchy;
- secondary scholarship and competing theories;
- jurisdictional comparison;
- hypothetical applications and counterarguments;
- current status, effective dates and subsequent treatment;
- uncertainty register and missing research.

## Evidence and authority model

Use primary authority first: constitutions, enacted statutes, regulations, court opinions, procedural rules, treaties and official agency orders. Secondary sources include treatises, Restatements, law reviews, legal encyclopedias, empirical studies and scholarly books.

Do not conflate:
- binding authority with persuasive authority;
- holding with dicta;
- enacted text with proposed legislation;
- agency guidance with binding regulation;
- allegation with adjudicated finding;
- a source quotation with semantic support for a proposition;
- a current rule with the rule applicable on a historical date.

Every source record retains its canonical URL, jurisdiction, source type, publication and retrieval timestamps, effective interval, edition/version, authority status, citation, hash when lawful to retain, and permitted-use metadata.

## Knowledge graph

Core entities:
- Jurisdiction, LegalSource, LegalProvision, LegalCase, Doctrine, LegalClaim;
- elements, exceptions, remedies, procedures, interpretations and scholarly works;
- source versions, amendments, repeals, citations and subsequent treatment;
- evidence receipts, reviewers, test artifacts and unresolved questions.

Relationships:
- governs, contains, interprets, cites, amends, repeals, supersedes;
- establishes, limits, distinguishes, applies_to, requires, permits;
- supported_by, contradicted_by, qualified_by, reviewed_by.

The Python implementation in `python/merlin/legal_intelligence.py` provides typed records and graph referential-integrity checks. It intentionally does not assert semantic truth.

## Temporal legal reasoning

A legal answer must identify the relevant as-of date. Store source-level and provision-level effective intervals. Do not infer that a current codification governed a past event. Preserve publication, enactment, effective, amendment, repeal, retrieval and decision dates as distinct fields.

Case-law status must be explicit: binding, persuasive, nonbinding, vacated, overruled, superseded, historical or unknown. A production citator must retrieve and verify subsequent treatment; a manually supplied status is not enough.

## Independent verification

The research agent and verifier must be separate. CACE review must bind:
- exact claim-set digest;
- source IDs and content digests;
- provision and case IDs;
- jurisdiction and as-of date;
- reviewer identity and role;
- verifier version and review outcome;
- counterauthority search record;
- authenticated signature and key-validity/revocation evidence.

A SHA-256 digest establishes content identity, not signer identity, source authenticity or legal correctness. The truth gate remains closed until the production CACE receipt verifier authenticates an independent review. Test callbacks are not production authentication.

## Research ingestion workflow

1. Discover authoritative source repositories for the jurisdiction and field.
2. Capture canonical URL, retrieval time, source metadata and lawful content snapshot.
3. Preserve original bytes when permitted; otherwise preserve URL, metadata and permitted citation/excerpt only.
4. Hash captured bytes and record parser/extractor version.
5. Extract provisions, opinions, citations, procedural posture and relevant dates.
6. Link amendments, repeals, cases and subsequent treatment.
7. Generate doctrine and claim candidates with traceable evidence.
8. Search for contrary authority and exceptions.
9. Run temporal, jurisdictional and citation validation.
10. Submit the exact claim set for independent CACE review.
11. Promote only after authenticated review; otherwise retain as research lead, source-supported, contested or inconclusive.

Respect source terms, licensing, copyright, database restrictions, robots/access rules and privacy. Do not scrape or republish restricted legal databases.

## Arizona pilot

The Arizona pilot should include:
- Arizona Constitution and amendment history;
- Arizona Revised Statutes with historical versions and effective dates;
- Arizona Administrative Code and Register materials;
- Arizona Supreme Court and Court of Appeals opinions;
- Arizona Rules of Civil Procedure, Criminal Procedure, Evidence, Appellate Procedure and local rules;
- agency orders, official guidance and administrative decisions;
- federal district/circuit/Supreme Court authority applicable in Arizona;
- tribal law and jurisdictional materials relevant to Arizona, handled as distinct sovereign legal systems.

Do not label the pilot complete until coverage is measured by field, source type, date range, court, agency and source completeness.

## Evaluation suite

Held-out, specialist-reviewed tests should include:
- statutory interpretation and amendment history;
- case briefing, holding/dicta distinction and procedural posture;
- binding-versus-persuasive authority;
- conflicting authority and contrary cases;
- jurisdiction and choice-of-law;
- temporal-law questions;
- legal deadline calculations;
- civil and criminal procedure;
- contract, tort, property, evidence and administrative-law hypotheticals;
- comparative-law translation and false-equivalence detection;
- legal memorandum writing and citation validation;
- correct abstention when primary authority is missing.

Track citation precision, proposition support, omitted exceptions, temporal errors, jurisdiction errors, counterauthority recall, reasoning quality and abstention calibration.

## Merlin integration

- Canonical registry: legal sources, source snapshots, cases, provisions, claims and dossier artifacts.
- Knowledge graph: typed legal nodes and edges; no parallel legal-only registry.
- Hermes: research task decomposition, jurisdiction routing, source discovery and review queues.
- Avrea: isolated parsers, document extraction, citation graph construction and benchmark execution.
- CACE: independent artifact/provenance/review receipt verification.
- HUD: show source coverage, authority status, effective dates, contradictions, research branches, review status and unresolved issues.

## Acceptance gates

- All records validate against typed schemas.
- No provision or claim may reference an unknown source/case/provision.
- Every claim includes jurisdiction and as-of date.
- Every legal source includes retrieval time and canonical HTTPS URL.
- Every source with retained bytes has a verified content digest.
- Historical queries resolve source/provision versions valid on the requested date.
- Contrary authority is represented, not silently discarded.
- Semantic truth is never inferred from quote matching.
- CACE authentication is required for independently verified status.
- Every CI attempt retains test logs and results.
