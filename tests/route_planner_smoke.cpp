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
        },
        {
            .name = "MathAI.Counter",
            .source = "Counter.lean",
            .status = "verified",
            .statement = "verified contradictory fact",
            .domain = "analysis",
            .tags = {"lean_verified"}
        },
        {
            .name = "MathAI.Analogy",
            .source = "Analogy.lean",
            .status = "verified",
            .statement = "verified analogous theorem",
            .domain = "topology",
            .tags = {"lean_verified"}
        },
        {
            .name = "MathAI.Dependent",
            .source = "Dependent.lean",
            .status = "verified",
            .statement = "verified theorem that depends on the target",
            .domain = "analysis",
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
    graph.add_edge({
        .source = "MathAI.Target",
        .relation = "CONTRADICTS",
        .target = "MathAI.Counter"
    });
    graph.add_edge({
        .source = "MathAI.Target",
        .relation = "ANALOGOUS_TO",
        .target = "MathAI.Analogy"
    });
    graph.add_edge({
        .source = "MathAI.Dependent",
        .relation = "USES",
        .target = "MathAI.Target"
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
    assert(has_kind(
        ProofRouteKind::CounterexampleSearch));

    const auto analogy_route =
        std::find_if(
            routes.begin(),
            routes.end(),
            [](const ProofRoute& route) {
                return
                    !route.theorem_path.empty() &&
                    route.theorem_path.back() ==
                        "MathAI.Analogy";
            });
    assert(analogy_route != routes.end());
    assert(
        analogy_route->kind ==
        ProofRouteKind::FollowTheoremPath);
    assert(
        lean_hint_tactics_for_route(
            *analogy_route).empty());

    // A verified theorem that depends on the current target cannot be used in
    // reverse as proof evidence for that target.
    const auto reverse_dependency =
        std::find_if(
            routes.begin(),
            routes.end(),
            [](const ProofRoute& route) {
                return
                    !route.theorem_path.empty() &&
                    route.theorem_path.back() ==
                        "MathAI.Dependent";
            });
    assert(reverse_dependency == routes.end());

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

    const auto sequences =
        planner.compose(routes);

    assert(!sequences.empty());
    assert(sequences.size() <= 6);

    bool saw_switch_then_decompose = false;
    for (const auto& sequence : sequences) {
        assert(!sequence.sequence_id.empty());
        assert(!sequence.steps.empty());
        assert(sequence.steps.size() <= 3);
        assert(sequence.average_route_score >= 0.0);
        assert(sequence.average_route_score <= 1.0);
        assert(sequence.synergy_score >= 0.0);
        assert(sequence.synergy_score <= 1.0);
        assert(sequence.final_score >= 0.0);
        assert(sequence.final_score <= 1.0);

        if (sequence.steps.size() >= 2 &&
            sequence.steps[0].kind ==
                ProofRouteKind::RepresentationSwitch &&
            sequence.steps[1].kind ==
                ProofRouteKind::RecursiveDecomposition) {
            saw_switch_then_decompose = true;
            assert(sequence.synergy_score > 0.0);
        }
    }

    assert(saw_switch_then_decompose);

    for (std::size_t i = 1; i < sequences.size(); ++i) {
        assert(
            sequences[i - 1].final_score >=
            sequences[i].final_score);
    }

    const auto sequences_again =
        planner.compose(routes);
    assert(
        sequences.front().sequence_id ==
        sequences_again.front().sequence_id);

    KnowledgeGraph formal_graph;
    formal_graph.sync_formal_registry(
        "formal/theorem_registry.json");

    ProofRoutePlanner formal_planner(
        formal_graph,
        RoutePlannerConfig{
            .max_graph_depth = 2,
            .max_graph_routes = 8,
            .max_imagination_routes = 1,
            .max_output_routes = 8
        });

    LogicalAssessment formal_logic;
    formal_logic.evidence_strength = 0.8;
    formal_logic.expected_success = 0.6;
    formal_logic.expected_information_gain = 0.4;
    formal_logic.contradiction_risk = 0.1;
    formal_logic.decomposition_value = 0.1;
    formal_logic.counterexample_value = 0.1;
    formal_logic.abstraction_value = 0.2;
    formal_logic.compression_value = 0.2;
    formal_logic.representation_switch_value = 0.1;
    formal_logic.current_route_progress = 0.2;
    formal_logic.branch_cost = 0.1;

    const auto formal_routes =
        formal_planner.plan(
            RoutePlanningRequest{
                .target_name =
                    "MathAI.Geometry.orthogonal_symm",
                .target_domain = "geometry",
                .cognitive_action =
                    CognitiveAction::ContinueCurrentRoute,
                .logic = formal_logic,
                .imagination = nullptr
            });

    const auto dependency_route =
        std::find_if(
            formal_routes.begin(),
            formal_routes.end(),
            [](const ProofRoute& route) {
                return
                    route.kind ==
                        ProofRouteKind::ReuseVerifiedTheorem &&
                    route.theorem_path.size() == 2 &&
                    route.theorem_path.back() ==
                        "MathAI.Geometry.dot_comm";
            });

    assert(
        dependency_route !=
        formal_routes.end());

    const auto dependency_hints =
        lean_hint_tactics_for_route(
            *dependency_route);

    assert(dependency_hints.size() == 3);
    assert(
        dependency_hints.front() ==
        "simp [MathAI.Geometry.dot_comm]");

    assert(
        proof_route_kind_name(
            ProofRouteKind::FollowTheoremPath) ==
        "follow_theorem_path");

    return 0;
}
