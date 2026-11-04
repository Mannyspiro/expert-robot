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

#check MathAI.EquationAtlas.square_nonnegative
#print axioms MathAI.EquationAtlas.square_nonnegative

#check MathAI.EquationAtlas.square_sum_ge_four_product
#print axioms MathAI.EquationAtlas.square_sum_ge_four_product

#check MathAI.EquationAtlas.normalized_logistic_growth_nonnegative
#print axioms MathAI.EquationAtlas.normalized_logistic_growth_nonnegative

#check MathAI.WireQualification.current_within_derated_ampacity
#print axioms MathAI.WireQualification.current_within_derated_ampacity

#check MathAI.WireQualification.dc_voltage_drop_nonnegative
#print axioms MathAI.WireQualification.dc_voltage_drop_nonnegative

#check MathAI.WireQualification.corrected_resistance_positive
#print axioms MathAI.WireQualification.corrected_resistance_positive

#check MathAI.WireQualification.lumped_thermal_fixed_point_unique
#print axioms MathAI.WireQualification.lumped_thermal_fixed_point_unique

#check MathAI.WireQualification.measured_clearance_meets_requirement
#print axioms MathAI.WireQualification.measured_clearance_meets_requirement

#check MathAI.WireQualification.minimum_bend_radius_meets_requirement
#print axioms MathAI.WireQualification.minimum_bend_radius_meets_requirement

#check MathAI.FractalEngineering.levelCount_compose
#print axioms MathAI.FractalEngineering.levelCount_compose

#check MathAI.FractalEngineering.levelScale_compose
#print axioms MathAI.FractalEngineering.levelScale_compose

#check MathAI.FractalEngineering.weighted_self_similarity_balance
#print axioms MathAI.FractalEngineering.weighted_self_similarity_balance

#check MathAI.FractalEngineering.levelScale_bounds
#print axioms MathAI.FractalEngineering.levelScale_bounds

#check MathAI.FractalEngineering.levelScale_step_nonincreasing
#print axioms MathAI.FractalEngineering.levelScale_step_nonincreasing
