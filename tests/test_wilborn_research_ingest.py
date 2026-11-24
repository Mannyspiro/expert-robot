import unittest
from wilborn_ops.research_ingest import ingest_public_text,ingest_batch,validate_url
from wilborn_ops.research_analysis import analyze_evidence

class ResearchIngestTests(unittest.TestCase):
    def test_public_evidence_dedup_and_analysis(self):
        content=b"Public synthetic test text; no client records."
        records=ingest_batch([
            ("https://www.nist.gov/publications",content),
            ("https://www.sba.gov/research",content),
            ("https://www.census.gov/data",b"Second public synthetic fixture"),
        ])
        self.assertEqual(len(records),2)
        report=analyze_evidence(records)
        self.assertEqual(report["document_count"],2)
        self.assertEqual(report["claims_verified"],0)
        self.assertEqual(report["data_class"],"public_research")

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
