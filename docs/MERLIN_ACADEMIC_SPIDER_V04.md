# Merlin AcademicSpider v0.4 — normalized scholarly graph

## Scope

This increment ingests the existing OpenAlex work result objects into a local
SQLite graph. It creates nodes for works, researchers, and institution names,
plus edges for authorship and researcher-institution associations.

The source of every node is retained as OpenAlex public metadata, with a
retrieval timestamp and an explicit `metadata_discovered` evidence status.
This does not assert that an author affiliation is current or that two author
IDs with similar names identify the same person.

## Run

After a public metadata query has been reviewed, use the Python API:

    from merlin.academic_graph import AcademicGraphStore
    from merlin.openalex_public import OpenAlexClient

    works = OpenAlexClient().search_works("geometric combinatorics", per_page=5)
    graph = AcademicGraphStore("data/merlin_academic_sources.sqlite3")
    for work in works:
        graph.ingest(work)
    print(graph.stats())

The network call is explicit and opt-in. The graph store itself is local-only.

Inspect graph totals:

    PYTHONPATH=python python3 -m merlin.academic_graph

## Graph rules

- OpenAlex W and A identifiers are stable external identity keys.
- Names are labels, not identity keys; equal names are never merged automatically.
- DOI collisions across distinct OpenAlex work IDs are surfaced as errors.
- Re-ingesting a work updates its metadata and replaces only its authorship edges.
- Institutional names are associated as reported in the work's authorship metadata.
- All records remain metadata-discovered until separately checked against public
  primary sources.

## Public-data boundaries

No private profiles, account-only resources, paywall bypass, access-control
circumvention, or private contact details. The adapter does not fetch full text.
The API's nested authorships are the work-author-institution join, not a claim
that an author currently works at that institution. OpenAlex documents these
as per-work byline affiliations.

## Next iteration

Add topic nodes and work-topic edges from the public OpenAlex `topics` field,
then a separate hypothesis layer that records proposed cross-field connections
with supporting works, counterexamples, and a reproducible test. Hypotheses
must remain distinct from source facts and verified mathematical results.
