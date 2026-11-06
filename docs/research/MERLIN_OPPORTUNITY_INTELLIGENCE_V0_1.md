# Merlin Opportunity Intelligence v0.1

## Purpose

Build a source-grounded discovery and matching subsystem for three distinct
beneficiaries:

1. The independent insurance agency: public contracts, subcontracting,
   insurance brokerage and risk-management procurements, and genuinely eligible
   business funding.
2. The local community: nonprofit, club, school, public-entity, arts, STEM,
   digital-inclusion, open-technology, amateur-radio, and resilience funding.
3. The individual applicant: scholarships, fellowships, artist opportunities,
   technology awards, and training support.

Initial geographic focus is Tucson and Pima County, Arizona, then statewide
Arizona and national programs. International opportunities may be added as a
separate jurisdictional expansion.

## Applicant profile boundaries

The agency is an independent insurance agency based in Tucson, Arizona. Its
known operating scope is Arizona property-and-casualty insurance. Personal-lines
research may cover California, Georgia, Florida, New York, and Texas, but the
system must not treat research coverage as authority to sell or service risks
in those states. Contract matching must verify business registration, actual
producer/entity licensing, appointments, lines of authority, and solicitation
requirements before recommending a bid.

Individual qualifications supplied for matching include: age 30; woman;
Latina; transgender; amateur-radio operator; Bloomberg Terminal certification;
completed Google coursework; and completed Harvard CS50. Identity attributes
are opt-in eligibility filters only. They must not be inferred, copied into
public application drafts, or exposed in telemetry. The user should be able to
disable identity-based matching independently of the other profile facts.

## Opportunity classes

- Government contract: paid procurement with solicitation, scope, NAICS,
  place of performance, response deadline, and contracting authority.
- Subcontract: opportunity from an existing prime or contract holder.
- Grant: award for an eligible project or organization, normally with
  restrictions and reporting.
- Scholarship: educational award paid under the program's rules.
- Fellowship / training stipend: program participation support.
- Artist opportunity / prize: creative practice, production, exhibition,
  professional development, or competition.

Do not merge these into one generic funding category.

## Discovery sources

### Federal
- SAM.gov Contract Opportunities and entity registration.
- Grants.gov and federal agency notices.
- GSA Forecast of Contracting Opportunities.
- SBA contracting programs and APEX Accelerator support.
- USAspending.gov for historical award research and incumbent discovery.
- SBA SubNet and prime-contractor subcontracting plans.

### Arizona and local
- Arizona Procurement Portal and state agency procurement pages.
- City of Tucson procurement and grant pages.
- Pima County procurement, community development, arts, and workforce pages.
- Arizona Commission on the Arts.
- Arts Foundation for Tucson and Southern Arizona.
- Arizona Community Foundation.
- Arizona amateur-radio associations and educational institutions.

### Individual / education / identity-specific
- Arizona community-college and university scholarship offices.
- Arizona Business and Professional Women's Foundation.
- ARCA amateur-radio scholarships.
- Out to Innovate, oSTEM, Point Foundation, and other LGBTQ+ education
  organizations; verify each current cycle and eligibility rules.
- Women-in-technology, Latina, adult-learner, and creative-technology programs.

## Matching and evidence

The Python module provides an offline typed model. It does not fetch listings
and cannot itself confirm a live opportunity. Every connector must preserve:

- canonical source URL and source organization;
- retrieval timestamp and last-verified timestamp;
- official vs secondary vs unverified source classification;
- opportunity class, applicant type, jurisdiction, status, deadline;
- award amount/range and allowed use, where stated;
- explicit eligibility rules and evidence for each requirement;
- required licenses, credentials, enrollment, fiscal sponsor, and entity type;
- source document digest when content is captured.

Eligibility states are eligible, conditional, or ineligible.
Missing facts produce conditional, not an invented yes. Closed status or
passed deadline blocks a live application recommendation. Secondary listings
must be checked against the official awarding source.

The score is a triage aid, not a prediction of award probability. The ranker
must not use protected identity as a bonus. Identity can only be compared to
explicit program eligibility criteria when the applicant has opted in.

## Initial agency procurement taxonomy

Initial NAICS candidates for discovery are 524210 (Insurance Agencies and
Brokerages), 524292 (Third Party Administration of Insurance and Pension Funds),
and 524298 (All Other Insurance Related Activities). These are search
candidates only; Merlin must verify each code against the actual business
activities and official NAICS definitions before a registration or bid.

Search terms include insurance brokerage, insurance agent, employee benefits,
risk management, insurance administration, commercial insurance, surety,
broker of record, and government contractor insurance. The agency should also
research subcontracting and teaming with established government vendors.
No direct award is implied by a search result.

## Community project design

Potential project families for an eligible partner include:
- amateur-radio and digital communications education;
- STEM and computer-science workshops;
- open-source software and digital inclusion;
- community art and technology installations;
- neighborhood resilience and preparedness education;
- public-interest research and accessible technology.

ARDC and ARRL grant rules differ. ARRL Foundation awards are organization-only
and exclude emergency-communications equipment/facility requests; ARDC
supports broader amateur-radio and digital-communications education and R&D
but requires an eligible organization and open-access approach. Always verify
the active cycle's current rules.

## Human approval and privacy

Merlin may discover, classify, compare, draft, and prepare application
materials. It must not submit bids, grant applications, registrations,
certifications, tax forms, bank details, or attestations without explicit
human approval. No application fees, credentials, banking information, or
identity documents may be transmitted without separate approval.

The system must not fabricate ownership percentages, revenue, employee count,
entity type, SAM registration, certifications, insurance appointments, or
community-partner commitments. It must ask only for missing facts that change
eligibility or the ability to bid.

## Next implementation steps

1. Add official source connectors with rate limits, provenance, and retained
   retrieval logs.
2. Normalize SAM.gov and Grants.gov notices into the common model.
3. Add Arizona Procurement Portal, City of Tucson, Pima County, arts, and
   scholarship connectors.
4. Add an opportunity ledger and deduplication by source ID plus canonical URL.
5. Add alerting for new opportunities, changed deadlines, amendments, and
   approaching close dates.
6. Add a human-reviewed application workspace and evidence checklist.
7. Qualify matching against a held-out set of known eligible/ineligible
   examples; CACE independently verifies source snapshots, parser versions,
   and ranking inputs before production claims.
