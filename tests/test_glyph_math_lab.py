import unittest
from merlin.glyph_math_lab import (
    canonical_glyph_bytes, glyph_grammar, glyph_grammar_digest, validate_expression,
)

class GlyphMathLabTests(unittest.TestCase):
    def test_grammar_is_deterministic_and_addressable(self):
        self.assertEqual(canonical_glyph_bytes(), canonical_glyph_bytes())
        self.assertEqual(len(glyph_grammar_digest()), 64)
        self.assertEqual(glyph_grammar()["schema"], "merlin-glyph-algebra/1")

    def test_iteration_requires_nonnegative_integer(self):
        good = {"op": "iterate", "args": ["f", 4], "domain": "X", "codomain": "X"}
        bad = dict(good, args=["f", -1])
        self.assertEqual(validate_expression(good), [])
        self.assertIn("iteration count must be a non-negative integer", validate_expression(bad))

    def test_invariant_requires_proof_obligation(self):
        expr = {"op": "invariant", "args": ["energy"], "domain": "State", "codomain": "Scalar"}
        self.assertIn("invariant requires a proof obligation", validate_expression(expr))

    def test_duality_requires_definition(self):
        expr = {"op": "dual", "args": ["V"], "domain": "Space", "codomain": "Dual"}
        self.assertIn("dual operation requires an explicit duality definition", validate_expression(expr))

if __name__ == "__main__":
    unittest.main()
