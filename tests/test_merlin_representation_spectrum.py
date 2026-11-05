import unittest
from fractions import Fraction as F
from merlin.representation_graph import matrix
from merlin.representation_spectrum import ScalarFieldMetadata, generalized_eigenspace

class RepresentationSpectrumTests(unittest.TestCase):
    def setUp(self):
        self.q = ScalarFieldMetadata(kind="Q", field_id="Q")

    def test_generalized_eigenspace_filtration_for_jordan_block(self):
        a = matrix([[2,1,0],[0,2,0],[0,0,3]])
        first = generalized_eigenspace(a,F(2),1,self.q)
        second = generalized_eigenspace(a,F(2),2,self.q)
        self.assertEqual(first.dimension,1)
        self.assertEqual(second.dimension,2)
        self.assertEqual(second.basis,((F(1),F(0),F(0)),(F(0),F(1),F(0))))

    def test_other_eigenvalue(self):
        a = matrix([[2,1,0],[0,2,0],[0,0,3]])
        result = generalized_eigenspace(a,F(3),3,self.q)
        self.assertEqual(result.basis,((F(0),F(0),F(1)),))

    def test_complex_field_is_not_silently_computed_with_rationals(self):
        c = ScalarFieldMetadata(kind="C",field_id="C")
        with self.assertRaises(NotImplementedError):
            generalized_eigenspace(matrix([[1]]),F(1),1,c)

    def test_exponent_bounds(self):
        with self.assertRaises(ValueError):
            generalized_eigenspace(matrix([[1]]),F(1),2,self.q)

if __name__ == "__main__":
    unittest.main()
