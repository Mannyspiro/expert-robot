import unittest
from fractions import Fraction as F

from merlin.rotation_representations import (
    quaternion, vector3, qmul, qconj, qnorm_sq, qrotate, q_to_matrix,
    matrix_rotate, gp, quaternion_to_rotor, rotor_rotate, complex_plane_rotate,
)


class RotationRepresentationTests(unittest.TestCase):
    def test_quaternion_units_follow_quaternion_multiplication(self):
        i=quaternion([0,1,0,0]); j=quaternion([0,0,1,0]); k=quaternion([0,0,0,1])
        self.assertEqual(qmul(i,j),k)
        self.assertEqual(qmul(j,k),i)
        self.assertEqual(qmul(k,i),j)

    def test_quaternion_to_cl3_even_subalgebra_is_multiplicative(self):
        i=quaternion([0,1,0,0]); j=quaternion([0,0,1,0]); k=quaternion([0,0,0,1])
        self.assertEqual(gp(quaternion_to_rotor(i),quaternion_to_rotor(j)),
                         quaternion_to_rotor(k))

    def test_180_degree_z_rotation_matches_all_three_views(self):
        q=quaternion([0,0,0,1])
        v=vector3([1,2,3])
        expected=vector3([-1,-2,3])
        self.assertEqual(qrotate(q,v),expected)
        self.assertEqual(matrix_rotate(q_to_matrix(q),v),expected)
        self.assertEqual(rotor_rotate(q,v),expected)

    def test_180_degree_x_and_y_rotations(self):
        v=vector3([1,2,3])
        self.assertEqual(qrotate(quaternion([0,1,0,0]),v),vector3([1,-2,-3]))
        self.assertEqual(rotor_rotate(quaternion([0,1,0,0]),v),vector3([1,-2,-3]))
        self.assertEqual(qrotate(quaternion([0,0,1,0]),v),vector3([-1,2,-3]))
        self.assertEqual(rotor_rotate(quaternion([0,0,1,0]),v),vector3([-1,2,-3]))

    def test_exact_120_degree_rotation_cycles_coordinate_axes(self):
        q=quaternion([F(1,2),F(1,2),F(1,2),F(1,2)])
        e1=vector3([1,0,0]); e2=vector3([0,1,0]); e3=vector3([0,0,1])
        self.assertEqual(qrotate(q,e1),e2)
        self.assertEqual(qrotate(q,e2),e3)
        self.assertEqual(qrotate(q,e3),e1)
        self.assertEqual(rotor_rotate(q,e1),e2)
        self.assertEqual(rotor_rotate(q,e2),e3)
        self.assertEqual(rotor_rotate(q,e3),e1)
        expected=((F(0),F(0),F(1)),(F(1),F(0),F(0)),(F(0),F(1),F(0)))
        self.assertEqual(q_to_matrix(q),expected)

    def test_complex_plane_view_matches_quaternion_matrix_and_rotor_for_all_axes(self):
        c,s=F(-7,25),F(24,25)
        v=vector3([2,3,5])
        quaternions=[
            quaternion([F(3,5),F(4,5),0,0]),
            quaternion([F(3,5),0,F(4,5),0]),
            quaternion([F(3,5),0,0,F(4,5)]),
        ]
        for axis,q in enumerate(quaternions):
            expected=qrotate(q,v)
            self.assertEqual(complex_plane_rotate(v,axis,c,s),expected)
            self.assertEqual(matrix_rotate(q_to_matrix(q),v),expected)
            self.assertEqual(rotor_rotate(q,v),expected)

    def test_complex_plane_adapter_rejects_invalid_rotation(self):
        with self.assertRaises(ValueError):
            complex_plane_rotate(vector3([1,2,3]),2,F(1,2),F(1,2))
        with self.assertRaises(ValueError):
            complex_plane_rotate(vector3([1,2,3]),3,F(0),F(1))

    def test_q_and_minus_q_induce_same_rotation_matrix_and_action(self):
        q=quaternion([0,0,0,1])
        minus_q=tuple(-x for x in q)
        v=vector3([4,-5,6])
        self.assertEqual(q_to_matrix(q),q_to_matrix(minus_q))
        self.assertEqual(qrotate(q,v),qrotate(minus_q,v))
        self.assertEqual(rotor_rotate(q,v),rotor_rotate(minus_q,v))

    def test_rotation_matrix_is_orthogonal_with_determinant_one(self):
        m=q_to_matrix(quaternion([0,0,0,1]))
        transpose=tuple(tuple(m[j][i] for j in range(3)) for i in range(3))
        product=tuple(tuple(sum(transpose[i][k]*m[k][j] for k in range(3))
                            for j in range(3)) for i in range(3))
        self.assertEqual(product,((F(1),F(0),F(0)),(F(0),F(1),F(0)),(F(0),F(0),F(1))))
        det=(m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])
             -m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
             +m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))
        self.assertEqual(det,F(1))

    def test_non_unit_quaternion_is_rejected(self):
        with self.assertRaises(ValueError):
            qrotate(quaternion([1,1,0,0]),vector3([1,0,0]))

    def test_bad_vector_dimension_is_rejected(self):
        with self.assertRaises(ValueError):
            vector3([1,2])


if __name__ == "__main__":
    unittest.main()
