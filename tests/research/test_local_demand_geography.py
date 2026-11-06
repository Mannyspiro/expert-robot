import unittest

from python.merlin.local_demand_geography import (
    major_market_tier, normalize_county_cbsa_membership,
    normalize_place, place_population_tier,
)


class GeographyNormalizationTests(unittest.TestCase):
    def test_normalizes_place_and_preserves_vintages(self):
        result = normalize_place(
            {"GEOID":"0644000","NAME":"Example city","STATE":"06","PLACE":"44000"},
            vintage=2026, population=123456, population_vintage=2025,
        )
        self.assertEqual(result["jurisdiction_id"], "census-place:0644000")
        self.assertEqual(result["geography_vintage"], 2026)
        self.assertEqual(result["population_vintage"], 2025)

    def test_population_requires_its_own_vintage(self):
        with self.assertRaisesRegex(ValueError, "population_vintage"):
            normalize_place(
                {"GEOID":"0644000","NAME":"Example city","STATE":"06","PLACE":"44000"},
                vintage=2026, population=123,
            )

    def test_missing_place_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing required"):
            normalize_place({"NAME":"Missing GEOID"}, vintage=2026)

    def test_county_cbsa_crosswalk_is_not_legal_municipal_boundary(self):
        result = normalize_county_cbsa_membership({
            "FIPS State Code":"6", "FIPS County Code":"37",
            "CBSA Code":"31080", "CBSA Title":"Los Angeles-Long Beach-Anaheim, CA",
            "Metropolitan/Micropolitan Statistical Area":"Metropolitan Statistical Area",
        }, vintage=2023)
        self.assertEqual(result["county_geoid"], "06037")
        self.assertFalse(result["is_legal_municipal_boundary"])

    def test_invalid_geography_codes_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be numeric"):
            normalize_county_cbsa_membership({
                "STATEFP":"06", "COUNTYFP":"037", "CBSA":"abc",
                "NAME":"Example", "LSAD":"Metro",
            }, vintage=2023)

    def test_market_tiers_prioritize_without_excluding(self):
        self.assertEqual(major_market_tier(1), "top_50_metro_areas")
        self.assertEqual(major_market_tier(75), "top_100_metro_areas")
        self.assertEqual(major_market_tier(125), "other_metro_or_micropolitan_area")
        self.assertEqual(major_market_tier(None), "unranked")

    def test_place_population_tier_handles_unknown(self):
        self.assertEqual(place_population_tier(None), "population_unknown")
        self.assertEqual(place_population_tier(50000), "above_configured_place_threshold")
        self.assertEqual(place_population_tier(49999), "below_configured_place_threshold")

    def test_invalid_population_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            place_population_tier(-1)


if __name__ == "__main__":
    unittest.main()
