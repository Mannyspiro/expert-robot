import tempfile
import unittest

from merlin.public_market_research import KalshiQuote, PublicResearchStore, evaluate_binary_market


class PublicResearchStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = PublicResearchStore(self.temp.name)
        self.snapshot = self.store.add_snapshot(
            source_id="SRC-BLS", source_url="https://www.bls.gov/news.release/example.htm",
            content=b"release-v1", retrieved_at="2026-01-10T09:00:00-05:00",
            published_at="2026-01-10T08:30:00-05:00", terms_reviewed=True,
        )

    def add_obs(self, observation_id, value, available_at):
        return self.store.add_observation(
            observation_id=observation_id, source_id="SRC-BLS",
            snapshot_sha256=self.snapshot.sha256, entity_id="US",
            metric="unemployment_rate", period_start="2025-12-01T00:00:00Z",
            period_end="2025-12-31T23:59:59Z", available_at=available_at,
            value=value, unit="percent", vintage=observation_id,
        )

    def test_snapshot_hash_is_verified(self):
        self.assertTrue(self.store.verify_snapshot(self.snapshot.sha256))
        self.assertFalse(self.store.verify_snapshot("0" * 64))

    def test_requires_terms_review_and_https(self):
        with self.assertRaises(ValueError):
            self.store.add_snapshot(
                source_id="x", source_url="https://example.gov/data", content=b"x",
                retrieved_at="2026-01-01T00:00:00Z", published_at="2026-01-01T00:00:00Z",
                terms_reviewed=False,
            )
        with self.assertRaises(ValueError):
            self.store.add_snapshot(
                source_id="x", source_url="http://example.gov/data", content=b"x",
                retrieved_at="2026-01-01T00:00:00Z", published_at="2026-01-01T00:00:00Z",
                terms_reviewed=True,
            )

    def test_observation_must_bind_to_existing_snapshot_and_source(self):
        with self.assertRaises(ValueError):
            self.store.add_observation(
                observation_id="bad", source_id="SRC-SEC", snapshot_sha256=self.snapshot.sha256,
                entity_id="X", metric="revenue", period_start="2025-01-01T00:00:00Z",
                period_end="2025-12-31T00:00:00Z", available_at="2026-01-01T00:00:00Z",
                value=1, unit="USD",
            )

    def test_point_in_time_query_excludes_future_release_and_selects_vintage(self):
        self.add_obs("initial", "4.2", "2026-01-10T13:30:00Z")
        self.add_obs("revision", "4.1", "2026-02-10T13:30:00Z")
        early = self.store.query_as_of(entity_id="US", metric="unemployment_rate",
                                       cutoff="2026-01-20T00:00:00Z")
        later = self.store.query_as_of(entity_id="US", metric="unemployment_rate",
                                       cutoff="2026-02-20T00:00:00Z")
        self.assertEqual([item.value for item in early], ["4.2"])
        self.assertEqual([item.value for item in later], ["4.1"])

    def test_duplicate_observation_id_is_rejected(self):
        self.add_obs("same", "4.2", "2026-01-10T13:30:00Z")
        with self.assertRaises(Exception):
            self.add_obs("same", "4.3", "2026-01-11T13:30:00Z")


class KalshiResearchTests(unittest.TestCase):
    def quote(self, yes=40, no=62):
        return KalshiQuote(
            ticker="EXAMPLE", title="Example event", yes_ask_cents=yes, no_ask_cents=no,
            observed_at="2026-11-06T10:00:00Z", rules_url="https://kalshi.com/markets/example",
        )

    def test_edge_uses_ask_and_fees(self):
        result = evaluate_binary_market(
            quote=self.quote(), estimated_yes_probability=0.50,
            fee_per_contract_dollars=0.01, minimum_edge=0.02,
        )
        self.assertAlmostEqual(result["yes_net_edge_per_contract"], 0.09)
        self.assertEqual(result["research_candidates"][0]["side"], "YES")
        self.assertFalse(result["is_trade_instruction"])

    def test_no_candidate_when_edge_below_threshold(self):
        result = evaluate_binary_market(
            quote=self.quote(yes=49, no=50), estimated_yes_probability=0.50,
            minimum_edge=0.02,
        )
        self.assertEqual(result["research_candidates"], [])

    def test_rejects_bad_probability_and_quote(self):
        with self.assertRaises(ValueError):
            evaluate_binary_market(quote=self.quote(), estimated_yes_probability=1.2)
        with self.assertRaises(ValueError):
            evaluate_binary_market(quote=self.quote(yes=101), estimated_yes_probability=0.5)


if __name__ == "__main__":
    unittest.main()
