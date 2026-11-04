import unittest

from merlin.academic_spider import (
    DEFAULT_INSTITUTIONS,
    Institution,
    build_queries,
    build_registry_queries,
)


class AcademicSpiderTests(unittest.TestCase):
    def test_registry_contains_relevant_institutions_once(self):
        rows = build_registry_queries()
        self.assertEqual(
            {row.domain for row in rows},
            {"stanford.edu", "mit.edu", "princeton.edu", "harvard.edu", "ethz.ch", "zib.de"},
        )
        self.assertEqual(len({row.domain for row in rows}), len(DEFAULT_INSTITUTIONS))
        self.assertTrue(all(f"site:{row.domain}" in row.query for row in rows))

    def test_query_urls_are_google_search_urls(self):
        rows = build_queries(Institution("Test University", "example.edu"), ["spectral geometry"])
        self.assertTrue(all(row.search_url.startswith("https://www.google.com/search?q=") for row in rows))
        self.assertTrue(any(row.category == "topic:spectral geometry" for row in rows))

    def test_rejects_invalid_domain(self):
        with self.assertRaises(ValueError):
            build_queries(Institution("Bad", "example.edu/path"))

    def test_rejects_empty_topics(self):
        with self.assertRaises(ValueError):
            build_queries(Institution("Test", "example.edu"), [])

    def test_accepts_topics_containing_r_and_n(self):
        rows = build_queries(Institution("Test", "example.edu"), ["combinatorics", "information theory"])
        self.assertTrue(any("combinatorics" in row.query for row in rows))

    def test_rejects_multiline_topic(self):
        with self.assertRaises(ValueError):
            build_queries(Institution("Test", "example.edu"), ["geometry\nsite:other.edu"])


if __name__ == "__main__":
    unittest.main()
