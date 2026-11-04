# Merlin AcademicSpider v0.2 — provenance-backed URL intake

## Scope

v0.2 adds a local SQLite store for public academic URLs that have already been
reviewed from search results or official university pages. It deliberately does
not fetch arbitrary URLs or scrape Google. Professor personal sites may be on
external domains, but the `discovered_from` URL must remain on the registered
institution domain.

## CLI

Add a reviewed public source:

    PYTHONPATH=python python3 -m merlin.academic_source_store add \
      --institution "Stanford University" --domain stanford.edu \
      --type personal_homepage \
      --url "https://math.example.org/~researcher/" \
      --discovered-from "https://www.stanford.edu/math/faculty/" \
      --researcher "Researcher Name" \
      --topic combinatorics --topic geometry

List the registry:

    PYTHONPATH=python python3 -m merlin.academic_source_store list
    PYTHONPATH=python python3 -m merlin.academic_source_store list --domain stanford.edu

The example URL is illustrative; use only URLs verified from actual public pages.

## Record contract

Each record stores the submitted URL, canonical URL, institution and domain,
source type, official discovery/provenance URL, optional title and researcher,
topics, evidence status, and capture timestamp. Canonical URL is unique, so
tracking parameters/fragments do not create duplicate records. Repeated intake
updates the same record.

Allowed source types: faculty_profile, personal_homepage, research_group,
publication, preprint, lecture_notes, project.

Evidence states: discovered, reviewed, verified_official, rejected.
A page is not automatically verified merely because it was indexed or submitted.

## Design debate

**Research-mining view:** store external professor homepages when a university
directory links to them; otherwise valuable researcher pages hosted on personal
domains would be missed.

**Provenance-first view:** do not accept an external URL as a university
discovery unless the official institutional page that linked to it is recorded.
This prevents search snippets from silently becoming institutional facts.

**Decision:** allow external target domains, but require the discovery source to
be within the institution's registered domain. Keep evidence state explicit.

## Safety and operational boundaries

- The module performs no network requests.
- Only HTTP(S) URLs are accepted; embedded credentials are rejected.
- It stores public professional research metadata, not private contact details.
- Do not fetch a URL until a later fetcher checks robots.txt, site terms, scope,
  response size, timeouts, and rate limits.
- Store provenance at record level; don't turn a research topic label into a
  verified claim.
