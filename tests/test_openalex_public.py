import json
import unittest
from unittest.mock import patch

from merlin.openalex_public import OpenAlexClient, _abstract_free_record


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class OpenAlexPublicTests(unittest.TestCase):
    def sample(self):
        return {
            "id": "https://openalex.org/W123",
            "doi": "https://doi.org/10.1234/example",
            "title": "Graph embeddings and geometry",
            "publication_year": 2025,
            "type": "article",
            "primary_location": {"landing_page_url": "https://journal.example.org/paper"},
            "open_access": {"is_oa": True},
            "cited_by_count": 4,
            "topics": [{"id": "https://openalex.org/T123", "display_name": "Graph theory", "score": 0.91}],
            "authorships": [{
                "author": {
                    "id": "https://openalex.org/A456",
                    "display_name": "Ada Example",
                    "orcid": "https://orcid.org/0000-0000-0000-0000",
                },
                "institutions": [{"display_name": "Example University"}],
            }],
        }

    def test_maps_only_public_metadata_and_author_identifiers(self):
        work = _abstract_free_record(self.sample())
        self.assertEqual(work.title, "Graph embeddings and geometry")
        self.assertEqual(work.authors[0].display_name, "Ada Example")
        self.assertEqual(work.authors[0].institutions, ("Example University",))
        self.assertEqual(work.evidence_status, "metadata_discovered")
        self.assertEqual(work.topics[0].openalex_id, "https://openalex.org/T123")
        self.assertAlmostEqual(work.topics[0].score, 0.91)

    def test_search_uses_https_api_and_small_page_size(self):
        seen = {}
        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            return FakeResponse({"results": [self.sample()]})
        client = OpenAlexClient(opener=opener, min_interval_seconds=0)
        rows = client.search_works("graph embeddings", per_page=5)
        self.assertEqual(len(rows), 1)
        self.assertTrue(seen["url"].startswith("https://api.openalex.org/works?"))
        self.assertIn("per_page=5", seen["url"])
        self.assertNotIn("api_key=", seen["url"])

    def test_optional_api_key_and_mailto_are_not_required(self):
        seen = {}
        def opener(request, timeout):
            seen["url"] = request.full_url
            return FakeResponse({"results": []})
        OpenAlexClient(api_key="test-key", mailto="research@example.org",
                       opener=opener, min_interval_seconds=0).search_works("topology")
        self.assertIn("api_key=test-key", seen["url"])
        self.assertIn("mailto=research%40example.org", seen["url"])

    def test_rejects_empty_or_oversized_query_and_page_size(self):
        client = OpenAlexClient(opener=lambda *a, **k: FakeResponse({"results": []}))
        for query, page in [("", 10), ("topology", 26)]:
            with self.assertRaises(ValueError):
                client.search_works(query, per_page=page)


if __name__ == "__main__":
    unittest.main()
