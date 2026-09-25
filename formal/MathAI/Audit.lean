import MathAI

/-!
# Formal qualification audit

This file is compiled by the dedicated formal-qualification workflow.
It deliberately names each theorem in the seed registry so CI emits the
kernel-visible axiom dependencies for review.
-/

#check MathAI.Trust.add_zero_verified
#print axioms MathAI.Trust.add_zero_verified

#check MathAI.Trust.square_nonnegative
#print axioms MathAI.Trust.square_nonnegative

#check MathAI.Geometry.origin_on_xy_plane
#print axioms MathAI.Geometry.origin_on_xy_plane

#check MathAI.Geometry.unit_x_on_unit_sphere
#print axioms MathAI.Geometry.unit_x_on_unit_sphere
