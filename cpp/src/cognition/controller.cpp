#include "expert_robot/cognition/controller.hpp"

#include <stdexcept>

namespace expert_robot::cognition {

CognitionController::CognitionController(
    PersonalityProfile personality,
    InteroceptionConfig interoception_config,
    NeuromodulationConfig neuromodulation_config)
    : interoception_(interoception_config),
      neuromodulators_(neuromodulation_config),
      personality_(personality) {}

CognitionCycle CognitionController::step(
    const InteroceptiveSensors& sensors,
    const LogicalAssessment& logic) {
    auto reading = interoception_.observe(sensors);
    const auto affect = neuromodulators_.update(reading.cognitive_signals);
    const auto decision =
        personality_.decide(logic, reading.state, affect);

    if (decision.verification_rigor_multiplier != 1.0 ||
        decision.authority_delta != 0.0 ||
        affect.verification_rigor_multiplier != 1.0 ||
        affect.authority_delta != 0.0) {
        throw std::logic_error(
            "cognition trust invariant violated");
    }

    return CognitionCycle{
        .interoception = std::move(reading),
        .neuromodulators = neuromodulators_.state(),
        .affect = affect,
        .decision = decision,
    };
}

void CognitionController::reset_transient_state() {
    interoception_.reset();
    neuromodulators_.reset();
}

const PersonalityProfile& CognitionController::personality() const noexcept {
    return personality_.profile();
}

const InteroceptiveState& CognitionController::interoceptive_state() const noexcept {
    return interoception_.state();
}

const NeuromodulatorState& CognitionController::neuromodulator_state() const noexcept {
    return neuromodulators_.state();
}

} // namespace expert_robot::cognition
