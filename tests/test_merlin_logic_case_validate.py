import unittest

from scripts.merlin_logic_case_validate import validate_case


def valid_case():
    return {
        "schema_version": 1,
        "case_id": "logic:case.test-example",
        "title": "A narrowly scoped historical reasoning case",
        "scope": {
            "tradition_or_school": "A named school in a specified period",
            "community_or_context": "A defined scholarly community and text corpus",
            "region": "A specified historical region",
            "languages": ["en"],
            "date_range": {"start": "1700", "end": "1750", "date_basis": "dated edition and correspondence"},
            "scope_note": "This record concerns a bounded set of texts and does not generalize to an entire culture."
        },
        "problem_context": {
            "problem_as_understood": "A specific question as represented in the cited historical material.",
            "why_it_mattered": "The problem shaped a documented debate.",
            "available_tools_and_knowledge": ["A named text", "A documented notation"]
        },
        "historical_context": {
            "institutions": ["A documented institution"],
            "social_and_material_context": "Context is described from the cited sources and scholarship.",
            "contributors_and_transmission": ["A documented translator or collaborator"],
            "uncertainties": ["The surviving record is incomplete."]
        },
        "sources": [{
            "source_id": "src:edition-1",
            "source_kind": "primary",
            "title": "A historical text",
            "creator": "A documented author",
            "edition_or_version": "Critical edition, 2001",
            "language": "en",
            "canonical_url": "https://example.org/source",
            "rights_status": "metadata_only",
            "license_uri": None,
            "locator": "Book II, section 4, pages 12-14",
            "provenance": "Catalog record and edition metadata"
        }],
        "argument_reconstruction": {
            "reconstruction_status": "candidate",
            "key_terms": [],
            "premises": ["Premise recorded from the cited passage."],
            "inference_steps": ["The author draws a conclusion from the stated premise."],
            "conclusion": "A scoped conclusion from the cited argument.",
            "caveats": ["This is a modern reconstruction, not a verbatim historical formalization."],
            "source_ids": ["src:edition-1"]
        },
        "formal_reconstruction": None,
        "translation_records": [{
            "source_expression": "Original term",
            "target_expression": "Working English gloss",
            "source_language_or_system": "Historical language",
            "target_language_or_system": "English",
            "mapping_kind": "approximate_translation",
            "equivalence_status": "partial",
            "preserved_features": ["One documented aspect"],
            "lost_or_changed_features": ["A connotation remains unresolved"],
            "assumptions": ["Gloss is provisional"],
            "review_status": "unreviewed"
        }],
        "claims": [{
            "claim_id": "claim:001",
            "statement": "The cited passage presents this particular inferential step.",
            "claim_type": "historical_report",
            "epistemic_status": "source_report",
            "source_ids": ["src:edition-1"],
            "limitations": ["One edition only"]
        }],
        "interpretations": [{
            "interpretation_id": "interp:001",
            "statement": "A possible interpretation of the author's argument.",
            "supporting_source_ids": ["src:edition-1"],
            "alternative_readings": ["An alternative reading remains possible."],
            "status": "working"
        }],
        "review": {
            "specialist_review_required": True,
            "review_status": "not_reviewed",
            "reviewer_expertise": [],
            "review_notes": []
        },
        "learning_assets": [],
        "record_status": "source_collected"
    }


class LogicCaseValidationTests(unittest.TestCase):
    def test_accepts_bounded_source_grounded_case(self):
        self.assertEqual(validate_case(valid_case()), [])

    def test_rejects_unscoped_case(self):
        case = valid_case()
        case["scope"]["date_range"] = {}
        case["scope"]["scope_note"] = "A culture thinks this way."
        errors = validate_case(case)
        self.assertTrue(any("scope.date_range.start" in e for e in errors))
        self.assertTrue(any("scope.scope_note" in e for e in errors))

    def test_rejects_claim_without_source_locator_or_provenance(self):
        case = valid_case()
        case["sources"][0]["locator"] = ""
        case["sources"][0]["provenance"] = ""
        errors = validate_case(case)
        self.assertTrue(any("sources[0].locator" in e for e in errors))
        self.assertTrue(any("sources[0].provenance" in e for e in errors))

    def test_rejects_dangling_claim_and_interpretation_sources(self):
        case = valid_case()
        case["claims"][0]["source_ids"] = ["src:missing"]
        case["interpretations"][0]["supporting_source_ids"] = ["src:missing"]
        errors = validate_case(case)
        self.assertTrue(any("claims[0] references unknown source_id" in e for e in errors))
        self.assertTrue(any("interpretations[0] references unknown source_id" in e for e in errors))

    def test_rejects_unlicensed_open_source_content(self):
        case = valid_case()
        case["sources"][0]["rights_status"] = "open_license_verified"
        case["sources"][0]["license_uri"] = None
        self.assertTrue(any("open-license content requires license_uri" in e for e in validate_case(case)))

    def test_rejects_lossy_translation_without_loss_description(self):
        case = valid_case()
        case["translation_records"][0]["lost_or_changed_features"] = []
        self.assertTrue(any("lost_or_changed_features" in e for e in validate_case(case)))

    def test_rejects_unqualified_specialist_review_status(self):
        case = valid_case()
        case["record_status"] = "specialist_reviewed"
        case["review"]["review_status"] = "not_reviewed"
        self.assertTrue(any("requires completed specialist review" in e for e in validate_case(case)))

    def test_rejects_duplicate_source_ids(self):
        case = valid_case()
        case["sources"].append(dict(case["sources"][0]))
        self.assertTrue(any("duplicate source_id" in e for e in validate_case(case)))


if __name__ == "__main__":
    unittest.main()
