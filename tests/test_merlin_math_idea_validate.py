import unittest

from scripts.merlin_math_idea_validate import validate_catalog


def idea(ident, relations=None):
    return {
        "id": ident, "title": ident, "kind": "concept", "claim": "A scoped claim.",
        "definitions": [], "assumptions": [], "status": "candidate",
        "provenance": ["test"], "relations": relations or [],
        "objections": [], "next_steps": [],
    }


class MathIdeaCatalogValidationTests(unittest.TestCase):
    def test_accepts_valid_forward_and_backward_links(self):
        data = {
            "schema_version": 1,
            "ideas": [
                idea("A", [{"type": "depends_on", "target": "B"}]),
                idea("B"),
            ],
        }
        self.assertEqual(validate_catalog(data), [])

    def test_rejects_duplicate_ids(self):
        data = {"schema_version": 1, "ideas": [idea("A"), idea("A")]}
        self.assertTrue(any("duplicate idea id" in e for e in validate_catalog(data)))

    def test_rejects_dangling_relation(self):
        data = {"schema_version": 1, "ideas": [idea("A", [{"type": "maps_to", "target": "MISSING"}])]}
        self.assertTrue(any("targets missing id" in e for e in validate_catalog(data)))

    def test_rejects_unknown_status_and_relation(self):
        item = idea("A", [{"type": "magic", "target": "A"}])
        item["status"] = "proven"
        errors = validate_catalog({"schema_version": 1, "ideas": [item]})
        self.assertTrue(any("status is not recognized" in e for e in errors))
        self.assertTrue(any("unknown relation type" in e for e in errors))

    def test_rejects_missing_fields(self):
        data = {"schema_version": 1, "ideas": [{"id": "A"}]}
        self.assertTrue(any("missing fields" in e for e in validate_catalog(data)))



if __name__ == "__main__":
    unittest.main()
