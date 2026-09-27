#include "expert_robot/research/strategy_discovery.hpp"

#include <cassert>

int main() {
    using namespace expert_robot::research;

    ResearchState state;
    state.history = {
        {
            .from = ResearchPhase::Intake,
            .to = ResearchPhase::RetrieveKnown,
            .action = ResearchAction::Retrieve,
            .reason = "retrieve"
        },
        {
            .from = ResearchPhase::RetrieveKnown,
            .to = ResearchPhase::DirectProof,
            .action = ResearchAction::AttemptDirectProof,
            .reason = "direct"
        },
        {
            .from = ResearchPhase::DirectProof,
            .to = ResearchPhase::Imagine,
            .action = ResearchAction::RunImagination,
            .reason = "reframe"
        },
        {
            .from = ResearchPhase::Imagine,
            .to = ResearchPhase::VerifyCandidate,
            .action = ResearchAction::VerifyCandidate,
            .reason = "check"
        },
        {
            .from = ResearchPhase::VerifyCandidate,
            .to = ResearchPhase::Imagine,
            .action = ResearchAction::RunImagination,
            .reason = "retry imagination"
        },
        {
            .from = ResearchPhase::Imagine,
            .to = ResearchPhase::Decompose,
            .action = ResearchAction::RunLemmaFactory,
            .reason = "decompose"
        },
        {
            .from = ResearchPhase::Decompose,
            .to = ResearchPhase::RetryParent,
            .action = ResearchAction::RetryParentProof,
            .reason = "verify parent"
        },
        {
            .from = ResearchPhase::RetryParent,
            .to = ResearchPhase::Consolidate,
            .action = ResearchAction::ConsolidateVerifiedKnowledge,
            .reason = "accepted"
        }
    };

    const auto discovered =
        discover_research_strategy(
            state,
            3);

    assert(discovered.has_value());
    assert(discovered->steps.size() == 3);
    assert(
        discovered->steps[0] ==
        ProofRouteKind::ImaginationCandidate);
    assert(
        discovered->steps[1] ==
        ProofRouteKind::RecursiveDecomposition);
    assert(
        discovered->steps[2] ==
        ProofRouteKind::IntensifyVerification);

    assert(
        discovered->title ==
        "Imagine, decompose, verify");

    const auto expected_signature =
        research_strategy_signature(
            discovered->steps);

    assert(
        discovered->signature ==
        expected_signature);
    assert(
        discovered->strategy_id ==
        research_strategy_id(
            expected_signature));

    // A trajectory without at least two meaningful strategic moves should not
    // be promoted into cross-problem strategy memory.
    ResearchState trivial;
    trivial.history = {
        {
            .from = ResearchPhase::Intake,
            .to = ResearchPhase::RetrieveKnown,
            .action = ResearchAction::Retrieve,
            .reason = "retrieve"
        },
        {
            .from = ResearchPhase::RetrieveKnown,
            .to = ResearchPhase::DirectProof,
            .action = ResearchAction::AttemptDirectProof,
            .reason = "direct"
        },
        {
            .from = ResearchPhase::DirectProof,
            .to = ResearchPhase::Decompose,
            .action = ResearchAction::RunLemmaFactory,
            .reason = "one move"
        }
    };

    assert(
        !discover_research_strategy(
             trivial,
             3).has_value());

    bool invalid_rejected = false;
    try {
        (void)discover_research_strategy(
            state,
            0);
    } catch (const std::invalid_argument&) {
        invalid_rejected = true;
    }
    assert(invalid_rejected);

    return 0;
}
