import unittest
from dataclasses import replace
from wilborn_ops.research_ingest import ingest_public_text,ingest_batch,validate_url,validate_evidence
from wilborn_ops.research_analysis import analyze_evidence

class ResearchIngestTests(unittest.TestCase):
    def test_public_evidence_dedup_and_analysis(self):
        content=b"Public synthetic test text; no client records."
        records=ingest_batch([
            ("https://www.nist.gov/publications",content),
            ("https://www.nist.gov/publications",content),
            ("https://www.census.gov/data",b"Second public synthetic fixture"),
        ])
        self.assertEqual(len(records),2)
        report=analyze_evidence(records)
        self.assertEqual(report["document_count"],2)
        self.assertEqual(report["claims_verified"],0)
        self.assertEqual(report["data_class"],"unverified_research_input")
        self.assertIs(report["source_authenticity_verified"],False)

    def test_block_unapproved_network_targets(self):
        for url in ("http://www.nist.gov/data",
                    "https://localhost/secrets",
                    "https://127.0.0.1/admin",
                    "https://www.nist.gov.evil.example/a",
                    "https://user:pass@www.nist.gov/a",
                    "file:///etc/passwd",
                    "https://www.nist.gov:8443/a"):
            with self.assertRaises((PermissionError,ValueError)):
                validate_url(url)

    def test_limits_and_invalid_content(self):
        with self.assertRaises(ValueError):
            ingest_public_text("https://www.nist.gov/a",b"")
        with self.assertRaises(ValueError):
            ingest_public_text("https://www.nist.gov/a",b"x"*256001)
        with self.assertRaises(ValueError):
            ingest_public_text("https://www.nist.gov/a",b"\xff")
        with self.assertRaises(ValueError):
            ingest_batch([("https://www.nist.gov/a",b"a")]*51)

    def test_conflicting_urls_rejected(self):
        with self.assertRaises(ValueError):
            ingest_batch([("https://www.sba.gov/",b"fixture"),
                          ("https://www.nist.gov/",b"fixture")])

    def test_consistency_does_not_establish_authenticity(self):
        item=ingest_public_text("https://www.sba.gov/",b"synthetic fixture")
        self.assertIs(validate_evidence(item).source_authenticity_verified,False)
        for change in ({"text":"modified"},{"bytes":0},{"sha256":"0"*64},
                       {"data_class":"public_research"},{"verification":"verified"},
                       {"source_authenticity_verified":True},{"url":"https://localhost/"}):
            with self.subTest(change=change):
                with self.assertRaises((ValueError,PermissionError)):
                    analyze_evidence([replace(item,**change)])
