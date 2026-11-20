# Mathematical lenses with explicit meaning

Always consider applicability; apply only with a declared mapping and test.

| Lens | Useful role | Required invariant and boundary |
| --- | --- | --- |
| Simplex | Convex mixtures, bounded resource trade-offs, barycentric state interpolation | Nonnegative coordinates sum to one; preserve dimensions/units; normalization is not evidence or a calibrated probability |
| N-ality | Describe n-way relations or multi-channel structures without collapsing distinct axes | Record geometric dimension, state dimension, logical channels and temporal parameters separately; distinguish measured interactions from a visual metaphor |
| Continuum | Model fields, transitions, parameter families and interpolation | Declare domain, carrier, boundary/gluing conditions, representation/basis, discretization/error and refinement test; sampled agreement is not a general existence/uniqueness theorem |
| Fuzzy logic | Declared graded categories and heuristic prioritization | Specify membership functions/units/thresholds and t-norm/t-conorm; memberships are not probabilities; do not make authorization or qualification fuzzy |

A triangle diagram with a central point is not evidence of a three-way physical interaction. An n-vertex standard simplex has abstract dimension n-1; that does not set its state-carrier dimension or number of logical channels. A generic convex blend does not establish affine independence or unique barycentric coordinates for arbitrary vertices.

Merlin's existing canonical contract is cpp/include/expert_robot/math/continuum_simplex.hpp with a versioned continuum-structure IR. Preserve its distinctions between incompatible shared vertices, an affine extension, and a boundary requiring a different extension. Failure of an affine model is not proof that no continuous extension exists.

Start with reference calculations and invariants: vertex reconstruction and convex bounds, compatible piecewise-linear interpolation, independently typed n-ality axes, bounded/monotone membership functions, explicit min/max fuzzy operators. Record numerical precision. For empirical use, compare to measurements and original-domain baselines, not just internally coherent geometry.

For any proposed decision record the lens, mapping, assumptions, exact/approximate status, meaningful predictions, counterexample and translation-back acceptance test. Retain not_applicable/deferred reasons. Scientific truth and physical or formal qualification do not follow from a geometric or fuzzy score.

Grounding: [Merlin mathematical contract](https://github.com/Mannyspiro/expert-robot/blob/d074cab60ea61411373098cb86562109813b3a3a/cpp/include/expert_robot/math/continuum_simplex.hpp), [SciPy barycentric examples](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.spatial.Delaunay.html), [Scholarpedia Fuzzy logic](https://www.scholarpedia.org/article/Fuzzy_logic). These are model/representation references, not evidence of a general Merlin capability improvement.
