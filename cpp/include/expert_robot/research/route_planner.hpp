#pragma once

#include "expert_robot/cognition/personality.hpp"
#include "expert_robot/imagination/controller.hpp"
#include "expert_robot/knowledge_graph.hpp"

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

namespace expert_robot::research {

class RouteOutcomeLedger;

enum class ProofRouteKind {
    ReuseVerifiedTheorem,
    FollowTheoremPath,
    RecursiveDecomposition,
    RepresentationSwitch,
    CounterexampleSearch,
    ImaginationCandidate,
    IntensifyVerification,
};

struct ProofRoute {
    ProofRouteKind kind{ProofRouteKind::ReuseVerifiedTheorem};
    std::string route_id;
    std::string description;

    std::vector<std::string> theorem_path;
    std::vector<std::string> supporting_relations;

    double evidence_score{0.0};
    double novelty_score{0.0};
    double information_gain_score{0.0};
    double expected_success_score{0.0};
    double estimated_cost_score{0.0};
    double diversity_score{0.0};
    double final_score{0.0};

    bool requires_model{false};
    bool requires_lean{true};
};

struct RoutePlannerConfig {
    std::size_t max_graph_depth{3};
    std::size_t max_graph_routes{12};
    std::size_t max_imagination_routes{3};
    std::size_t max_output_routes{8};

    double evidence_weight{0.24};
    double novelty_weight{0.16};
    double information_gain_weight{0.18};
    double expected_success_weight{0.24};
    double diversity_weight{0.10};
    double cost_penalty_weight{0.16};

    // Bounded empirical prior. It influences route ordering only after enough
    // domain-specific outcomes exist and can never exceed this contribution.
    double route_experience_weight{0.12};
    long long minimum_experience_attempts{3};
};

struct RoutePlanningRequest {
    std::string target_name;
    std::string target_domain;

    cognition::CognitiveAction cognitive_action{
        cognition::CognitiveAction::ContinueCurrentRoute};
    cognition::LogicalAssessment logic;

    const imagination::ImaginationRun* imagination{nullptr};
};

void validate_route_planner_config(const RoutePlannerConfig& config);

[[nodiscard]] std::string_view proof_route_kind_name(
    ProofRouteKind kind);

class ProofRoutePlanner {
public:
    ProofRoutePlanner(
        const KnowledgeGraph& graph,
        RoutePlannerConfig config = {},
        const RouteOutcomeLedger* route_memory = nullptr);

    [[nodiscard]] std::vector<ProofRoute> plan(
        const RoutePlanningRequest& request) const;

private:
    [[nodiscard]] std::vector<ProofRoute> graph_routes(
        const RoutePlanningRequest& request) const;

    [[nodiscard]] std::vector<ProofRoute> policy_routes(
        const RoutePlanningRequest& request) const;

    [[nodiscard]] std::vector<ProofRoute> imagination_routes(
        const RoutePlanningRequest& request) const;

    [[nodiscard]] double score_route(
        const ProofRoute& route) const;

    const KnowledgeGraph& graph_;
    RoutePlannerConfig config_;
    const RouteOutcomeLedger* route_memory_{nullptr};
};

} // namespace expert_robot::research
