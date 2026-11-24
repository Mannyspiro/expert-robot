"""Finite paradox and mathematical representation preflight tests."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from merlin.paradox_preflight import ScopedClaim,assess_claims,check_simplex,check_continuum_boundary,check_glyph_translation

class ParadoxTests(unittest.TestCase):
    def claim(self,truth,**scope):
        return ScopedClaim("signal","active",truth,scope.get("time","t0"),scope.get("domain","local"),scope.get("units","count"),scope.get("frame","classical"))

    def test_true_contradiction_shared_scope(self):
        v=assess_claims(self.claim(True),self.claim(False))
        self.assertEqual(v["status"],"contradiction_under_shared_classical_scope")
        self.assertFalse(v["logical_resolution_proven"])

    def test_scope_mismatch_not_classical_contradiction(self):
        for spec in ({"time":"t1"},{"domain":"remote"},{"units":"meters"},{"frame":"other"}):
            v=assess_claims(self.claim(True),self.claim(False,**spec))
            self.assertEqual(v["status"],"scope_mismatch_requires_mapping")
            self.assertEqual(v["different_axes"],list(spec))
            self.assertFalse(v["factual_premises_verified"])

    def test_uninterpreted_nonclassical_frame_needs_semantics(self):
        r=assess_claims(self.claim(True,frame="paraconsistent"),
                        self.claim(False,frame="paraconsistent"))
        self.assertEqual(r["status"],"nonclassical_semantics_not_defined")
        self.assertFalse(r["logical_resolution_proven"])

    def test_same_truth_not_a_paradox(self):
        r=assess_claims(self.claim(True),self.claim(True))
        self.assertEqual(r["status"],"no_direct_contradiction_found")
        self.assertFalse(r["logical_resolution_proven"])

    def test_invalid_claim_is_not_silently_coerced(self):
        with self.assertRaises(ValueError):self.claim(1)
        with self.assertRaises(ValueError):self.claim(True,units="")
        with self.assertRaises(TypeError):assess_claims("unsupported",self.claim(False))

    def test_simplex_coordinates_have_bounded_sum(self):
        self.assertTrue(check_simplex([0.2,0.3,0.5])["valid"])
        self.assertFalse(check_simplex([0.2,0.3,0.4])["valid"])
        self.assertFalse(check_simplex([-0.1,1.1])["valid"])
        self.assertFalse(check_simplex([0.2,0.3,0.5])["affine_independence_proven"])

    def test_simplex_invalid_number_fails_closed(self):
        with self.assertRaises(ValueError):check_simplex([0.5,float("nan")])
        with self.assertRaises(ValueError):check_simplex([True,0])
        with self.assertRaises(ValueError):check_simplex([0.5,0.5],tolerance=-1)

    def test_continuum_boundary_checks_are_local(self):
        bad=check_continuum_boundary([("x=0",1.0),("x=0",2.0)])
        self.assertEqual(bad["status"],"incompatible_shared_boundary")
        good=check_continuum_boundary([("x=0",1.0),("x=1",2.0)])
        self.assertEqual(good["status"],"finite_constraints_consistent")
        self.assertFalse(good["continuous_extension_proven"])

    def test_glyph_translation_is_only_a_preflight(self):
        r=check_glyph_translation(["plus","x"],{"plus":"add","x":"variable"})
        self.assertEqual(r["status"],"typed_tokens_present")
        self.assertFalse(r["semantics_preservation_proven"])
        missing=check_glyph_translation(["plus","y"],{"plus":"add"})
        self.assertEqual(missing["undefined_tokens"],["y"])
        self.assertFalse(missing["novel_mathematical_system_proven"])

if __name__=="__main__":
    unittest.main()
