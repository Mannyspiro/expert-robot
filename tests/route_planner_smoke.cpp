#include "expert_robot/research/route_planner.hpp"

#include <algorithm>
#include <cassert>
#include <string>

int main() {
    using namespace expert_robot;
    using namespace expert_robot::research;
    using namespace expert_robot::imagination;
    using namespace expert_robot::cognition;

    KnowledgeGraph graph({
        {
            .name = "MathAI.Target",
            .source = "Target.lean",
            .status = "candidate",
            .statement = "target",
            .domain = "analysis",
            .tags = {"target"}
        },
        {
            .name = "MathAI.Helper",
            .source = "Helper.lean",
            .status = "verified",
            .statement = "verified helper",
            .domain = "analysis",
            .tags = {"lean_verified"}
        },
        {
            .name = "MathAI.GeometryBridge",
            .source = "Bridge.lean",
            .status = "verified",
            .statement = "geometric bridge",
            .domain = "geometry",
            .tags = {"lean_verified"}
        }
    });

    graph.add_edge({
        .source = "MathAI.Target",
        .relation = "USES",
        .target = "MathAI.Helper"
    });
    graph.add_edge({
        .source = "MathAI.Helper",
        .relation = "GEOMETRIC_FORM_OF",
        .target = "MathAI.GeometryBridge"
    });

    IdeaCandidate idea{
        .idea_id = "idea-1",
        .lens = ImaginationLens::Geometry,
        .source_role = swarm::AgentRole::GeometrySpecialist,
        .text = "Recast the target as an exact geometric invariant.",
        .novelty_score = 0.90,
        .relevance_score = 0.80,
        .quality_diversity_score = 0.85,
        .skeptic_valid = true,
        .skeptic_keep = true,
        .skeptic_risk = 20,
        .skeptic_critique = "worth formal testing"
    };

    ImaginationRun imagination;
    imagination.imagination_drive = 0.8;
    imagination.shortlisted = {idea};

    LogicalAssessment logic;
    logic.evidence_strength = 0.30;
    logic.expected_success = 0.40;
    logic.expected_information_gain = 0.85;
    logic.contradiction_risk = 0.20;
    logic.decomposition_value = 0.75;
    logic.counterexample_value = 0.20;
    logic.abstraction_value = 0.70;
    logic.compression_value = 0.50;
    logic.representation_switch_value = 0.90;
    logic.current_route_progress = 0.10;
    logic.branch_cost = 0.30;

    ProofRoutePlanner planner(
        graph,
        RoutePlannerConfig{
            .max_graph_depth = 3,
            .max_graph_routes = 8,
            .max_imagination_routes = 2,
            .max_output_routes = 8
        });

    const auto routes = planner.plan(
        RoutePlanningRequest{
            .target_name = "MathAI.Target",
            .target_domain = "analysis",
            .cognitive_action =
                CognitiveAction::SwitchRepresentation,
            .logic = logic,
            .imagination = &imagination
        });

    assert(!routes.empty());
    assert(routes.size() <= 8);

    const auto has_kind =
        [&](ProofRouteKind kind) {
            return std::any_of(
                routes.begin(),
                routes.end(),
                [&](const ProofRoute& route) {
                    return route.kind == kind;
                });
        };

    assert(has_kind(
        ProofRouteKind::ReuseVerifiedTheorem));
    assert(has_kind(
        ProofRouteKind::RepresentationSwitch));
    assert(has_kind(
        ProofRouteKind::RecursiveDecomposition));
    assert(has_kind(
        ProofRouteKind::ImaginationCandidate));

    bool saw_multihop = false;
    for (const auto& route : routes) {
        assert(!route.route_id.empty());
        assert(!route.description.empty());
        assert(route.final_score >= 0.0);
        assert(route.final_score <= 1.0);
        assert(route.evidence_score >= 0.0);
        assert(route.evidence_score <= 1.0);
        assert(route.novelty_score >= 0.0);
        assert(route.novelty_score <= 1.0);

        if (route.theorem_path.size() >= 3) {
            saw_multihop = true;
        }
    }
    assert(saw_multihop);

    for (std::size_t i = 1; i < routes.size(); ++i) {
        assert(
            routes[i - 1].final_score >=
            routes[i].final_score);
    }

    assert(
        proof_route_kind_name(
            ProofRouteKind::FollowTheoremPath) ==
        "follow_theorem_path");

    return 0;
}
