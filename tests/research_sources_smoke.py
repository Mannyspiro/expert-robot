#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from merlin.research_sources import (  # noqa: E402
    HttpResponse,
    MetadataFetchError,
    ProviderRateLimiter,
    ResearchMetadataClient,
)


class FakeClock:
    def __init__(self, value: float = 100.0):
        self.value = value
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds

    def now(self) -> float:
        return self.value


class FakeTransport:
    def __init__(self, responses: list[HttpResponse]):
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str], float]] = []

    def __call__(self, url, headers, timeout):
        self.calls.append((url, dict(headers), timeout))
        if not self.responses:
            raise AssertionError("unexpected extra HTTP request")
        return self.responses.pop(0)


class ResearchSourcesSmoke(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache = Path(self.temp.name) / "metadata.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def test_crossref_fetch_and_cache(self):
        body = json.dumps({
            "message": {
                "DOI": "10.1234/example",
                "title": ["A Test of Relational Mathematics"],
                "author": [
                    {"given": "Ada", "family": "Lovelace"},
                    {"given": "Alan", "family": "Turing"},
                ],
                "published-print": {"date-parts": [[2025, 4, 9]]},
                "abstract": "<jats:p>Typed <jats:italic>relations</jats:italic> matter.</jats:p>",
                "URL": "https://doi.org/10.1234/example",
            }
        }).encode()
        transport = FakeTransport([HttpResponse(200, {}, body)])
        clock = FakeClock()
        limiter = ProviderRateLimiter(
            {"crossref": 0, "arxiv": 0},
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )
        client = ResearchMetadataClient(
            self.cache, transport=transport, limiter=limiter,
            now=clock.now, sleep=clock.sleep, mailto="research@example.org",
        )
        first = client.get_by_doi("https://doi.org/10.1234/EXAMPLE")
        second = client.get_by_doi("doi:10.1234/example")
        self.assertEqual(first.title, "A Test of Relational Mathematics")
        self.assertEqual(first.authors, ("Ada Lovelace", "Alan Turing"))
        self.assertEqual(first.published, "2025-04-09")
        self.assertEqual(first.abstract, "Typed relations matter.")
        self.assertEqual(first.metadata_sha256, second.metadata_sha256)
        self.assertEqual(len(transport.calls), 1)
        self.assertIn("mailto:research@example.org", transport.calls[0][1]["User-Agent"])
        client.close()

    def test_expired_cache_refetches(self):
        def response(title: str) -> HttpResponse:
            return HttpResponse(200, {}, json.dumps({
                "message": {"DOI": "10.1234/ttl", "title": [title], "author": []}
            }).encode())

        transport = FakeTransport([response("First"), response("Second")])
        clock = FakeClock()
        limiter = ProviderRateLimiter(
            {"crossref": 0}, monotonic=clock.monotonic, sleep=clock.sleep
        )
        client = ResearchMetadataClient(
            self.cache, transport=transport, limiter=limiter,
            now=clock.now, sleep=clock.sleep, cache_ttl_seconds=5,
        )
        self.assertEqual(client.get_by_doi("10.1234/ttl").title, "First")
        clock.value += 6
        self.assertEqual(client.get_by_doi("10.1234/ttl").title, "Second")
        self.assertEqual(len(transport.calls), 2)
        client.close()

    def test_corrupted_cache_metadata_is_rejected_and_refetched(self):
        def response(title: str) -> HttpResponse:
            return HttpResponse(200, {}, json.dumps({
                "message": {"DOI": "10.1234/cache-integrity", "title": [title], "author": []}
            }).encode())

        first_transport = FakeTransport([response("Original")])
        limiter = ProviderRateLimiter({"crossref": 0})
        first_client = ResearchMetadataClient(
            self.cache, transport=first_transport, limiter=limiter
        )
        self.assertEqual(
            first_client.get_by_doi("10.1234/cache-integrity").title, "Original"
        )
        first_client.close()

        connection = sqlite3.connect(self.cache)
        row = connection.execute(
            "SELECT cache_key, payload_json FROM research_metadata_cache"
        ).fetchone()
        payload = json.loads(row[1])
        payload["title"] = "Tampered"
        connection.execute(
            "UPDATE research_metadata_cache SET payload_json=? WHERE cache_key=?",
            (json.dumps(payload), row[0]),
        )
        connection.commit()
        connection.close()

        second_transport = FakeTransport([response("Recovered")])
        second_client = ResearchMetadataClient(
            self.cache,
            transport=second_transport,
            limiter=ProviderRateLimiter({"crossref": 0}),
        )
        recovered = second_client.get_by_doi("10.1234/cache-integrity")
        self.assertEqual(recovered.title, "Recovered")
        self.assertEqual(len(second_transport.calls), 1)
        second_client.close()

    def test_arxiv_atom_parsing(self):
        atom = b"""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:arxiv="http://arxiv.org/schemas/atom">
          <entry>
            <id>https://arxiv.org/abs/2301.01234v2</id>
            <published>2023-01-03T12:00:00Z</published>
            <title>  Harmonic   Graphs </title>
            <summary> Coupled oscillators and phase structure. </summary>
            <author><name>Ada Lovelace</name></author>
            <arxiv:doi>10.1234/harmonic</arxiv:doi>
          </entry>
        </feed>"""
        transport = FakeTransport([HttpResponse(200, {}, atom)])
        client = ResearchMetadataClient(
            self.cache, transport=transport,
            limiter=ProviderRateLimiter({"arxiv": 0}),
        )
        record = client.get_by_arxiv("https://arxiv.org/abs/2301.01234v2")
        self.assertEqual(record.title, "Harmonic Graphs")
        self.assertEqual(record.authors, ("Ada Lovelace",))
        self.assertEqual(record.published, "2023-01-03")
        self.assertEqual(record.doi, "10.1234/harmonic")
        client.close()

    def test_provider_rate_limit_and_retry_after(self):
        clock = FakeClock()
        limiter = ProviderRateLimiter(
            {"crossref": 1.0}, monotonic=clock.monotonic, sleep=clock.sleep
        )
        limiter.wait("crossref")
        limiter.wait("crossref")
        self.assertEqual(clock.sleeps, [1.0])

        ok = HttpResponse(200, {}, json.dumps({
            "message": {"DOI": "10.1234/retry", "title": ["Retry"], "author": []}
        }).encode())
        transport = FakeTransport([
            HttpResponse(429, {"Retry-After": "2"}, b"slow down"),
            ok,
        ])
        client = ResearchMetadataClient(
            self.cache, transport=transport,
            limiter=ProviderRateLimiter({"crossref": 0}),
            sleep=clock.sleep,
        )
        self.assertEqual(client.get_by_doi("10.1234/retry").title, "Retry")
        self.assertEqual(clock.sleeps[-1], 2.0)
        self.assertEqual(len(transport.calls), 2)
        client.close()

    def test_invalid_identifiers_and_http_failure(self):
        client = ResearchMetadataClient(
            self.cache,
            transport=FakeTransport([HttpResponse(500, {}, b"error")]),
            limiter=ProviderRateLimiter({"crossref": 0, "arxiv": 0}),
            max_retries=0,
        )
        with self.assertRaises(ValueError):
            client.get_by_doi("not-a-doi")
        with self.assertRaises(ValueError):
            client.get_by_arxiv("../not-an-id")
        with self.assertRaises(MetadataFetchError):
            client.get_by_doi("10.1234/server-error")
        client.close()


if __name__ == "__main__":
    unittest.main()
