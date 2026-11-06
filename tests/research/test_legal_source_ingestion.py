import unittest

from merlin.legal_source_ingestion import (
    IngestionPolicy, arizona_register_index, build_capture_manifest,
    govinfo_bulk_index_urls, validate_source_url,
)


class LegalSourceIngestionTests(unittest.TestCase):
    def test_govinfo_catalog_has_federal_bulk_collections(self):
        rows = govinfo_bulk_index_urls(2026)
        collections = {row.collection for row in rows}
        self.assertTrue({"FR", "CFR", "USCODE", "STATUTE", "PLAW"} <= collections)
        for row in rows:
            row.validate()

    def test_arizona_register_candidate_uses_official_host(self):
        row = arizona_register_index(2026)
        row.validate()
        self.assertEqual(row.jurisdiction_id, "US-AZ")
        self.assertIn("apps.azsos.gov", row.url)

    def test_rejects_non_https_unknown_host_credentials_and_custom_port(self):
        for url in (
            "http://www.govinfo.gov/bulkdata/FR",
            "https://evil.example/bulkdata/FR",
            "https://user:pass@www.govinfo.gov/bulkdata/FR",
            "https://www.govinfo.gov:8443/bulkdata/FR",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_source_url(url)

    def test_capture_manifest_binds_exact_bytes_and_metadata(self):
        candidate = govinfo_bulk_index_urls(2026)[0]
        body = b"<root>public test fixture</root>"
        manifest = build_capture_manifest(
            candidate=candidate, final_url=candidate.url, body=body,
            content_type="application/xml; charset=utf-8",
            retrieved_at="2026-11-05T12:00:00+00:00",
        )
        self.assertEqual(manifest.byte_length, len(body))
        self.assertEqual(manifest.sha256, manifest.artifact_id.removeprefix("sha256:"))
        self.assertEqual(manifest.retention_decision, "metadata_only")

    def test_retain_requires_explicit_policy_and_permitted_use(self):
        candidate = govinfo_bulk_index_urls(2026)[0]
        body = b"licensed test"
        policy = IngestionPolicy(retain_content=True)
        manifest = build_capture_manifest(
            candidate=candidate, final_url=candidate.url, body=body,
            content_type="application/xml", permitted_use="licensed", policy=policy,
        )
        self.assertEqual(manifest.retention_decision, "retain")

    def test_oversized_capture_rejected(self):
        candidate = govinfo_bulk_index_urls(2026)[0]
        with self.assertRaises(ValueError):
            build_capture_manifest(
                candidate=candidate, final_url=candidate.url, body=b"12345",
                content_type="text/plain", policy=IngestionPolicy(max_capture_bytes=4),
            )

    def test_redirect_target_must_remain_allowlisted(self):
        candidate = govinfo_bulk_index_urls(2026)[0]
        with self.assertRaises(ValueError):
            build_capture_manifest(
                candidate=candidate, final_url="https://outside.example/file",
                body=b"x", content_type="text/plain",
            )


if __name__ == "__main__":
    unittest.main()
