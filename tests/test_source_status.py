import unittest

from merlin.source_status import SourceObservation, resolve_opportunity_status


class SourceStatusTests(unittest.TestCase):
    def obs(self, role, status, day="2026-11-05", url="https://example.gov/bids"):
        return SourceObservation(role, status, url, "Source", day)

    def test_secondary_open_never_proves_open(self):
        result = resolve_opportunity_status((self.obs("secondary", "open"),))
        self.assertEqual(result.status, "unverified")
        self.assertFalse(result.verified_open)

    def test_official_open_confirms_open(self):
        result = resolve_opportunity_status((self.obs("issuing_authority", "open"),))
        self.assertEqual(result.status, "verified_open")
        self.assertTrue(result.verified_open)

    def test_official_not_listed_and_secondary_open_is_conflict(self):
        result = resolve_opportunity_status((
            self.obs("issuing_authority", "not_listed"),
            self.obs("secondary", "open", url="https://aggregator.example/rfp"),
        ))
        self.assertEqual(result.status, "conflicting")
        self.assertFalse(result.verified_open)

    def test_latest_authority_observation_wins(self):
        result = resolve_opportunity_status((
            self.obs("issuing_authority", "open", "2026-11-04"),
            self.obs("issuing_authority", "closed", "2026-11-05"),
        ))
        self.assertEqual(result.status, "closed")

    def test_bad_role_status_or_url_rejected(self):
        with self.assertRaises(ValueError):
            self.obs("blog", "open")
        with self.assertRaises(ValueError):
            self.obs("secondary", "maybe")
        with self.assertRaises(ValueError):
            self.obs("secondary", "open", url="http://example.com")


if __name__ == "__main__":
    unittest.main()
