import unittest

from merlin.legal_xml_parsers import parse_govinfo_xml, record_dict


class GovInfoXmlParserTests(unittest.TestCase):
    def test_federal_register_document_fields(self):
        xml = b"""<ROOT><FEDREG><TITLE>Rules and Regulations</TITLE><DATE>2026-11-01</DATE><DOCUMENTNUMBER>2026-12345</DOCUMENTNUMBER><AGENCY><AGENCYNAME>Example Agency</AGENCYNAME></AGENCY><EFFECTIVEDATE>2026-12-01</EFFECTIVEDATE><SUMMARY>Example summary.</SUMMARY></FEDREG></ROOT>"""
        row, = parse_govinfo_xml(xml, collection="FR", package_id="FR-2026-11-01")
        self.assertEqual(row.record_type, "federal_register_document")
        self.assertEqual(row.document_number, "2026-12345")
        self.assertEqual(row.effective_date, "2026-12-01")
        self.assertIn("Example Agency", row.agency)

    def test_uslm_sections_are_separate_records(self):
        xml = b"""<law><meta><docTitle>Example Act</docTitle></meta><main><section id="sec-1"><num>101</num><heading>Definitions</heading><content>Text one.</content></section><section id="sec-2"><num>102</num><heading>Scope</heading><content>Text two.</content></section></main></law>"""
        rows = parse_govinfo_xml(xml, collection="USCODE", package_id="USCODE-test")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].section_id, "sec-1")
        self.assertEqual(rows[1].section_number, "102")
        self.assertEqual(rows[0].title, "Example Act")

    def test_rejects_empty_oversized_malformed_and_dtd_payloads(self):
        for body in (b"", b"<broken>", b"<!DOCTYPE x [<!ENTITY y 'z'>]><x>&y;</x>"):
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_govinfo_xml(body, collection="FR", package_id="fixture")
        with self.assertRaises(ValueError):
            parse_govinfo_xml(b"<x>12345</x>", collection="FR", package_id="fixture", max_bytes=4)

    def test_digest_binds_exact_source_bytes_and_serialization(self):
        body = b"<root><title>One</title></root>"
        record, = parse_govinfo_xml(body, collection="FR", package_id="fixture")
        self.assertEqual(len(record.source_sha256), 64)
        self.assertEqual(record_dict(record)["package_id"], "fixture")
        changed, = parse_govinfo_xml(body.replace(b"One", b"Two"), collection="FR", package_id="fixture")
        self.assertNotEqual(record.source_sha256, changed.source_sha256)

    def test_unknown_metadata_is_reported_not_invented(self):
        record, = parse_govinfo_xml(b"<root><body>Text</body></root>", collection="FR", package_id="fixture")
        self.assertIsNone(record.title)
        self.assertIn("title_not_found", record.extraction_warnings)
        self.assertIn("publication_date_not_found", record.extraction_warnings)


if __name__ == "__main__":
    unittest.main()
