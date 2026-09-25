#include "expert_robot/research/route_memory.hpp"
#include "expert_robot/research/strategy_planner.hpp"

#include <cassert>
#include <filesystem>

namespace {

expert_robot::research::ProofRoute route(
    expert_robot::research::ProofRouteKind kind,
    const char* id,
    double score) {
    return expert_robot::research::ProofRoute{
        .kind = kind,
        .route_id = id,
        .description = id,
        .final_score = score
    };
}

expert_robot::research::ProofRouteSequence sequence(
    const char* id,
    std::vector<expert_robot::research::ProofRoute> steps,
    double score) {
    return expert_robot::research::ProofRouteSequence{
        .sequence_id = id,
        .steps = std::move(steps),
        .average_route_score = score,
        .synergy_score = 0.8,
        .final_score = score
    };
}

const expert_robot::research::ResearchStrategyPlan*
find_signature(
    const std::vector<expert_robot::research::ResearchStrategyPlan>& plans,
    const std::string& signature) {
    for (const auto& plan : plans) {
        if (plan.signature == signature) {
            return &plan;
        }
    }
    return nullptr;
}

} // namespace

int main() {
    using namespace expert_robot::research;

    const auto db =
        std::filesystem::temp_directory_path() /
        "expert-robot-strategy-planner.sqlite3";
    std::filesystem::remove(db);

    RouteOutcomeLedger memory(db);

    const auto seq_a =
        sequence(
            "seq-a",
            {
                route(
                    ProofRouteKind::RepresentationSwitch,
                    "switch-a",
                    0.72),
                route(
                    ProofRouteKind::RecursiveDecomposition,
                    "decompose-a",
                    0.78),
                route(
                    ProofRouteKind::IntensifyVerification,
                    "verify-a",
                    0.74)
            },
            0.76);

    const auto seq_b =
        sequence(
            "seq-b",
            {
                route(
                    ProofRouteKind::ImaginationCandidate,
                    "imagine-b",
                    0.75),
                route(
                    ProofRouteKind::RecursiveDecomposition,
                    "decompose-b",
                    0.74),
                route(
                    ProofRouteKind::IntensifyVerification,
                    "verify-b",
                    0.73)
            },
            0.75);

    ResearchStrategyPlanner baseline;

    const auto baseline_plans =
        baseline.plan(
            {seq_a, seq_b},
            "algebra");

    assert(baseline_plans.size() == 2);

    const std::string signature_a =
        research_strategy_signature(seq_a);
    const std::string signature_b =
        research_strategy_signature(seq_b);

    const auto* base_a =
        find_signature(
            baseline_plans,
            signature_a);
    const auto* base_b =
        find_signature(
            baseline_plans,
            signature_b);

    assert(base_a != nullptr);
    assert(base_b != nullptr);
    assert(
        base_a->strategy_id ==
        research_strategy_id(signature_a));
    assert(
        base_a->title ==
        "Reframe, decompose, verify");
    assert(
        base_b->title ==
        "Imagine, decompose, verify");

    for (int i = 0; i < 5; ++i) {
        memory.record_strategy(
            ResearchStrategyOutcome{
                .strategy_id =
                    base_a->strategy_id,
                .signature =
                    base_a->signature,
                .domain = "algebra",
                .verified_progress = true,
                .target_verified = true,
                .dead_end_escaped = true,
                .resource_cost = 0.20
            });

        memory.record_strategy(
            ResearchStrategyOutcome{
                .strategy_id =
                    base_b->strategy_id,
                .signature =
                    base_b->signature,
                .domain = "algebra",
                .verified_progress = false,
                .target_verified = false,
                .dead_end_escaped = false,
                .resource_cost = 0.80
            });
    }

    const auto exp_a =
        memory.strategy_experience(
            base_a->strategy_id,
            "algebra");
    const auto exp_b =
        memory.strategy_experience(
            base_b->strategy_id,
            "algebra");

    assert(exp_a.attempts == 5);
    assert(exp_a.target_verifications == 5);
    assert(
        exp_a.smoothed_verified_rate() >
        exp_b.smoothed_verified_rate());
    assert(
        exp_a.average_resource_cost() <
        exp_b.average_resource_cost());

    ResearchStrategyPlanner learned(
        ResearchStrategyPlannerConfig{},
        &memory);

    // New theorem-specific route IDs, same research methods.
    const auto seq_a_new =
        sequence(
            "seq-a-new-theorem",
            {
                route(
                    ProofRouteKind::RepresentationSwitch,
                    "switch-new",
                    0.70),
                route(
                    ProofRouteKind::RecursiveDecomposition,
                    "decompose-new",
                    0.76),
                route(
                    ProofRouteKind::IntensifyVerification,
                    "verify-new",
                    0.72)
            },
            0.74);

    const auto seq_b_new =
        sequence(
            "seq-b-new-theorem",
            {
                route(
                    ProofRouteKind::ImaginationCandidate,
                    "imagine-new",
                    0.76),
                route(
                    ProofRouteKind::RecursiveDecomposition,
                    "decompose-new-b",
                    0.75),
                route(
                    ProofRouteKind::IntensifyVerification,
                    "verify-new-b",
                    0.74)
            },
            0.75);

    const auto learned_plans =
        learned.plan(
            {seq_a_new, seq_b_new},
            "algebra");

    const auto* learned_a =
        find_signature(
            learned_plans,
            signature_a);
    const auto* learned_b =
        find_signature(
            learned_plans,
            signature_b);

    assert(learned_a != nullptr);
    assert(learned_b != nullptr);

    // Cross-theorem strategy evidence overcomes the small raw sequence-score
    // advantage of the historically weak method.
    assert(
        learned_a->final_score >
        learned_b->final_score);
    assert(
        learned_a->experience_adjustment >
        0.0);
    assert(
        learned_b->experience_adjustment <
        0.0);
    assert(
        learned_a->evidence_confidence > 0.0);
    assert(
        learned_a->evidence_confidence < 1.0);

    const double early_confidence =
        learned_a->evidence_confidence;
    const double early_adjustment =
        learned_a->experience_adjustment;

    for (int i = 0; i < 15; ++i) {
        memory.record_strategy(
            ResearchStrategyOutcome{
                .strategy_id =
                    learned_a->strategy_id,
                .signature =
                    learned_a->signature,
                .domain = "algebra",
                .verified_progress = true,
                .target_verified = true,
                .dead_end_escaped = true,
                .resource_cost = 0.20
            });
    }

    const auto mature =
        learned.plan(
            {seq_a_new, seq_b_new},
            "algebra");
    const auto* mature_a =
        find_signature(
            mature,
            signature_a);

    assert(mature_a != nullptr);
    assert(
        mature_a->evidence_confidence >
        early_confidence);
    assert(
        mature_a->experience_adjustment >
        early_adjustment);

    // Strategy evidence must remain domain-specific.
    const auto geometry =
        learned.plan(
            {seq_a_new, seq_b_new},
            "geometry");

    const auto* geometry_a =
        find_signature(
            geometry,
            signature_a);
    assert(geometry_a != nullptr);
    assert(
        geometry_a->experience_adjustment ==
        0.0);
    assert(
        geometry_a->evidence_confidence ==
        0.0);

    // Two theorem-specific sequences with the same move signature collapse to
    // one strategy and retain the stronger exemplar.
    const auto seq_a_weaker =
        sequence(
            "seq-a-weaker",
            {
                route(
                    ProofRouteKind::RepresentationSwitch,
                    "switch-weak",
                    0.60),
                route(
                    ProofRouteKind::RecursiveDecomposition,
                    "decompose-weak",
                    0.61),
                route(
                    ProofRouteKind::IntensifyVerification,
                    "verify-weak",
                    0.62)
            },
            0.61);

    const auto collapsed =
        learned.plan(
            {seq_a_new, seq_a_weaker},
            "algebra");

    assert(collapsed.size() == 1);
    assert(
        collapsed.front().
            exemplar_sequence.sequence_id ==
        "seq-a-new-theorem");

    std::filesystem::remove(db);
    return 0;
}
