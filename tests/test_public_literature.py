import json
import unittest
from urllib.parse import urlparse, parse_qs

from python.merlin.public_literature import PublicLiteratureSearch


class FakeResponse:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body[:size]


class PublicLiteratureSearchTests(unittest.TestCase):
    def test_crossref_search_needs_no_credentials_and_preserves_provenance(self):
        body = json.dumps({
            "message": {"items": [{
                "title": ["A Test Paper"],
                "DOI": "10.5555/example",
                "author": [{"given": "Ada", "family": "Lovelace"}],
                "published": {"date-parts": [[2025, 4, 1]]},
            }]}
        }).encode()

        def opener(request, timeout):
            self.assertEqual(urlparse(request.full_url).hostname, "api.crossref.org")
            self.assertNotIn("api_key", parse_qs(urlparse(request.full_url).query))
            self.assertIn("User-Agent", request.headers)
            return FakeResponse(body)

        search = PublicLiteratureSearch(opener=opener, cache_ttl_seconds=0)
        result = search.search("formal verification", source="crossref", limit=5)
        self.assertFalse(result["credentials_required"])
        self.assertEqual(result["results"][0]["source_id"], "doi:10.5555/example")
        self.assertEqual(result["results"][0]["evidence_class"], "OBSERVED_DOCUMENT")
        self.assertEqual(result["results"][0]["claim_verification"], "NOT_VERIFIED")
        self.assertEqual(len(result["source_response_sha256"]["crossref"]), 64)

    def test_arxiv_search_parses_atom_and_records_source_id(self):
        body = b"""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>https://arxiv.org/abs/2601.01234v2</id>
            <title>  A Quantum Test  </title>
            <summary> Abstract text </summary>
            <published>2026-01-02T00:00:00Z</published>
            <author><name>A. Researcher</name></author>
          </entry>
        </feed>"""

        def opener(request, timeout):
            self.assertEqual(urlparse(request.full_url).hostname, "export.arxiv.org")
            return FakeResponse(body)

        result = PublicLiteratureSearch(
            opener=opener, cache_ttl_seconds=0
        ).search("quantum test", source="arxiv", limit=3)
        self.assertEqual(result["results"][0]["source_id"], "arxiv:2601.01234v2")
        self.assertEqual(result["results"][0]["authors"], ["A. Researcher"])
        self.assertEqual(result["results"][0]["claim_verification"], "NOT_VERIFIED")

    def test_invalid_queries_sources_and_limits_are_rejected(self):
        search = PublicLiteratureSearch(opener=lambda *_args, **_kwargs: self.fail("network called"))
        for query in ("", "x", "  "):
            with self.assertRaises(ValueError):
                search.search(query)
        with self.assertRaises(ValueError):
            search.search("valid query", source="unknown")
        with self.assertRaises(ValueError):
            search.search("valid query", limit=21)

    def test_failed_source_is_reported_without_fabricating_results(self):
        def fail(*_args, **_kwargs):
            raise OSError("network unavailable")

        result = PublicLiteratureSearch(
            opener=fail, cache_ttl_seconds=0
        ).search("network outage test", source="crossref")
        self.assertEqual(result["results"], [])
        self.assertEqual(result["errors"], [
            {"source": "crossref", "error_class": "OSError"}
        ])

    def test_response_size_is_bounded(self):
        body = b"x" * (2_000_001)

        def opener(*_args, **_kwargs):
            return FakeResponse(body)

        result = PublicLiteratureSearch(
            opener=opener, cache_ttl_seconds=0
        ).search("bounded response test", source="crossref")
        self.assertEqual(result["results"], [])
        self.assertEqual(result["errors"][0]["error_class"], "ValueError")


if __name__ == "__main__":
    unittest.main()
