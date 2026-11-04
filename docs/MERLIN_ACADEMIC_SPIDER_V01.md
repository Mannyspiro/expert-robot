# Merlin AcademicSpider v0.1

AcademicSpider creates reproducible Google dork query plans for discovering public professor homepages, faculty directories, research groups, publications, preprints, research statements, and lecture notes. The initial registry includes Stanford (stanford.edu), MIT (mit.edu), and Zuse Institute Berlin (zib.de).

## Run

From the repository root:

    PYTHONPATH=python python3 -m merlin.academic_spider --pretty
    PYTHONPATH=python python3 -m merlin.academic_spider --domain ox.ac.uk --name "University of Oxford" --topic "combinatorics" --topic "formal mathematics"

The command prints JSON records with institution, domain, category, raw query, and Google search URL. Results are discovery leads, not a complete census: Google's site: operator searches indexed pages only.

## Data lifecycle

1. Generate scoped query records.
2. Review public search results and collect official profile URLs.
3. Fetch only public pages linked from official university/research pages.
4. Extract researcher identity, institution, research topics, publication links, public resources, retrieval time, and source URL.
5. Deduplicate by canonical URL and stable researcher identifiers.
6. Attach each extracted fact to its source and extraction timestamp.
7. Send topic/publication records to Merlin's ideonomy and evidence pipeline.

## Boundaries

- This release generates queries; it does not automate Google result scraping.
- Do not bypass logins, paywalls, CAPTCHAs, robots exclusions, or access controls.
- A future fetcher must honor each site's robots.txt, terms, rate limits, and response-size/time budgets.
- Store public professional information only; do not infer private contact data.
- Preserve provenance and distinguish indexed search results from verified official profile pages.
- A discovered paper or profile is not proof of a research claim; formal claims proceed through independent checks and Lean.

## Next increments

- v0.2: public URL intake, canonicalization, and provenance records.
- v0.3: robots-aware, low-rate official-page fetcher with strict domain scope.
- v0.4: structured researcher/publication extraction and deduplication.
- v0.5: graph links from researchers to papers, methods, conjectures, and candidate Lean statements, with explicit evidence status.
