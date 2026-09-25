#pragma once

#include "expert_robot/formalizer.hpp"
#include "expert_robot/text_generation.hpp"

#include <string>
#include <vector>

namespace expert_robot {

struct InformalFormalizationRequest {
    std::string name_hint;
    std::string name_space{"MathAI.Generated"};
    std::string informal_claim;
    std::string domain{"unknown"};
    std::vector<std::string> imports{"MathAI"};
    std::vector<std::string> context;
};

struct ModelFormalizationResult {
    FormalizationProposal proposal;
    std::string raw_output;
};

class ModelFormalizationProposer {
public:
    explicit ModelFormalizationProposer(
        ITextGenerationBackend& backend);

    [[nodiscard]] ModelFormalizationResult propose(
        const InformalFormalizationRequest& request);

private:
    ITextGenerationBackend& backend_;
};

[[nodiscard]] ModelFormalizationResult
parse_formalization_proposal_json(
    std::string_view json);

} // namespace expert_robot
