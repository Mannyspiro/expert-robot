import tempfile
import unittest
from pathlib import Path

from merlin.academic_source_store import AcademicSourceStore, canonicalize_url


class AcademicSourceStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = AcademicSourceStore(Path(self.temp.name) / "sources.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def add(self, **overrides):
        args = dict(
            source_url="https://math.example.edu/~prof/?utm_source=google",
            institution="Example University",
            institution_domain="example.edu",
            source_type="personal_homepage",
            discovered_from="https://www.example.edu/math/faculty/",
            researcher_name="Ada Example",
            topics=["geometry", "combinatorics"],
        )
        args.update(overrides)
        return self.store.add(**args)

    def test_canonicalizes_tracking_and_fragment(self):
        self.assertEqual(
            canonicalize_url("HTTPS://EXAMPLE.EDU/a/?utm_campaign=x&b=2#bio"),
            "https://example.edu/a?b=2",
        )

    def test_accepts_external_personal_site_with_official_provenance(self):
        self.add(source_url="https://ada-math.net/")
        rows = self.store.list("example.edu")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].researcher_name, "Ada Example")

    def test_rejects_unprovenanced_external_discovery(self):
        with self.assertRaises(ValueError):
            self.add(discovered_from="https://random-blog.net/profile")

    def test_deduplicates_canonical_urls(self):
        self.add()
        self.add(title="Updated title", evidence_status="reviewed")
        rows = self.store.list()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].title, "Updated title")
        self.assertEqual(rows[0].evidence_status, "reviewed")

    def test_rejects_credentials_and_non_http_urls(self):
        with self.assertRaises(ValueError):
            canonicalize_url("https://user:pass@example.edu/")
        with self.assertRaises(ValueError):
            canonicalize_url("file:///etc/passwd")

    def test_rejects_unknown_source_types(self):
        with self.assertRaises(ValueError):
            self.add(source_type="private_contact_database")


if __name__ == "__main__":
    unittest.main()
