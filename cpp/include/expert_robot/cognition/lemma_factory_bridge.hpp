#pragma once

#include "expert_robot/cognition/controller.hpp"
#include "expert_robot/lemma_factory.hpp"

#include <optional>

namespace expert_robot::cognition {

struct LemmaFactoryActivation {
    bool invoked{false};
    std::optional<LemmaFactoryNode> result;
};

/**
 * Search-policy bridge from the personality executive to recursive
 * decomposition. The factory runs only when the selected cognitive action is
 * DecomposeProblem.
 */
class CognitionLemmaBridge {
public:
    explicit CognitionLemmaBridge(RecursiveLemmaFactory& factory);

    [[nodiscard]] LemmaFactoryActivation run_if_selected(
        const CognitionCycle& cycle,
        FormalizationProposal proposal);

private:
    RecursiveLemmaFactory& factory_;
};

} // namespace expert_robot::cognition
