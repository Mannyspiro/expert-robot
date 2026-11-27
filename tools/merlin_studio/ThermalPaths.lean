import Mathlib

namespace MerlinStudio

/-- The equal split gives the same temperature rise on either equal branch
    of the ideal linear model ΔT = P × R. -/
theorem equal_branch_rise (power resistance : ℚ) :
    (power / 2) * resistance = (power * resistance) / 2 := by
  ring

/-- Both branch powers add to the input power in the stipulated model. -/
theorem equal_branch_power (power : ℚ) :
    power / 2 + power / 2 = power := by
  ring

end MerlinStudio
