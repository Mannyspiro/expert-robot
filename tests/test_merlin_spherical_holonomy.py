import math
import unittest

from merlin.spherical_holonomy import (
    vec3, norm, dot, transport_loop, oriented_spherical_triangle_area,
    signed_holonomy_angle, parallel_transport_geodesic,
)


class SphericalHolonomyTests(unittest.TestCase):
    def setUp(self):
        self.p=vec3([1,0,0])
        self.q=vec3([0,1,0])
        self.r=vec3([0,0,1])
        self.initial=vec3([0,1,0])

    def test_octant_triangle_area_is_pi_over_two(self):
        area=oriented_spherical_triangle_area(self.p,self.q,self.r)
        self.assertAlmostEqual(area,math.pi/2,places=10)

    def test_parallel_transport_holonomy_equals_spherical_area(self):
        final=transport_loop([self.p,self.q,self.r],self.initial)
        angle=signed_holonomy_angle(self.p,self.initial,final)
        area=oriented_spherical_triangle_area(self.p,self.q,self.r)
        self.assertAlmostEqual(angle,area,places=10)
        self.assertAlmostEqual(norm(final),norm(self.initial),places=10)
        self.assertAlmostEqual(dot(self.p,final),0.0,places=10)

    def test_reversing_loop_reverses_holonomy(self):
        final=transport_loop([self.p,self.r,self.q],self.initial)
        angle=signed_holonomy_angle(self.p,self.initial,final)
        area=oriented_spherical_triangle_area(self.p,self.r,self.q)
        self.assertAlmostEqual(angle,area,places=10)
        self.assertAlmostEqual(angle,-math.pi/2,places=10)

    def test_single_geodesic_transport_preserves_tangent_norm(self):
        v=parallel_transport_geodesic(self.p,self.q,self.initial)
        self.assertAlmostEqual(norm(v),norm(self.initial),places=10)
        self.assertAlmostEqual(dot(self.q,v),0.0,places=10)

    def test_antipodal_edge_is_rejected(self):
        with self.assertRaises(ValueError):
            parallel_transport_geodesic(self.p,vec3([-1,0,0]),self.initial)

    def test_non_tangent_initial_vector_is_rejected(self):
        with self.assertRaises(ValueError):
            parallel_transport_geodesic(self.p,self.q,vec3([1,0,0]))

    def test_triangle_requires_unit_vertices(self):
        with self.assertRaises(ValueError):
            oriented_spherical_triangle_area(vec3([2,0,0]),self.q,self.r)


if __name__ == "__main__":
    unittest.main()
