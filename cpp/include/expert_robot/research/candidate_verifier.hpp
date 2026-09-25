#pragma once

#include "expert_robot/formalizer.hpp"
#include "expert_robot/imagination/idea.hpp"
#include "expert_robot/model_formalization_proposer.hpp"

#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace expert_robot::research {

struct CandidateVerifierConfig {
    std::size_t max_candidates{3};
};

struct CandidateVerification {
    std::string idea_id;
    bool proposal_generated{false};
    std::optional<FormalizationProposal> proposal;
    std::optional<FormalizationResult> formalization;
    std::string error;

    [[nodiscard]] bool proven() const noexcept {
        return formalization.has_value() &&
               formalization->proven();
    }
};

class CandidateVerifier {
public:
    CandidateVerifier(
        ModelFormalizationProposer& proposer,
        IProofSearcher& searcher,
        CandidateVerifierConfig config = {});

    [[nodiscard]] std::vector<CandidateVerification> verify(
        std::string_view original_goal,
        std::string_view domain,
        const std::vector<imagination::IdeaCandidate>& candidates,
        const std::vector<std::string>& context = {});

private:
    ModelFormalizationProposer& proposer_;
    IProofSearcher& searcher_;
    CandidateVerifierConfig config_;
};

} // namespace expert_robot::research
