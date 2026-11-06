# Merlin partner qualification evidence report — Arizona public-sector benefits

**Evidence cut-off:** 2026-11-05  
**Repository branch:** `feat/merlin-opportunity-intelligence-v01-20261106`  
**Purpose:** Public-record-based partner discovery and qualification. No outreach, registration, proposal submission, or vendor contact was performed.

## Executive finding

This is a traceable **partial qualification report**, not a declaration that any firm is qualified to partner. Public award and cooperative-contract records have been imported for Alliant, CBIZ Optumas, CapFi Consulting, and HUB International. The official Arizona DIFI license-search workflow has been identified, and a normalized CSV ingestion adapter has been implemented. However, **no dated DIFI license observations have yet been captured for any candidate entity or responsible individual**. It would be misleading to claim actual license verification without the exact public registry record.

All candidates therefore remain on hold for license/appointment evidence and teaming permission. Competitors and capability benchmarks are kept separate from potential primes. No individual producer is named or inferred from contract contacts.

## Official licensing source and ingestion status

Arizona DIFI's [License Search](https://difi.az.gov/license-search) directs users to NAIC State Based Systems. It distinguishes an insurance licensee (individual or business entity) from an insurance company. The documented lookup workflow is Arizona jurisdiction, Search Type = Licensee, then Entity Type = Individual or Entity. The page does not expose a documented public machine-readable API in the material reviewed.

The new `merlin.partner_evidence_pipeline.ingest_difi_normalized_csv` adapter accepts a dated public lookup export after normalization to explicit fields: subject ID/type, legal name, license number/type, lines of authority, status, source record ID, and effective date. It hashes each imported row and binds it to the DIFI/SBS source URL and observation date. It does not automate login, bypass access controls, scrape interactive search results, or invent a result.

**DIFI observation result as of this report:** zero entity records and zero responsible-individual records imported. The names below are public supplier names, not evidence of producer identity. Responsible producers must be identified from an authoritative entity/agency record or other public filing before their individual license records can be joined.

