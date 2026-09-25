#include "expert_robot/research/strategy_planner.hpp"

#include "expert_robot/research/route_memory.hpp"
#include "expert_robot/sha256.hpp"

#include <algorithm>
#include <cmath>
#include <initializer_list>
#include <map>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace expert_robot::research {
namespace {

double clamp01(double value) {
    return std::clamp(value, 0.0, 1.0);
}

bool same_steps(
    const std::vector<ProofRouteKind>& a,
    std::initializer_list<ProofRouteKind> b) {
    return a.size() == b.size() &&
           std::equal(
               a.begin(),
               a.end(),
               b.begin(),
               b.end());
}

bool better_strategy(
    const ResearchStrategyPlan& a,
    const ResearchStrategyPlan& b) {
    if (a.final_score != b.final_score) {
        return a.final_score > b.final_score;
    }
    if (a.base_score != b.base_score) {
        return a.base_score > b.base_score;
    }
    return a.strategy_id < b.strategy_id;
}

} // namespace

void validate_research_strategy_planner_config(
    const ResearchStrategyPlannerConfig& c) {
    if (c.max_output_strategies == 0U) {
        throw std::invalid_argument(
            "strategy planner output limit must be positive");
    }

    for (const double value : {
             c.experience_weight,
             c.exploration_weight,
             c.evidence_half_saturation_attempts,
             c.soft_retirement_verified_rate_ceiling,
             c.soft_retirement_cost_floor,
             c.soft_retirement_penalty}) {
        if (!std::isfinite(value) ||
            value < 0.0) {
            throw std::invalid_argument(
                "strategy planner weights must be finite and nonnegative");
        }
    }

    if (c.minimum_experience_attempts < 0 ||
        c.soft_retirement_min_attempts < 0) {
        throw std::invalid_argument(
            "strategy planner minimum experience must be nonnegative");
    }
    if (c.soft_retirement_verified_rate_ceiling > 1.0 ||
        c.soft_retirement_cost_floor > 1.0) {
        throw std::invalid_argument(
            "strategy retirement rate/cost thresholds must be within [0,1]");
    }
    if (c.evidence_half_saturation_attempts <= 0.0) {
        throw std::invalid_argument(
            "strategy evidence half-saturation must be positive");
    }
}

std::string research_strategy_signature(
    const std::vector<ProofRouteKind>& steps) {
    if (steps.empty()) {
        throw std::invalid_argument(
            "research strategy requires at least one route step");
    }

    std::ostringstream out;
    for (std::size_t i = 0U;
         i < steps.size();
         ++i) {
        if (i > 0U) {
            out << " -> ";
        }
        out << proof_route_kind_name(
            steps[i]);
    }
    return out.str();
}

std::string research_strategy_signature(
    const ProofRouteSequence& sequence) {
    std::vector<ProofRouteKind> steps;
    steps.reserve(sequence.steps.size());
    for (const auto& route : sequence.steps) {
        steps.push_back(route.kind);
    }
    return research_strategy_signature(steps);
}

std::string research_strategy_id(
    std::string_view signature) {
    if (signature.empty()) {
        throw std::invalid_argument(
            "research strategy signature must be non-empty");
    }

    return sha256_hex(
        "research_strategy\n" +
        std::string(signature));
}

std::string research_strategy_title(
    const std::vector<ProofRouteKind>& steps) {
    using K = ProofRouteKind;

    if (same_steps(
            steps,
            {K::CounterexampleSearch,
             K::RepresentationSwitch,
             K::RecursiveDecomposition})) {
        return "Falsify, reframe, decompose";
    }

    if (same_steps(
            steps,
            {K::RepresentationSwitch,
             K::RecursiveDecomposition,
             K::IntensifyVerification})) {
        return "Reframe, decompose, verify";
    }

    if (same_steps(
            steps,
            {K::RepresentationSwitch,
             K::ImaginationCandidate,
             K::RecursiveDecomposition})) {
        return "Reframe, imagine, decompose";
    }

    if (same_steps(
            steps,
            {K::ImaginationCandidate,
             K::RecursiveDecomposition,
             K::IntensifyVerification})) {
        return "Imagine, decompose, verify";
    }

    if (same_steps(
            steps,
            {K::RecursiveDecomposition,
             K::IntensifyVerification})) {
        return "Decompose, verify";
    }

    if (same_steps(
            steps,
            {K::ReuseVerifiedTheorem,
             K::IntensifyVerification})) {
        return "Reuse verified knowledge, verify";
    }

    if (steps.size() == 1U) {
        return std::string(
            proof_route_kind_name(
                steps.front()));
    }

    std::ostringstream title;
    title << "Composed strategy: ";
    for (std::size_t i = 0U;
         i < steps.size();
         ++i) {
        if (i > 0U) title << " -> ";
        title << proof_route_kind_name(
            steps[i]);
    }
    return title.str();
}

