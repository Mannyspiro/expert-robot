# Merlin AcademicSpider v0.3 — public scholarly metadata

## What it does

Adds an opt-in OpenAlex client for public scholarly metadata. It queries only
`https://api.openalex.org/works`, maps a small set of fields, and retains
OpenAlex work/author IDs, DOI, ORCID, author display names, affiliations,
publication year, open-access flag, and citation count.

It does not download PDFs, extract full text, access university accounts,
circumvent paywalls, scrape private profiles, or infer private contact details.
A returned open-access flag is metadata, not a guarantee that every linked copy
is currently reachable or reusable.

## Run manually

    PYTHONPATH=python python3 -m merlin.openalex_public --query "geometric combinatorics"
    PYTHONPATH=python python3 -m merlin.openalex_public --query "Lean theorem proving" --per-page 5

No API key is needed for casual public queries. Optional configuration:
- `OPENALEX_API_KEY`: user-provided OpenAlex key, if available.
- `OPENALEX_MAILTO`: optional contact email for OpenAlex's polite pool.

The client makes one request per invocation, defaults to ten records, caps a
single result page at 25, and waits at least one second between calls on a
reused client. It stops on rate-limit responses rather than retrying aggressively.

## Evidence model

OpenAlex records are marked `metadata_discovered`, not verified facts. A DOI
or ORCID is a useful identity key but does not prove that two people with
similar names are the same researcher. Institutional affiliations are recorded
as supplied by OpenAlex and should be checked against an official public profile
before being promoted to institution-verified provenance.

## Next graph step

Connect this adapter to the v0.2 SQLite source store using a separate
`academic_works` table keyed by OpenAlex work ID and unique DOI where present,
plus a many-to-many `work_authors` table keyed by OpenAlex author ID. Preserve
the original API entity IDs and the retrieval timestamp. Do not overwrite
human-reviewed university provenance with API metadata.
