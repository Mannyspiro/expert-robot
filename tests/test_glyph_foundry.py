import unittest
from merlin.glyph_foundry import EvidenceState, GlyphFoundry, PromotionError, TypeMismatch, TypeRef, build_default_registry

class GlyphFoundryTests(unittest.TestCase):
    def setUp(self):
        self.registry=build_default_registry()
        self.foundry=GlyphFoundry(self.registry)
    def test_identity_laws_and_elimination(self):
        f=self.registry.primitive_expr("NEGATE_INT")
        i=self.registry.identity(TypeRef("Int"))
        self.assertEqual(f.evaluate(7,self.registry),-7)
        self.assertEqual(self.registry.compose(f,i),f)
        self.assertEqual(self.registry.compose(i,f),f)
    def test_type_mismatch_rejected(self):
        with self.assertRaises(TypeMismatch):
            self.registry.compose(self.registry.primitive_expr("NEGATE_INT"),self.registry.primitive_expr("INT_TO_FLOAT"))
    def test_composition_order(self):
        f=self.registry.compose(self.registry.primitive_expr("ABS_INT"),self.registry.primitive_expr("NEGATE_INT"))
        self.assertEqual([f.evaluate(x,self.registry) for x in (3,-3)],[3,3])
    def test_pair_and_projection(self):
        f=self.registry.primitive_expr("NEGATE_INT")
        i=self.registry.primitive_expr("IDENTITY_INT")
        p=self.registry.pair(f,i)
        self.assertEqual(self.registry.project(p,0).evaluate(4,self.registry),-4)
        self.assertEqual(self.registry.project(p,1).evaluate(4,self.registry),4)
    def test_equal_returns_bool(self):
        f=self.registry.primitive_expr("NEGATE_INT")
        self.assertTrue(self.registry.equal(f,f).evaluate(9,self.registry))
    def test_constraint_is_typed_and_executed(self):
        f=self.registry.constrain(self.registry.primitive_expr("ABS_INT"),"NONNEGATIVE_NAT")
        self.assertEqual(f.evaluate(-8,self.registry),8)
    def test_candidate_enumeration_is_bounded_and_deduplicated(self):
        xs=list(self.foundry.enumerate_compositions(3,5,30))
        fps=[x.fingerprint() for x in xs]
        self.assertLessEqual(len(xs),30)
        self.assertEqual(len(fps),len(set(fps)))
    def test_promotion_requires_all_evidence(self):
        c=self.foundry.propose(self.registry.primitive_expr("NEGATE_INT"))
        with self.assertRaises(PromotionError): self.foundry.promote(c)
        self.foundry.record_tests(c,["test-run"])
        self.foundry.record_proof(c,"lean-receipt")
        self.foundry.record_independent_review(c,"independent-review")
        with self.assertRaises(PromotionError): self.foundry.promote(c)
        self.foundry.record_value(c,1.2,1.0,"benchmark-run",min_relative_gain=.1)
        self.foundry.promote(c)
        self.assertEqual(c.state,EvidenceState.PROMOTED)
    def test_bounded_search_slices_resume_without_repeating(self):
        first = list(self.foundry.enumerate_compositions(4, 10, 5))
        second = list(self.foundry.enumerate_compositions(4, 10, 100))
        self.assertTrue(first)
        self.assertTrue(second)
        self.assertFalse({x.fingerprint() for x in first} & {x.fingerprint() for x in second})
    def test_nonfinite_benchmark_is_rejected(self):
        c = self.foundry.propose(self.registry.primitive_expr("NEGATE_INT"))
        with self.assertRaises(PromotionError):
            self.foundry.record_value(c, float("nan"), 1.0, "bad-benchmark")
    def test_no_improvement_cannot_be_promoted(self):
        c=self.foundry.propose(self.registry.primitive_expr("NEGATE_INT"))
        self.foundry.record_tests(c,["test"])
        self.foundry.record_proof(c,"proof")
        self.foundry.record_independent_review(c,"review")
        self.foundry.record_value(c,1.0,1.0,"benchmark")
        with self.assertRaises(PromotionError): self.foundry.promote(c)

if __name__=="__main__": unittest.main()