Official source: [Arizona DIFI License Search](https://difi.az.gov/license-search). DIFI's public-records page also explains that certain private information is confidential and must not be collected or republished: [DIFI Public Records](https://difi.az.gov/prr).

## Public contract and cooperative evidence imported

The source records below are public contract/award evidence, not proof of quality, past performance, license status, appointments, or willingness to subcontract.

| Candidate | Record | Public source and finding | Graph treatment |
|---|---|---|---|
| Alliant Insurance Services | CTR069812 — Insurance Broker Services | [SPO award alert](https://spo.az.gov/sites/default/files/2025-05/SPO%20Alert%20-%20Contract%20Award_%20Insurance%20Broker%20Services.pdf), dated 2024-02-07; initial term 2024-02-01 through 2027-01-31, available to state agencies and co-op members | Potential competitor; capability benchmark |
| Alliant Insurance Services | CTR066530 — Statewide Healthcare and Employee Benefit Consulting | [SPO contract record](https://spo.az.gov/ctr066530); statewide and co-op designated; current end 2027-06-30, maximum end 2028-06-30 | Potential competitor; capability benchmark |
| CBIZ Optumas LLC | CTR066534 — Statewide Healthcare and Employee Benefit Consulting | [SPO contract record](https://spo.az.gov/ctr066534); active; co-op designated; current end 2027-06-30, maximum end 2028-06-30 | Potential competitor; capability benchmark |
| CapFi Consulting | 1GPA 24-05P-02 — Employee Benefits Broker/Consultant Services | [1GPA vendor record](https://1gpa.org/vendor/capfi-consulting/); displayed expiry 2028-12-04 | Potential prime; legal contracting entity not yet confirmed |
| HUB International Insurance Services | 1GPA 24-05P-03 — Employee Benefits Broker/Consultant Services | [1GPA vendor record](https://1gpa.org/vendor/hub-international-insurance-services/); displayed expiry 2028-12-04 | Potential prime; exact contracting entity not yet confirmed |

The State Procurement Office explains that its contract search is updated monthly until a real-time solution is available, while APP is the real-time source for contract data: [SPO Contracts](https://spo.az.gov/contracts). The cooperative program describes how eligible members use state contracts: [Arizona Cooperative Program](https://spo.az.gov/programs/cooperative/cooperative-program).

The contract evidence JSON is in `data/merlin/partner_contract_evidence_2026-11-05.json`. The relationship graph is in `data/merlin/partner_graph_2026-11-05.json`.

### Reference evidence limitation

A public award or active cooperative contract is not a client reference. No performance reference has been marked verified. The data model requires a separate public contracting-authority or client-reference source and an explicit performance verification flag before that evidence can affect the performance component of ranking.

## Relationship-aware ranking

The graph uses distinct cohorts:

- **Competitor:** a market participant with overlapping services; not a teaming candidate by default.
- **Capability benchmark:** a source of public capability signals; not an endorsement or partnership relationship.
- **Potential prime:** a candidate with a public contract/market signal that may warrant future qualification; no teaming permission is implied.
- **Potential subcontractor:** requires explicit scope complementarity and verified permission; no candidate is presently qualified in this cohort.
- **Referral source:** requires a documented basis and conflict review.

Ranking is cohort-aware and explainable. Public awards, cooperative contracts, active official license observations, and verified performance references contribute separate signals. A high score cannot change qualification state or authorize selection. Competitors/benchmarks remain benchmark-only.

## Solicitation and addenda ingestion

The code now supports clause-linked ingestion of already-extracted official solicitation text. Each clause stores solicitation ID, clause ID, heading, source URL, observation date, addendum flag, document name, and SHA-256 of the extracted text.

For City of Maricopa RFP 26-102626-RFP-HR, the official posting describes the employee-benefits scope and reports a November 23, 2026 5:00 PM Arizona deadline. It requires sign-in/registration to view the full specifications: [official posting](https://www.egovlink.com/maricopa/postings_info.asp?dlistid=1675&listtype=BID&posting_id=5761&sc_category_id=&sc_show_expired=Y&sc_status_id=122). The official bid-opportunities page is [here](https://www.maricopa-az.gov/Departments/Finance/Bid-Opportunities).

**No RFP specification or addendum file has been ingested in this report**, because the official full specification attachment was not publicly retrievable without portal access. Secondary summaries are not treated as official clauses. When an authorized official file is supplied or made publicly accessible, the parser can split extracted text into clauses; a PDF/DOCX extraction adapter and original-byte hash binding remain required before full document ingestion is production-complete.

## Proposal evidence vault

`ProposalEvidenceVault` registers source artifacts by evidence ID, HTTPS source URL, SHA-256 digest, and source type. Claims with no evidence or unknown evidence IDs are blocked. Claims with registered sources move only to `human_review_required`; the vault does not certify truth, draft unsupported credentials, or submit a proposal. Source maps retain the exact claim-to-source links.

Required production extension: bind each source to original bytes, extraction version, source timestamp, page/paragraph/clause locator, legal entity identity, and independent review receipt. Pricing, certifications, insurance limits, references, and claims of past performance must be independently checked and explicitly approved.

## Learning loop and privacy boundary

The learning aggregator measures source accuracy, qualification outcomes, partner performance, and proposal outcomes from non-private observations. Private rows are excluded from the aggregate. The result explicitly records `authority_change: none` and `human_approval_required: true`.

Learning may adjust source reliability estimates, retrieval ordering, and ranking weights after held-out evaluation. It may not silently expand user authority, infer licenses, alter an applicant's legal status, contact firms, register on portals, make proposal commitments, or submit bids. Personal and sensitive identity attributes are not copied into the public partner graph or telemetry.

## Remaining evidence gates before any partner can be recommended

1. Exact contracting legal name and entity identifier crosswalk.
2. DIFI/SBS entity license record, dated and hashed.
3. Each responsible producer's individual license record, relevant lines of authority, status, and public appointment evidence where available.
4. Scope-specific authority for the actual proposed work; do not treat P&C authority as employee-benefits authority.
5. Public-sector performance references with a contracting-authority/client source and clear scope/outcome.
6. Written teaming permission and exact role/scope.
7. Conflict review, capacity, insurance, indemnity, cybersecurity, and contract-flowdown review.
8. Full official solicitation and all addenda, clause-by-clause evidence matrix, and human-approved proposal claims.

## Implementation status

- DIFI normalized export ingestion: implemented; no candidate observations yet.
- Public award/cooperative evidence: initial Arizona records imported; no verified performance references.
- Relationship-aware ranking: implemented; rankings remain separate from qualification decisions.
- RFP text clause ingestion: implemented for extracted text; official attachments not yet imported.
- Proposal evidence vault: implemented as a fail-closed provenance gate; original-file/page locators and independent review still needed.
- Learning loop: aggregate-only prototype; requires held-out evaluation and governance before weights are used in production.
- CI: latest attempts are being cancelled before a job log or artifact is available. No passing result is claimed for the new partner pipeline until a completed run retains the verbose log and result JSON.

## Reproducible artifacts

- `python/merlin/partner_qualification.py`
- `python/merlin/partner_evidence_pipeline.py`
- `tests/test_partner_qualification.py`
- `tests/test_partner_evidence_pipeline.py`
- `data/merlin/partner_contract_evidence_2026-11-05.json`
- `data/merlin/partner_graph_2026-11-05.json`
- CI artifact pattern: `merlin-opportunity-intelligence-*`, uploaded with `if: always()`.


## CI evidence update — 2026-11-06

The Avrea-backed `build-and-smoke` job was not started because the Avrea organization reported **no credits available**. This is an infrastructure/billing block, not a test failure. The new independent GitHub-hosted partner test job was therefore rerun directly.

- Workflow run: [CI #2747](https://github.com/Mannyspiro/expert-robot/actions/runs/42173547085)
- Commit under test: `39e932b16c042f9830859cd699b3b9b5dcd5b46e`
- Partner evidence job: all five suites passed.
- Test totals: opportunity 13, procurement readiness 6, source status 5, partner qualification 7, partner evidence pipeline 8 — **39 tests passed**.
- All five suite exit codes: `0`; aggregate exit code: `0`.
- Retained artifact: `merlin-partner-evidence-42173547085`, artifact ID `13482370509`.
- Artifact SHA-256: `434ef90109e307efc00e34f019f92f9d061539da0d940ae006f34adf09983ab5`.
- Artifact contents: verbose test log, per-suite exit-code file, and valid machine-readable JSON result.
- The overall workflow run remains marked cancelled because the separate Avrea job did not start; the GitHub-hosted partner test job's steps completed successfully and the evidence artifact was uploaded.

This is a passing result for the partner evidence suites only. It does **not** certify the full C++/Avrea CI pipeline.


## Latest verification after contract-importer fix — CI #2747

The normalized contract-record importer was corrected and its test added. The rerun of the GitHub-hosted partner job completed the test step successfully:

- [CI run #2747](https://github.com/Mannyspiro/expert-robot/actions/runs/42173547085)
- Commit tested: `39e932b16c042f9830859cd699b3b9b5dcd5b46e`
- 39 total tests passed across the five suites: 13 + 6 + 5 + 7 + 8.
- All five suite exit codes and the aggregate result JSON are zero.
- Artifact ID: `13482370509`; artifact SHA-256: `434ef90109e307efc00e34f019f92f9d061539da0d940ae006f34adf09983ab5`.
- The artifact includes the verbose log, exit-code file, and valid JSON result.

The full workflow remains cancelled because Avrea's runner had no available credits; the GitHub-hosted partner test job and its artifact completed. The report's licensing limitation remains unchanged: no candidate DIFI entity or responsible-individual record has yet been imported, so no candidate is license-qualified.
