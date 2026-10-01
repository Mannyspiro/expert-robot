#include "expert_robot/research/candidate_verifier.hpp"

#include <algorithm>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>

namespace expert_robot::research {
namespace {

std::string name_hint(
    std::string_view idea_id,
    std::size_t index) {
    std::string suffix;
    const std::size_t take =
        std::min<std::size_t>(
            12U,
            idea_id.size());

    suffix.assign(
        idea_id.substr(0, take));

    if (suffix.empty()) {
        suffix =
            std::to_string(index);
    }

    for (auto& ch : suffix) {
        const bool valid =
            (ch >= 'A' && ch <= 'Z') ||
            (ch >= 'a' && ch <= 'z') ||
            (ch >= '0' && ch <= '9') ||
            ch == '_';
        if (!valid) ch = '_';
    }

    return "idea_" + suffix;
}

} // namespace

CandidateVerifier::CandidateVerifier(
    ModelFormalizationProposer& proposer,
    IProofSearcher& searcher,
    CandidateVerifierConfig config)
    : proposer_(proposer),
      searcher_(searcher),
      config_(config) {
    if (config_.max_candidates == 0U) {
        throw std::invalid_argument(
            "candidate verifier max_candidates must be positive");
    }
}

std::vector<CandidateVerification>
CandidateVerifier::verify(
    std::string_view original_goal,
    std::string_view domain,
    const std::vector<imagination::IdeaCandidate>& candidates,
    const std::vector<std::string>& context) {
    if (original_goal.empty()) {
        throw std::invalid_argument(
            "candidate verifier original_goal must be non-empty");
    }

    const std::size_t count =
        std::min(
            config_.max_candidates,
            candidates.size());

    std::vector<CandidateVerification> results;
    results.reserve(count);

    for (std::size_t i = 0;
         i < count;
         ++i) {
        const auto& idea =
            candidates[i];

        CandidateVerification result;
        result.idea_id = idea.idea_id;

        if (!idea.skeptic_valid ||
            !idea.skeptic_keep) {
            result.error =
                "candidate did not pass skeptic gate";
            results.push_back(
                std::move(result));
            continue;
        }

        std::ostringstream informal;
        informal
            << "Original target:\n"
            << original_goal
            << "\n\nCandidate mechanism:\n"
            << idea.text
            << "\n\nExtract ONE precise helper theorem or testable "
            << "mathematical claim whose Lean verification would materially "
            << "support or falsify this candidate mechanism. Do not claim the "
            << "original target is proved.";

        auto proposal_context =
            context;
        proposal_context.push_back(
            "imagination_lens=" +
            std::string(
                imagination::lens_name(
                    idea.lens)));
        proposal_context.push_back(
            "skeptic_risk=" +
            std::to_string(
                idea.skeptic_risk));
        if (!idea.skeptic_critique.empty()) {
            proposal_context.push_back(
                "skeptic_critique=" +
                idea.skeptic_critique);
        }

        try {
            auto proposed =
                proposer_.propose(
                    InformalFormalizationRequest{
                        .name_hint =
                            name_hint(
                                idea.idea_id,
                                i),
                        .name_space =
                            "MathAI.Generated",
                        .informal_claim =
                            informal.str(),
                        .domain =
                            domain.empty()
                                ? "unknown"
                                : std::string(domain),
                        .imports =
                            {"MathAI"},
                        .context =
                            std::move(
                                proposal_context),
                    });

            result.proposal_generated = true;
            result.proposal =
                proposed.proposal;

            auto formal =
                formalize(
                    proposed.proposal,
                    searcher_);

            result.formalization =
                std::move(formal);
        } catch (const std::exception& e) {
            result.error = e.what();
        }

        results.push_back(
            std::move(result));
    }

    return results;
}

} // namespace expert_robot::research
