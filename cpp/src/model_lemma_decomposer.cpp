#include "expert_robot/model_lemma_decomposer.hpp"

#include <stdexcept>
#include <utility>

namespace expert_robot {

ModelLemmaDecomposer::ModelLemmaDecomposer(
    ITextGenerationBackend& backend,
    ModelLemmaDecomposerConfig config)
    : backend_(backend), config_(std::move(config)) {
    if (config_.max_children == 0U) {
        throw std::invalid_argument(
            "model lemma decomposer max_children must be positive");
    }
    if (config_.system_prompt.empty()) {
        throw std::invalid_argument(
            "model lemma decomposer system prompt must be non-empty");
    }
}

std::vector<FormalizationProposal> ModelLemmaDecomposer::decompose(
    const FormalizationProposal& proposal,
    const FormalizationResult& failed_result) {
    const auto generated = backend_.generate(
        TextGenerationRequest{
            .system_prompt = config_.system_prompt,
            .user_prompt = decomposition_prompt(
                proposal,
                failed_result,
                config_.max_children),
        });

    if (!generated.ok) {
        throw std::runtime_error(
            "math model lemma decomposition failed: exit_code=" +
            std::to_string(generated.exit_code) +
            (generated.timed_out ? " timeout" : "") +
            (generated.diagnostics.empty()
                 ? std::string{}
                 : " diagnostics=" + generated.diagnostics));
    }

    return parse_decomposition_json(
        generated.output,
        config_.max_children);
}

} // namespace expert_robot
