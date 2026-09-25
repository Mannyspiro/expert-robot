#include "expert_robot/research/route_memory.hpp"
#include "expert_robot/research/route_planner.hpp"

#include <cassert>
#include <filesystem>
#include <stdexcept>

namespace {

const expert_robot::research::ProofRoute* find_kind(
    const std::vector<expert_robot::research::ProofRoute>& routes,
    expert_robot::research::ProofRouteKind kind) {
    for (const auto& route : routes) {
        if (route.kind == kind) {
            return &route;
        }
    }
    return nullptr;
}

} // namespace

int main() {
    using namespace expert_robot;
    using namespace expert_robot::research;
    using namespace expert_robot::cognition;

    const auto db =
        std::filesystem::temp_directory_path() /
        "expert-robot-route-memory.sqlite3";
    std::filesystem::remove(db);

    RouteOutcomeLedger memory(db);

    for (int i = 0; i < 4; ++i) {
        memory.record(
            RouteOutcome{
                .route_id =
                    "decompose-" +
                    std::to_string(i),
                .kind =
                    ProofRouteKind::RecursiveDecomposition,
                .domain = "algebra",
                .verified_progress = true,
                .target_verified = true,
                .dead_end_escaped = true,
                .resource_cost = 0.20
            });

        memory.record(
            RouteOutcome{
                .route_id =
                    "switch-" +
                    std::to_string(i),
                .kind =
                    ProofRouteKind::RepresentationSwitch,
                .domain = "algebra",
                .verified_progress = false,
                .target_verified = false,
                .dead_end_escaped = false,
                .resource_cost = 0.80
            });
    }

    const auto decomp_exp =
        memory.experience(
            ProofRouteKind::RecursiveDecomposition,
            "algebra");
    const auto switch_exp =
        memory.experience(
            ProofRouteKind::RepresentationSwitch,
            "algebra");

    assert(decomp_exp.attempts == 4);
    assert(decomp_exp.verified_progresses == 4);
    assert(decomp_exp.target_verifications == 4);
    assert(decomp_exp.dead_end_escapes == 4);
    assert(
        decomp_exp.smoothed_verified_rate() >
        switch_exp.smoothed_verified_rate());
    assert(
        decomp_exp.average_resource_cost() <
        switch_exp.average_resource_cost());

    KnowledgeGraph graph({
        {
            .name = "MathAI.Target",
            .source = "Target.lean",
            .status = "candidate",
            .statement = "target",
            .domain = "algebra",
            .tags = {"target"}
        }
    });

    LogicalAssessment logic;
    logic.evidence_strength = 0.4;
    logic.expected_success = 0.4;
    logic.expected_information_gain = 0.7;
    logic.contradiction_risk = 0.2;
    logic.decomposition_value = 0.8;
    logic.counterexample_value = 0.2;
    logic.abstraction_value = 0.5;
    logic.compression_value = 0.5;
    logic.representation_switch_value = 0.8;
    logic.current_route_progress = 0.1;
    logic.branch_cost = 0.3;

    RoutePlannerConfig config;
    config.minimum_experience_attempts = 3;
    config.route_experience_weight = 0.12;

    ProofRoutePlanner baseline_planner(
        graph,
        config,
        nullptr);

    ProofRoutePlanner learned_planner(
        graph,
        config,
        &memory);

    const RoutePlanningRequest request{
        .target_name = "MathAI.Target",
        .target_domain = "algebra",
        .cognitive_action =
            CognitiveAction::ExploreNovelRoute,
        .logic = logic,
        .imagination = nullptr
    };

    const auto baseline =
        baseline_planner.plan(request);
    const auto learned =
        learned_planner.plan(request);

    const auto* base_decomp =
        find_kind(
            baseline,
            ProofRouteKind::RecursiveDecomposition);
    const auto* learned_decomp =
        find_kind(
            learned,
            ProofRouteKind::RecursiveDecomposition);

    const auto* base_switch =
        find_kind(
            baseline,
            ProofRouteKind::RepresentationSwitch);
    const auto* learned_switch =
        find_kind(
            learned,
            ProofRouteKind::RepresentationSwitch);

    assert(base_decomp != nullptr);
    assert(learned_decomp != nullptr);
    assert(base_switch != nullptr);
    assert(learned_switch != nullptr);

    assert(
        learned_decomp->final_score >
        base_decomp->final_score);
    assert(
        learned_switch->final_score <
        base_switch->final_score);

    // A different mathematical domain has no experience and therefore retains
    // the original route scores.
    auto geometry_request = request;
    geometry_request.target_domain = "geometry";

    const auto geometry =
        learned_planner.plan(
            geometry_request);

    const auto* geometry_decomp =
        find_kind(
            geometry,
            ProofRouteKind::RecursiveDecomposition);

    assert(geometry_decomp != nullptr);
    assert(
        geometry_decomp->final_score ==
        base_decomp->final_score);

    bool invalid_rejected = false;
    try {
        memory.record(
            RouteOutcome{
                .route_id = "bad",
                .kind =
                    ProofRouteKind::CounterexampleSearch,
                .domain = "algebra",
                .resource_cost = -1.0
            });
    } catch (const std::invalid_argument&) {
        invalid_rejected = true;
    }
    assert(invalid_rejected);

    std::filesystem::remove(db);
    return 0;
}
