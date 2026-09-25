#include "expert_robot/research/route_planner.hpp"

#include "expert_robot/sha256.hpp"
#include "expert_robot/research/route_memory.hpp"

#include <algorithm>
#include <cmath>
#include <deque>
#include <set>
#include <sstream>
#include <stdexcept>
#include <unordered_set>
#include <utility>

namespace expert_robot::research {
namespace {

double clamp01(double value) {
    return std::clamp(value, 0.0, 1.0);
}

double relation_strength(std::string_view relation) {
    if (relation == "IMPLIES" ||
        relation == "USES" ||
        relation == "REQUIRES") {
        return 1.0;
    }
    if (relation == "GENERALIZES" ||
        relation == "SPECIALIZES") {
        return 0.90;
    }
    if (relation == "GEOMETRIC_FORM_OF" ||
        relation == "ALGEBRAIC_FORM_OF") {
        return 0.85;
    }
    if (relation == "ANALOGOUS_TO") {
        return 0.65;
    }
    if (relation == "CONTRADICTS") {
        return 0.55;
    }
    return 0.50;
}

double path_diversity(
    const std::vector<std::string>& relations) {
    if (relations.empty()) return 0.0;

    std::set<std::string> unique(
        relations.begin(),
        relations.end());

    return clamp01(
        static_cast<double>(unique.size()) /
        static_cast<double>(relations.size()));
}

std::string route_id(
    ProofRouteKind kind,
    std::string_view payload) {
    return sha256_hex(
        std::string(proof_route_kind_name(kind)) +
        "\n" +
        std::string(payload));
}

bool better_route(
    const ProofRoute& a,
    const ProofRoute& b) {
    if (a.final_score != b.final_score) {
        return a.final_score > b.final_score;
    }
    if (a.evidence_score != b.evidence_score) {
        return a.evidence_score > b.evidence_score;
    }
    if (a.estimated_cost_score != b.estimated_cost_score) {
        return a.estimated_cost_score < b.estimated_cost_score;
    }
    return a.route_id < b.route_id;
}

} // namespace

void validate_route_planner_config(
    const RoutePlannerConfig& c) {
    if (c.max_graph_depth == 0U ||
        c.max_graph_routes == 0U ||
        c.max_output_routes == 0U) {
        throw std::invalid_argument(
            "route planner limits must be positive");
    }

    for (const double value : {
             c.evidence_weight,
             c.novelty_weight,
             c.information_gain_weight,
             c.expected_success_weight,
             c.diversity_weight,
             c.cost_penalty_weight,
             c.route_experience_weight}) {
        if (!std::isfinite(value) ||
            value < 0.0) {
            throw std::invalid_argument(
                "route planner weights must be finite and nonnegative");
        }
    }

    if (c.minimum_experience_attempts < 0) {
        throw std::invalid_argument(
            "minimum_experience_attempts must be nonnegative");
    }
}

std::string_view proof_route_kind_name(
    ProofRouteKind kind) {
    switch (kind) {
        case ProofRouteKind::ReuseVerifiedTheorem:
            return "reuse_verified_theorem";
        case ProofRouteKind::FollowTheoremPath:
            return "follow_theorem_path";
        case ProofRouteKind::RecursiveDecomposition:
            return "recursive_decomposition";
        case ProofRouteKind::RepresentationSwitch:
            return "representation_switch";
        case ProofRouteKind::CounterexampleSearch:
            return "counterexample_search";
        case ProofRouteKind::ImaginationCandidate:
            return "imagination_candidate";
        case ProofRouteKind::IntensifyVerification:
            return "intensify_verification";
    }
    return "unknown";
}

std::optional<cognition::CognitiveAction>
executable_action_for_route(
    ProofRouteKind kind) {
    using A = cognition::CognitiveAction;

    switch (kind) {
        case ProofRouteKind::RecursiveDecomposition:
            return A::DecomposeProblem;
        case ProofRouteKind::RepresentationSwitch:
            return A::SwitchRepresentation;
        case ProofRouteKind::CounterexampleSearch:
            return A::SeekCounterexample;
        case ProofRouteKind::ImaginationCandidate:
            return A::ExploreNovelRoute;
        case ProofRouteKind::IntensifyVerification:
            return A::IntensifyVerification;

        // The theorem-graph routes are informative but do not yet have a
        // dedicated Lean theorem-hint executor, so they must not control
        // dispatch yet.
        case ProofRouteKind::ReuseVerifiedTheorem:
        case ProofRouteKind::FollowTheoremPath:
            return std::nullopt;
    }
    return std::nullopt;
}

std::vector<std::string>
lean_hint_tactics_for_route(
    const ProofRoute& route) {
    if (route.kind !=
            ProofRouteKind::ReuseVerifiedTheorem ||
        route.theorem_path.size() < 2U) {
        return {};
    }

    const std::string& theorem =
        route.theorem_path.back();

    if (theorem.empty()) {
        return {};
    }

    return {
        "exact " + theorem,
        "simpa using " + theorem,
    };
}



ProofRoutePlanner::ProofRoutePlanner(
    const KnowledgeGraph& graph,
    RoutePlannerConfig config,
    const RouteOutcomeLedger* route_memory)
    : graph_(graph),
      config_(config),
      route_memory_(route_memory) {
    validate_route_planner_config(config_);
}

double ProofRoutePlanner::score_route(
    const ProofRoute& route) const {
    return clamp01(
        config_.evidence_weight *
            route.evidence_score +
        config_.novelty_weight *
            route.novelty_score +
        config_.information_gain_weight *
            route.information_gain_score +
        config_.expected_success_weight *
            route.expected_success_score +
        config_.diversity_weight *
            route.diversity_score -
        config_.cost_penalty_weight *
            route.estimated_cost_score);
}

std::vector<ProofRoute>
ProofRoutePlanner::graph_routes(
    const RoutePlanningRequest& request) const {
    if (request.target_name.empty()) {
        return {};
    }

    struct QueueNode {
        std::string theorem;
        std::vector<std::string> path;
        std::vector<std::string> relations;
        std::unordered_set<std::string> visited;
    };

    std::deque<QueueNode> queue;
    queue.push_back(
        QueueNode{
            .theorem = request.target_name,
            .path = {request.target_name},
            .relations = {},
            .visited = {request.target_name},
        });

    std::vector<ProofRoute> routes;

    while (!queue.empty() &&
           routes.size() < config_.max_graph_routes) {
        auto current =
            std::move(queue.front());
        queue.pop_front();

        if (current.path.size() >
            config_.max_graph_depth) {
            continue;
        }

        const auto edges =
            graph_.related(current.theorem);

        for (const auto& edge : edges) {
            const std::string next =
                edge.source == current.theorem
                    ? edge.target
                    : edge.source;

            if (current.visited.contains(next)) {
                continue;
            }

            QueueNode child = current;
            child.theorem = next;
            child.path.push_back(next);
            child.relations.push_back(edge.relation);
            child.visited.insert(next);

            try {
                const auto& node =
                    graph_.get(next);

                const bool verified =
                    node.status == "verified";

                const double relation_score =
                    relation_strength(edge.relation);
                const double distance_penalty =
                    clamp01(
                        static_cast<double>(
                            child.path.size() - 1U) /
                        static_cast<double>(
                            config_.max_graph_depth));

                std::ostringstream description;
                description
                    << "Follow verified theorem structure from "
                    << request.target_name
                    << " to "
                    << next
                    << " through "
                    << child.path.size() - 1U
                    << " graph hop(s).";

                ProofRoute route{
                    .kind = verified
                        ? ProofRouteKind::ReuseVerifiedTheorem
                        : ProofRouteKind::FollowTheoremPath,
                    .route_id = {},
                    .description = description.str(),
                    .theorem_path = child.path,
                    .supporting_relations =
                        child.relations,
                    .evidence_score =
                        clamp01(
                            (verified ? 0.90 : 0.55) *
                            relation_score),
                    .novelty_score =
                        clamp01(
                            0.30 +
                            0.55 * distance_penalty),
                    .information_gain_score =
                        clamp01(
                            0.45 +
                            0.35 *
                            path_diversity(
                                child.relations)),
                    .expected_success_score =
                        clamp01(
                            0.50 +
                            (verified ? 0.30 : 0.05) -
                            0.15 * distance_penalty),
                    .estimated_cost_score =
                        clamp01(
                            0.10 +
                            0.18 *
                            static_cast<double>(
                                child.path.size() - 1U)),
                    .diversity_score =
                        path_diversity(
                            child.relations),
                    .final_score = 0.0,
                    .requires_model = false,
                    .requires_lean = true,
                };

                std::ostringstream payload;
                for (const auto& item : child.path) {
                    payload << item << "\n";
                }
                for (const auto& relation :
                     child.relations) {
                    payload << relation << "\n";
                }

                route.route_id =
                    route_id(
                        route.kind,
                        payload.str());
                route.final_score =
                    score_route(route);

                routes.push_back(
                    std::move(route));
            } catch (const std::out_of_range&) {
                // Graph edges referencing absent nodes cannot become routes.
            }

            if (child.path.size() - 1U <
                config_.max_graph_depth) {
                queue.push_back(
                    std::move(child));
            }

            if (routes.size() >=
                config_.max_graph_routes) {
                break;
            }
        }
    }

    return routes;
}

std::vector<ProofRoute>
ProofRoutePlanner::policy_routes(
    const RoutePlanningRequest& request) const {
    using A = cognition::CognitiveAction;

    std::vector<ProofRoute> routes;

    auto add = [&](ProofRoute route) {
        route.route_id =
            route_id(
                route.kind,
                route.description);
        route.final_score =
            score_route(route);
        routes.push_back(
            std::move(route));
    };

    if (request.cognitive_action ==
            A::DecomposeProblem ||
        request.logic.decomposition_value >
            0.55) {
        add(
            ProofRoute{
                .kind =
                    ProofRouteKind::RecursiveDecomposition,
                .route_id = "",
                .description =
                    "Decompose the target into smaller Lean-verifiable helper lemmas and retry the parent.",
                .theorem_path = {},
                .supporting_relations = {},
                .evidence_score = 0.65,
                .novelty_score = 0.35,
                .information_gain_score =
                    clamp01(
                        0.55 +
                        0.35 *
                        request.logic.decomposition_value),
                .expected_success_score =
                    clamp01(
                        0.45 +
                        0.40 *
                        request.logic.decomposition_value),
                .estimated_cost_score = 0.55,
                .diversity_score = 0.45,
                .requires_model = true,
                .requires_lean = true,
            });
    }

    if (request.cognitive_action ==
            A::SwitchRepresentation ||
        request.logic.representation_switch_value >
            0.55) {
        add(
            ProofRoute{
                .kind =
                    ProofRouteKind::RepresentationSwitch,
                .route_id = "",
                .description =
                    "Translate the target into a different mathematical representation and search for a simpler invariant.",
                .theorem_path = {},
                .supporting_relations = {},
                .evidence_score = 0.45,
                .novelty_score = 0.80,
                .information_gain_score =
                    clamp01(
                        0.60 +
                        0.30 *
                        request.logic.representation_switch_value),
                .expected_success_score =
                    clamp01(
                        0.35 +
                        0.35 *
                        request.logic.representation_switch_value),
                .estimated_cost_score = 0.45,
                .diversity_score = 0.85,
                .requires_model = true,
                .requires_lean = true,
            });
    }

    if (request.cognitive_action ==
            A::SeekCounterexample ||
        request.logic.counterexample_value >
            0.55 ||
        request.logic.contradiction_risk >
            0.65) {
        add(
            ProofRoute{
                .kind =
                    ProofRouteKind::CounterexampleSearch,
                .route_id = "",
                .description =
                    "Try to falsify the target or isolate missing hypotheses before spending more proof compute.",
                .theorem_path = {},
                .supporting_relations = {},
                .evidence_score =
                    clamp01(
                        0.45 +
                        0.35 *
                        request.logic.contradiction_risk),
                .novelty_score = 0.55,
                .information_gain_score =
                    clamp01(
                        0.65 +
                        0.25 *
                        request.logic.counterexample_value),
                .expected_success_score =
                    clamp01(
                        0.35 +
                        0.40 *
                        request.logic.counterexample_value),
                .estimated_cost_score = 0.30,
                .diversity_score = 0.70,
                .requires_model = true,
                .requires_lean = false,
            });
    }

    if (request.cognitive_action ==
            A::IntensifyVerification ||
        request.logic.evidence_strength < 0.35) {
        add(
            ProofRoute{
                .kind =
                    ProofRouteKind::IntensifyVerification,
                .route_id = "",
                .description =
                    "Spend compute on direct formal checking, assumption auditing, and proof replay before branching further.",
                .theorem_path = {},
                .supporting_relations = {},
                .evidence_score =
                    clamp01(
                        0.60 +
                        0.30 *
                        request.logic.contradiction_risk),
                .novelty_score = 0.10,
                .information_gain_score = 0.45,
                .expected_success_score =
                    clamp01(
                        0.45 +
                        0.30 *
                        request.logic.evidence_strength),
                .estimated_cost_score = 0.25,
                .diversity_score = 0.20,
                .requires_model = false,
                .requires_lean = true,
            });
    }

    return routes;
}

std::vector<ProofRoute>
ProofRoutePlanner::imagination_routes(
    const RoutePlanningRequest& request) const {
    if (request.imagination == nullptr) {
        return {};
    }

    std::vector<ProofRoute> routes;

    const auto& shortlisted =
        request.imagination->shortlisted;

    const std::size_t limit =
        std::min(
            config_.max_imagination_routes,
            shortlisted.size());

    for (std::size_t i = 0; i < limit; ++i) {
        const auto& idea =
            shortlisted[i];

        ProofRoute route{
            .kind =
                ProofRouteKind::ImaginationCandidate,
            .route_id = {},
            .description = idea.text,
            .theorem_path = {},
            .supporting_relations = {},
            .evidence_score =
                clamp01(
                    1.0 -
                    static_cast<double>(
                        idea.skeptic_risk) /
                        100.0),
            .novelty_score =
                idea.novelty_score,
            .information_gain_score =
                clamp01(
                    0.50 +
                    0.45 *
                    idea.quality_diversity_score),
            .expected_success_score =
                clamp01(
                    0.25 +
                    0.40 *
                    (1.0 -
                     static_cast<double>(
                         idea.skeptic_risk) /
                         100.0)),
            .estimated_cost_score = 0.60,
            .diversity_score =
                idea.quality_diversity_score,
            .final_score = 0.0,
            .requires_model = true,
            .requires_lean = true,
        };

        route.route_id =
            route_id(
                route.kind,
                idea.idea_id);
        route.final_score =
            score_route(route);
        routes.push_back(
            std::move(route));
    }

    return routes;
}

std::vector<ProofRoute>
ProofRoutePlanner::plan(
    const RoutePlanningRequest& request) const {
    cognition::validate_logical_assessment(
        request.logic);

    std::vector<ProofRoute> routes;

    auto append = [&](std::vector<ProofRoute> more) {
        routes.insert(
            routes.end(),
            std::make_move_iterator(more.begin()),
            std::make_move_iterator(more.end()));
    };

    append(graph_routes(request));
    append(policy_routes(request));
    append(imagination_routes(request));

    std::unordered_set<std::string> seen;
    std::vector<ProofRoute> unique;
    unique.reserve(routes.size());

    for (auto& route : routes) {
        if (seen.insert(route.route_id).second) {
            unique.push_back(
                std::move(route));
        }
    }

    for (auto& route : unique) {
        double score = score_route(route);

        if (route_memory_ != nullptr &&
            !request.target_domain.empty()) {
            const auto experience =
                route_memory_->experience(
                    route.kind,
                    request.target_domain);

            if (experience.attempts >=
                config_.minimum_experience_attempts) {
                const double success_prior =
                    clamp01(
                        0.65 *
                            experience.
                                smoothed_verified_rate() +
                        0.35 *
                            experience.
                                smoothed_target_rate());

                const double normalized_cost =
                    clamp01(
                        experience.
                            average_resource_cost());

                const double signed_success =
                    2.0 * success_prior - 1.0;

                const double adjustment =
                    config_.route_experience_weight *
                    (signed_success -
                     0.25 * normalized_cost);

                score =
                    clamp01(
                        score + adjustment);
            }
        }

        route.final_score = score;
    }

    std::stable_sort(
        unique.begin(),
        unique.end(),
        better_route);

    if (unique.size() >
        config_.max_output_routes) {
        unique.resize(
            config_.max_output_routes);
    }

    return unique;
}

} // namespace expert_robot::research
