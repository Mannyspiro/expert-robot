import unittest
from dataclasses import replace
from wilborn_ops.research_ingest import ingest_public_text
from wilborn_ops.research_tabular import analyze_numeric_csv

class PublicTabularTests(unittest.TestCase):
    def evidence(self,raw):
        return ingest_public_text("https://www.census.gov/data",raw)

    def test_numeric_summary_with_missingness(self):
        e=self.evidence(b"period,value\nA,2\nB,4\nC,\nD,6\n")
        report=analyze_numeric_csv(e,"value")
        self.assertEqual(report["rows"],4)
        self.assertEqual(report["missing_count"],1)
        self.assertEqual(report["mean"],4)
        self.assertEqual(report["median"],4)
        self.assertEqual(report["claims_verified"],0)
        self.assertEqual(report["data_class"],"unverified_research_input")
        self.assertIs(report["source_authenticity_verified"],False)

    def test_reject_malformed_or_unbounded_data(self):
        for raw in (b"x\nNaN\n",b"x\nInfinity\n",b"x\nnot-a-number\n",
                    b"x\n1,extra\n",b"x,x\n1,2\n",
                    b"x\n"+b"1\n"*1001):
            with self.assertRaises(ValueError):
                analyze_numeric_csv(self.evidence(raw),"x")

    def test_short_rows_and_identity_mismatch_rejected(self):
        for body in (b"period,value\nA\n",b"value,period\n2\n",b"value,\n2,A\n"):
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    analyze_numeric_csv(self.evidence(body),"value")
        item=self.evidence(b"value\n2\n")
        with self.assertRaises(ValueError):
            analyze_numeric_csv(replace(item,text="value\n9\n"),"value")
