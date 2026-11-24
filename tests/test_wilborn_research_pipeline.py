import unittest
from dataclasses import replace
from wilborn_ops.research_retrieval import FetchReceipt
from wilborn_ops.research_pipeline import research_report

class ResearchPipelineTests(unittest.TestCase):
    def test_composed_fixture_pipeline(self):
        url="https://www.census.gov/data"
        receipt=FetchReceipt(url,url,200,"text/csv",b"value\n2\n4\n",0,True,True,True)
        result=research_report(receipt,numeric_column="value")
        self.assertEqual(result["numeric_analysis"]["mean"],3)
        self.assertEqual(result["claims_verified"],0)
        self.assertTrue(result["untrusted_content"])
        self.assertEqual(result["data_class"],"unverified_research_input")
        self.assertIs(result["source_authenticity_verified"],False)
        self.assertIs(result["numeric_analysis"]["source_authenticity_verified"],False)
        self.assertEqual(result["source_url"],url)
        with self.assertRaises(PermissionError):
            research_report(replace(receipt,tls_verified=False))
        page=research_report(replace(receipt,content_type="text/html",body=b"<p>Public fixture</p>"))
        self.assertEqual(page["extracted_text"],"Public fixture")
        with self.assertRaises(ValueError):
            research_report(replace(receipt,content_type="text/html"),numeric_column="value")
