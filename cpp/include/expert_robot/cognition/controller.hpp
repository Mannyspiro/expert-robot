#pragma once

#include "expert_robot/cognition/interoception.hpp"
#include "expert_robot/cognition/neuromodulation.hpp"
#include "expert_robot/cognition/personality.hpp"

namespace expert_robot::cognition {

struct CognitionCycle {
    InteroceptiveReading interoception;
    NeuromodulatorState neuromodulators;
    ExecutiveBias affect;
    ExecutiveDecision decision;
};

/**
 * End-to-end deterministic cognition control stack.
 *
 * Personality is stable. Interoception and neuromodulators are transient.
 * The output is a search-policy decision only.
 */
class CognitionController {
public:
    explicit CognitionController(
        PersonalityProfile personality = math_researcher_personality(),
        InteroceptionConfig interoception_config = {},
        NeuromodulationConfig neuromodulation_config = {});

    [[nodiscard]] CognitionCycle step(
        const InteroceptiveSensors& sensors,
        const LogicalAssessment& logic);

    void reset_transient_state();

    [[nodiscard]] const PersonalityProfile& personality() const noexcept;
    [[nodiscard]] const InteroceptiveState& interoceptive_state() const noexcept;
    [[nodiscard]] const NeuromodulatorState& neuromodulator_state() const noexcept;

private:
    ArtificialInteroception interoception_;
    SoftwareNeuromodulators neuromodulators_;
    PersonalityExecutive personality_;
};

} // namespace expert_robot::cognition
