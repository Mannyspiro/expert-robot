#include "expert_robot/cognition/lemma_factory_bridge.hpp"

#include <utility>

namespace expert_robot::cognition {

CognitionLemmaBridge::CognitionLemmaBridge(
    RecursiveLemmaFactory& factory)
    : factory_(factory) {}

LemmaFactoryActivation CognitionLemmaBridge::run_if_selected(
    const CognitionCycle& cycle,
    FormalizationProposal proposal) {
    if (cycle.decision.action != CognitiveAction::DecomposeProblem) {
        return LemmaFactoryActivation{
            .invoked = false,
            .result = std::nullopt,
        };
    }

    return LemmaFactoryActivation{
        .invoked = true,
        .result = factory_.solve(std::move(proposal)),
    };
}

} // namespace expert_robot::cognition
