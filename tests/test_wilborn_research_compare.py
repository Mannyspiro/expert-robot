import unittest
from wilborn_ops.research_ingest import ingest_public_text
from wilborn_ops.research_compare import compare_public_series

class PublicComparisonTests(unittest.TestCase):
    def setUp(self):
        self.a=ingest_public_text("https://www.census.gov/data",b"value\n2\n4\n")
        self.b=ingest_public_text("https://www.sba.gov/data",b"value\n4\n8\n")

    def test_requires_explicit_comparability(self):
        result=compare_public_series(self.a,self.b,"value",unit="cases")
        self.assertIsNone(result["difference_of_means"])
        self.assertEqual(result["claims_verified"],0)
        measured=compare_public_series(self.a,self.b,"value",unit="cases",comparable=True)
        self.assertEqual(measured["difference_of_means"],3)
        self.assertEqual(measured["relative_difference_percent"],100)
        self.assertEqual(measured["interpretation"],"descriptive difference only; no causal inference")

    def test_rejects_same_source_and_missing_units(self):
        with self.assertRaises(ValueError):
            compare_public_series(self.a,self.a,"value",unit="cases",comparable=True)
        with self.assertRaises(ValueError):
            compare_public_series(self.a,self.b,"value",unit="",comparable=True)

    def test_missing_data_is_reported(self):
        a=ingest_public_text("https://www.census.gov/data",b"value\n\n")
        result=compare_public_series(a,self.b,"value",unit="cases",comparable=True)
        self.assertIsNone(result["difference_of_means"])
