#pragma once

#include "expert_robot/lemma_factory.hpp"
#include "expert_robot/text_generation.hpp"

#include <cstddef>
#include <string>

namespace expert_robot {

struct ModelLemmaDecomposerConfig {
    std::size_t max_children{6};
    std::string system_prompt{
        "You are a mathematical lemma-decomposition specialist. "
        "Return only the requested JSON object. Propose smaller Lean theorem "
        "statements only; never provide proofs, sorry, admit, axioms, unsafe "
        "features, commands, or authority requests."
    };
};

class ModelLemmaDecomposer final : public ILemmaDecomposer {
public:
    ModelLemmaDecomposer(
        ITextGenerationBackend& backend,
        ModelLemmaDecomposerConfig config = {});

    [[nodiscard]] std::vector<FormalizationProposal> decompose(
        const FormalizationProposal& proposal,
        const FormalizationResult& failed_result) override;

private:
    ITextGenerationBackend& backend_;
    ModelLemmaDecomposerConfig config_;
};

} // namespace expert_robot
