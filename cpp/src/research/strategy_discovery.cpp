#include "expert_robot/research/strategy_discovery.hpp"

#include <stdexcept>

namespace expert_robot::research {
namespace {

std::optional<ProofRouteKind>
route_kind_for_research_action(
    ResearchAction action) {
    switch (action) {
        case ResearchAction::RunImagination:
            return ProofRouteKind::ImaginationCandidate;

        case ResearchAction::RunLemmaFactory:
            return ProofRouteKind::RecursiveDecomposition;

        case ResearchAction::RetryParentProof:
            return ProofRouteKind::IntensifyVerification;

        // These are baseline plumbing, formal checking, or terminal actions;
        // they do not by themselves identify a reusable strategic move.
        case ResearchAction::Retrieve:
        case ResearchAction::AttemptDirectProof:
        case ResearchAction::VerifyCandidate:
        case ResearchAction::ConsolidateVerifiedKnowledge:
        case ResearchAction::StopComplete:
        case ResearchAction::StopExhausted:
            return std::nullopt;
    }

    return std::nullopt;
}

} // namespace

std::optional<DiscoveredResearchStrategy>
discover_research_strategy(
    const ResearchState& state,
    std::size_t max_steps) {
    if (max_steps == 0U) {
        throw std::invalid_argument(
            "strategy discovery max_steps must be positive");
    }

    std::vector<ProofRouteKind> steps;
    steps.reserve(max_steps);

    for (const auto& transition :
         state.history) {
        const auto kind =
            route_kind_for_research_action(
                transition.action);

        if (!kind.has_value()) {
            continue;
        }

        // Compress repeated cycles into a method signature rather than
        // memorizing incidental retry counts.
        if (!steps.empty() &&
            steps.back() == *kind) {
            continue;
        }

        steps.push_back(*kind);
        if (steps.size() >= max_steps) {
            break;
        }
    }

    if (steps.size() < 2U) {
        return std::nullopt;
    }

    const std::string signature =
        research_strategy_signature(
            steps);

    return DiscoveredResearchStrategy{
        .strategy_id =
            research_strategy_id(
                signature),
        .signature =
            signature,
        .title =
            research_strategy_title(
                steps),
        .steps =
            std::move(steps),
    };
}

} // namespace expert_robot::research
