# Merlin Research: Curvature and Spherical Holonomy v0.1

**Status:** classical theorem + numerical finite experiment.
**Implementation:** `merlin/spherical_holonomy.py`
**Tests:** `tests/test_merlin_spherical_holonomy.py`

## Why this experiment matters

The multi-frame linear prototype constructs every coordinate transition from a shared family of frame maps (P_i). Its closed loops are identity by cancellation. Curved-space parallel transport is different: it is defined by a connection, and transporting a tangent vector around a closed loop can rotate the vector even though the base point returns to itself.

This is the mathematical distinction between a coordinate-transition cocycle and connection holonomy.

## Sphere model

On the unit sphere (S^2\subset\mathbb R^3), the induced metric has Gaussian curvature (K=1). For a positively oriented geodesic triangle with interior angles (A,B,C), its spherical excess and area are

[
\mathcal A=A+B+C-\pi.
]

The Gauss–Bonnet theorem gives the holonomy angle of Levi-Civita parallel transport around the geodesic boundary as

[
\Delta\varphi=\int_{\Sigma}K\,dA=\mathcal A\pmod{2\pi},
]

with sign determined by loop orientation.

For the octant triangle with vertices (p=(1,0,0)), (q=(0,1,0)), (r=(0,0,1)), all interior angles are (pi/2), so

[
\mathcal A=3\pi/2-\pi=\pi/2.
]

Starting with tangent vector (v_0=(0,1,0)) at p, parallel transport around p→q→r→p returns (v_1=(0,0,1)). This is a +90° rotation in the tangent plane at p. Reversing the loop reverses the sign.

## Numerical transport

For non-antipodal unit points p and q, the shorter great-circle arc lies in their span. Let (n=(p\times q)/\|p\times q\|) and (\theta=\operatorname{atan2}(\|p\times q\|,p\cdot q)). Parallel transport along this arc is the ambient Rodrigues rotation about n by θ. The implementation checks unit endpoints, tangent input, tangent output, norm preservation and antipodal ambiguity.

The signed holonomy angle is measured in the tangent plane using

[
\operatorname{atan2}\big(p\cdot(v_0\times v_1),v_0\cdot v_1\big).
]

## Evidence and limitations

The experiment uses floating-point trigonometry with explicit tolerances. It tests one exact geometric configuration (the octant triangle), loop reversal, tangent preservation and invalid inputs. It is a numerical check of a classical result, not a new theorem or a formal proof of Gauss–Bonnet.

## Next research steps

1. Test non-octant spherical triangles and compare measured holonomy with the exact spherical-area formula.
2. Add mesh-based transport and convergence checks.
3. Derive curvature from infinitesimal loops and compare with finite-loop holonomy.
4. Extend from (S^2) to a torus and then to a declared spacetime metric.
5. Formalize the algebraic path-composition layer separately from the differential-geometric connection layer.
6. Add XMG operators for `CONNECTION`, `PARALLEL_TRANSPORT`, `CURVATURE` and `HOLONOMY`, each with explicit domains and evidence status.
