import unittest

from merlin.ideonomy import enumerate_lesson_designs, parrondo_design_shortlist


class IdeonomyEnumerationTests(unittest.TestCase):
    def test_enumerates_full_bounded_cartesian_space(self):
        report = enumerate_lesson_designs()
        self.assertEqual(report.cartesian_size, 1728)
        self.assertEqual(report.evaluated, report.cartesian_size)
        self.assertGreater(report.rejected, 0)
        self.assertEqual(len(report.retained), 24)

    def test_incoherent_combinations_are_explained(self):
        report = enumerate_lesson_designs()
        self.assertIn("reflection-alone-cannot-establish-mastery", report.rejection_counts)
        self.assertIn("formal-proof-evidence-outside-mathematician-path", report.rejection_counts)
        self.assertIn("executable-model-without-computational-activity", report.rejection_counts)

    def test_retained_designs_are_coherent(self):
        report = enumerate_lesson_designs(limit=1728)
        for design in report.retained:
            self.assertNotEqual(design.evidence, "reflection_only")
            if design.evidence == "formal_proof":
                self.assertEqual(design.path, "mathematician")
            if design.sequence == "problem_code_explain":
                self.assertEqual(design.representation, "executable_model")
            if design.activity == "implement_simulation":
                self.assertNotEqual(design.path, "mathematician")

    def test_ranking_is_deterministic_and_explained(self):
        first = enumerate_lesson_designs(limit=12)
        second = enumerate_lesson_designs(limit=12)
        self.assertEqual(first.retained, second.retained)
        self.assertTrue(all(item.rationale for item in first.retained))
        self.assertEqual(tuple(sorted(first.retained, key=lambda item: -item.score)), first.retained)

    def test_parrondo_shortlist_is_bounded_and_ranked(self):
        report = parrondo_design_shortlist(limit=8)
        self.assertEqual(report.evaluated, 1728)
        self.assertEqual(len(report.retained), 8)
        self.assertGreaterEqual(report.retained[0].score, report.retained[-1].score)

    def test_limit_must_be_positive(self):
        with self.assertRaises(ValueError):
            enumerate_lesson_designs(limit=0)


if __name__ == "__main__":
    unittest.main()
