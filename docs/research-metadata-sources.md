# Research metadata sources

Merlin's research source client retrieves bibliographic metadata from the free
Crossref REST API and arXiv Atom API using only Python's standard library.

## Supported lookups

- Crossref DOI lookup, accepting a DOI, `doi:` prefix, or doi.org URL.
- arXiv lookup, accepting modern IDs, legacy category IDs, version suffixes,
  and arxiv.org abstract/PDF URLs.

## Persistence and request discipline

- SQLite TTL cache with stable source/identifier keys.
- Default cache lifetime: seven days.
- Cache hits do not make network requests.
- Configurable per-provider minimum request intervals; defaults are
  conservative (Crossref 1 second, arXiv 3 seconds).
- User-Agent identification, with optional Crossref `mailto` contact.
- Bounded retry for HTTP 429/503 and numeric `Retry-After`.
- Request timeout and response-size limit.
- Raw-response SHA-256 and canonical metadata SHA-256.
- Transport injection permits fully offline tests.

## Use

```python
from merlin.research_sources import ResearchMetadataClient

with ResearchMetadataClient(
    "~/.cache/merlin/research-metadata.sqlite3",
    mailto="your-contact@example.org",
) as client:
    paper = client.get_by_doi("10.1234/example")
    preprint = client.get_by_arxiv("2301.01234v2")
```

The client does not download full papers or execute code from retrieved
records. Metadata is untrusted input and should be normalized and provenance
tracked before it is used in claims or candidate generation.

The smoke tests use fake HTTP responses and do not call external services.
