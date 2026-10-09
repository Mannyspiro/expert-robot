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

#check MathAI.Geometry.dot_comm
#print axioms MathAI.Geometry.dot_comm

#check MathAI.Geometry.dot_zero_left
#print axioms MathAI.Geometry.dot_zero_left

#check MathAI.Geometry.dot_zero_right
#print axioms MathAI.Geometry.dot_zero_right

#check MathAI.Geometry.orthogonal_symm
#print axioms MathAI.Geometry.orthogonal_symm

#check MathAI.Geometry.zero_orthogonal_left
#print axioms MathAI.Geometry.zero_orthogonal_left

#check MathAI.Geometry.zero_orthogonal_right
#print axioms MathAI.Geometry.zero_orthogonal_right

#check MathAI.Geometry.squaredDistance_self
#print axioms MathAI.Geometry.squaredDistance_self

#check MathAI.Geometry.squaredDistance_symm
#print axioms MathAI.Geometry.squaredDistance_symm

#check MathAI.Geometry.squaredDistance_nonnegative
#print axioms MathAI.Geometry.squaredDistance_nonnegative

#check MathAI.Geometry.validSphere_of_pointOnSphere
#print axioms MathAI.Geometry.validSphere_of_pointOnSphere

#check MathAI.Geometry.squaredDistance_eq_radius_of_pointOnSphere
#print axioms MathAI.Geometry.squaredDistance_eq_radius_of_pointOnSphere

#check MathAI.Geometry.cross_zero_left
#print axioms MathAI.Geometry.cross_zero_left

#check MathAI.Geometry.cross_zero_right
#print axioms MathAI.Geometry.cross_zero_right

#check MathAI.Geometry.cross_self
#print axioms MathAI.Geometry.cross_self

#check MathAI.Geometry.vecBetween_self
#print axioms MathAI.Geometry.vecBetween_self

#check MathAI.Geometry.parallel_zero_left
#print axioms MathAI.Geometry.parallel_zero_left

#check MathAI.Geometry.parallel_zero_right
#print axioms MathAI.Geometry.parallel_zero_right

#check MathAI.Geometry.parallel_self
#print axioms MathAI.Geometry.parallel_self

#check MathAI.Geometry.dot_self_nonnegative
#print axioms MathAI.Geometry.dot_self_nonnegative

#check MathAI.Geometry.validPlane_of_pointOnPlane
#print axioms MathAI.Geometry.validPlane_of_pointOnPlane

#check MathAI.Geometry.validLine_of_pointOnLine
#print axioms MathAI.Geometry.validLine_of_pointOnLine

#check MathAI.Geometry.squaredDistance_eq_dot_vecBetween
#print axioms MathAI.Geometry.squaredDistance_eq_dot_vecBetween

#check MathAI.Geometry.cross_orthogonal_left
#print axioms MathAI.Geometry.cross_orthogonal_left

#check MathAI.Geometry.cross_orthogonal_right
#print axioms MathAI.Geometry.cross_orthogonal_right

#check MathAI.Geometry.squaredDistance_origin_quarterTurnZ
#print axioms MathAI.Geometry.squaredDistance_origin_quarterTurnZ

#check MathAI.Geometry.pointOn_xyCircleAtOrigin_quarterTurnZ
#print axioms MathAI.Geometry.pointOn_xyCircleAtOrigin_quarterTurnZ

#check MathAI.Geometry.squaredDistance_left_midpoint
#print axioms MathAI.Geometry.squaredDistance_left_midpoint

#check MathAI.Geometry.squaredDistance_midpoint_midpoint_shared
#print axioms MathAI.Geometry.squaredDistance_midpoint_midpoint_shared

#check MathAI.Geometry.midpoint_comm
#print axioms MathAI.Geometry.midpoint_comm

#check MathAI.Beam.corrected_solution
#print axioms MathAI.Beam.corrected_solution

#check MathAI.Beam.exact_error
#print axioms MathAI.Beam.exact_error

#check MathAI.Beam.coordinate_error_bound
#print axioms MathAI.Beam.coordinate_error_bound

#check MathAI.Molecular.energy_defect_bound
#print axioms MathAI.Molecular.energy_defect_bound

#check MathAI.Molecular.energy_endpoint_bound
#print axioms MathAI.Molecular.energy_endpoint_bound

#check MathAI.Graph.l1Distance_append
#print axioms MathAI.Graph.l1Distance_append

#check MathAI.Graph.l1AppendReal_norm_sub
#print axioms MathAI.Graph.l1AppendReal_norm_sub
