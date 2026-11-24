import unittest
from dataclasses import replace
from wilborn_ops.research_ingest import ingest_public_text
from wilborn_ops.research_metadata import DatasetMetadata,compare_with_metadata

class MetadataComparisonTests(unittest.TestCase):
    def setUp(self):
        self.left=ingest_public_text("https://www.census.gov/data",b"value\n2\n4\n")
        self.right=ingest_public_text("https://www.sba.gov/data",b"value\n4\n8\n")
        self.a=DatasetMetadata(self.left.sha256,"Arizona","2025","small businesses",
                               "business count","count")
        self.b=DatasetMetadata(self.right.sha256,"Arizona","2025","small businesses",
                               "business count","count")

    def test_matching_metadata_allows_descriptive_comparison(self):
        result=compare_with_metadata(self.left,self.right,self.a,self.b,"value")
        self.assertTrue(result["comparable"])
        self.assertEqual(result["difference_of_means"],3)
        self.assertEqual(result["claims_verified"],0)

    def test_mismatches_block_differences(self):
        for field,value in (("geography","Nevada"),("period","2024"),
                            ("population","all residents"),("measure","revenue"),
                            ("unit","USD")):
            result=compare_with_metadata(self.left,self.right,self.a,
                                         replace(self.b,**{field:value}),"value")
            self.assertFalse(result["comparable"])
            self.assertIn(field,result["mismatched_dimensions"])
            self.assertIsNone(result["difference_of_means"])

    def test_forged_metadata_hash_rejected(self):
        with self.assertRaises(PermissionError):
            compare_with_metadata(self.left,self.right,self.a,
                                  replace(self.b,source_sha256="0"*64),"value")

    def test_mismatch_cannot_bypass_evidence_validation(self):
        with self.assertRaises(ValueError):
            compare_with_metadata(replace(self.left,text="value\n9\n"),self.right,
                                  self.a,replace(self.b,unit="USD"),"value")