ResearchStrategyPlanner::ResearchStrategyPlanner(
    ResearchStrategyPlannerConfig config,
    const RouteOutcomeLedger* memory)
    : config_(config),
      memory_(memory) {
    validate_research_strategy_planner_config(
        config_);
}

std::vector<ResearchStrategyPlan>
ResearchStrategyPlanner::plan(
    const std::vector<ProofRouteSequence>& sequences,
    std::string_view target_domain) const {
    std::map<std::string, ResearchStrategyPlan>
        collapsed;

    for (const auto& sequence : sequences) {
        if (sequence.steps.empty()) {
            continue;
        }

        const std::string signature =
            research_strategy_signature(
                sequence);
        const std::string id =
            research_strategy_id(
                signature);

        std::vector<ProofRouteKind> steps;
        steps.reserve(
            sequence.steps.size());
        for (const auto& route :
             sequence.steps) {
            steps.push_back(route.kind);
        }

        ResearchStrategyPlan candidate{
            .strategy_id = id,
            .signature = signature,
            .title =
                research_strategy_title(
                    steps),
            .steps = std::move(steps),
            .exemplar_sequence = sequence,
            .base_score =
                sequence.final_score,
            .evidence_confidence = 0.0,
            .experience_adjustment = 0.0,
            .soft_retired = false,
            .soft_retirement_penalty = 0.0,
            .exploration_bonus = 0.0,
            .final_score =
                sequence.final_score,
        };

        const auto existing =
            collapsed.find(id);
        if (existing == collapsed.end() ||
            candidate.base_score >
                existing->second.base_score) {
            collapsed[id] =
                std::move(candidate);
        }
    }

    std::vector<ResearchStrategyPlan> result;
    result.reserve(
        collapsed.size());

    for (auto& [id, strategy] :
         collapsed) {
        (void)id;

        long long attempts = 0;

        if (memory_ != nullptr &&
            !target_domain.empty()) {
            const auto experience =
                memory_->strategy_experience(
                    strategy.strategy_id,
                    target_domain);

            attempts =
                experience.attempts;

            if (experience.attempts >=
                config_.
                    minimum_experience_attempts) {
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

                strategy.evidence_confidence =
                    static_cast<double>(
                        experience.attempts) /
                    (static_cast<double>(
                         experience.attempts) +
                     config_.
                         evidence_half_saturation_attempts);

                strategy.experience_adjustment =
                    config_.experience_weight *
                    strategy.evidence_confidence *
                    (signed_success -
                     0.25 * normalized_cost);

                if (experience.attempts >=
                        config_.soft_retirement_min_attempts &&
                    experience.smoothed_verified_rate() <=
                        config_.
                            soft_retirement_verified_rate_ceiling &&
                    normalized_cost >=
                        config_.soft_retirement_cost_floor) {
                    strategy.soft_retired = true;
                    strategy.soft_retirement_penalty =
                        config_.soft_retirement_penalty *
                        strategy.evidence_confidence;
                }
            }
        }

        strategy.exploration_bonus =
            config_.exploration_weight /
            std::sqrt(
                static_cast<double>(
                    attempts + 1));

        strategy.final_score =
            clamp01(
                strategy.base_score +
                strategy.experience_adjustment +
                strategy.exploration_bonus -
                strategy.soft_retirement_penalty);

        result.push_back(
            std::move(strategy));
    }

    std::stable_sort(
        result.begin(),
        result.end(),
        better_strategy);

    if (result.size() >
        config_.max_output_strategies) {
        result.resize(
            config_.max_output_strategies);
    }

    return result;
}

} // namespace expert_robot::research
