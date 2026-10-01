#include "expert_robot/research/strategy_planner.hpp"

#include "expert_robot/research/route_memory.hpp"
#include "expert_robot/sha256.hpp"

#include <algorithm>
#include <array>
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

std::string_view bucket(double value) {
    const double v = clamp01(value);
    if (v < 0.34) return "low";
    if (v < 0.67) return "mid";
    return "high";
}

std::string_view failure_bucket(long long failures) {
    if (failures <= 0) return "fresh";
    if (failures <= 3) return "some";
    return "stuck";
}

std::string_view dominant_need(
    const ResearchStrategyContext& c) {
    struct Need {
        std::string_view name;
        double value;
    };

    const std::array<Need, 5> needs{{
        {"decompose", c.decomposition_value},
        {"counterexample", c.counterexample_value},
        {"abstract", c.abstraction_value},
        {"compress", c.compression_value},
        {"reframe", c.representation_switch_value},
    }};

    const auto best =
        std::max_element(
            needs.begin(),
            needs.end(),
            [](const Need& a, const Need& b) {
                return a.value < b.value;
            });

    if (best == needs.end() ||
        best->value < 0.34) {
        return "general";
    }

    return best->name;
}

void validate_strategy_context(
    const ResearchStrategyContext& c) {
    if (c.domain.empty()) {
        throw std::invalid_argument(
            "strategy context domain must be non-empty");
    }
    if (c.consecutive_failures < 0) {
        throw std::invalid_argument(
            "strategy context consecutive_failures must be nonnegative");
    }

    for (const double value : {
             c.theorem_graph_coverage,
             c.uncertainty,
             c.route_repetition,
             c.decomposition_value,
             c.counterexample_value,
             c.abstraction_value,
             c.compression_value,
             c.representation_switch_value}) {
        if (!std::isfinite(value) ||
            value < 0.0 ||
            value > 1.0) {
            throw std::invalid_argument(
                "strategy context rates must be in [0,1]");
        }
    }
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
             c.context_experience_weight,
             c.step_experience_weight,
             c.max_abs_step_adjustment,
             c.exploration_weight,
             c.evidence_half_saturation_attempts,
             c.context_half_saturation_attempts,
             c.step_half_saturation_attempts,
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
        c.minimum_context_attempts < 0 ||
        c.minimum_step_attempts < 0 ||
        c.soft_retirement_min_attempts < 0) {
        throw std::invalid_argument(
            "strategy planner minimum experience must be nonnegative");
    }
    if (c.soft_retirement_verified_rate_ceiling > 1.0 ||
        c.soft_retirement_cost_floor > 1.0) {
        throw std::invalid_argument(
            "strategy retirement rate/cost thresholds must be within [0,1]");
    }
    if (c.evidence_half_saturation_attempts <= 0.0 ||
        c.context_half_saturation_attempts <= 0.0 ||
        c.step_half_saturation_attempts <= 0.0) {
        throw std::invalid_argument(
            "strategy evidence half-saturation values must be positive");
    }
    if (c.step_experience_weight > 0.10 ||
        c.max_abs_step_adjustment > 0.10) {
        throw std::invalid_argument(
            "step evidence influence must remain bounded at or below 0.10");
    }
}

std::string research_strategy_context_key(
    const ResearchStrategyContext& context) {
    validate_strategy_context(context);

    std::ostringstream out;
    out
        << "domain=" << context.domain
        << "|graph=" << bucket(context.theorem_graph_coverage)
        << "|uncertainty=" << bucket(context.uncertainty)
        << "|repetition=" << bucket(context.route_repetition)
        << "|failures=" << failure_bucket(context.consecutive_failures)
        << "|need=" << dominant_need(context);

    return out.str();
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
    std::string_view target_domain,
    const ResearchStrategyContext* context) const {
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
            .context_key = "",
            .context_evidence_confidence = 0.0,
            .context_adjustment = 0.0,
            .step_evidence_steps = 0U,
            .step_evidence_confidence = 0.0,
            .step_adjustment = 0.0,
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

        if (memory_ != nullptr &&
            context != nullptr) {
            validate_strategy_context(*context);

            strategy.context_key =
                research_strategy_context_key(
                    *context);

            const auto contextual =
                memory_->strategy_context_experience(
                    strategy.strategy_id,
                    strategy.context_key);

            if (contextual.attempts >=
                config_.minimum_context_attempts) {
                const double success_prior =
                    clamp01(
                        0.65 *
                            contextual.
                                smoothed_verified_rate() +
                        0.35 *
                            contextual.
                                smoothed_target_rate());

                const double normalized_cost =
                    clamp01(
                        contextual.
                            average_resource_cost());

                const double signed_success =
                    2.0 * success_prior - 1.0;

                strategy.context_evidence_confidence =
                    static_cast<double>(
                        contextual.attempts) /
                    (static_cast<double>(
                         contextual.attempts) +
                     config_.
                         context_half_saturation_attempts);

                strategy.context_adjustment =
                    config_.context_experience_weight *
                    strategy.context_evidence_confidence *
                    (signed_success -
                     0.25 * normalized_cost);
            }
        }

        if (memory_ != nullptr &&
            !target_domain.empty() &&
            !strategy.steps.empty()) {
            double confidence_sum = 0.0;
            double weighted_signal_sum = 0.0;
            std::size_t eligible_steps = 0U;

            for (std::size_t step_index = 0U;
                 step_index < strategy.steps.size();
                 ++step_index) {
                const auto step =
                    memory_->strategy_step_experience(
                        strategy.strategy_id,
                        step_index,
                        target_domain);

                if (step.attempts <
                    config_.minimum_step_attempts) {
                    continue;
                }

                // Strategy IDs should make this invariant true already, but
                // refuse mismatched historical rows rather than learning from
                // potentially stale/corrupt evidence.
                if (step.kind !=
                    strategy.steps[step_index]) {
                    continue;
                }

                const double success_prior =
                    clamp01(
                        0.65 *
                            step.smoothed_verified_rate() +
                        0.35 *
                            step.smoothed_target_rate());

                const double normalized_cost =
                    clamp01(
                        step.average_resource_cost());

                const double confidence =
                    static_cast<double>(
                        step.attempts) /
                    (static_cast<double>(
                         step.attempts) +
                     config_.
                         step_half_saturation_attempts);

                const double signed_success =
                    2.0 * success_prior - 1.0;

                const double signal =
                    signed_success -
                    0.25 * normalized_cost;

                confidence_sum += confidence;
                weighted_signal_sum +=
                    confidence * signal;
                ++eligible_steps;
            }

            if (eligible_steps > 0U &&
                confidence_sum > 0.0) {
                strategy.step_evidence_steps =
                    eligible_steps;
                strategy.step_evidence_confidence =
                    confidence_sum /
                    static_cast<double>(
                        eligible_steps);

                const double mean_signal =
                    weighted_signal_sum /
                    confidence_sum;

                const double raw_adjustment =
                    config_.step_experience_weight *
                    strategy.
                        step_evidence_confidence *
                    mean_signal;

                strategy.step_adjustment =
                    std::clamp(
                        raw_adjustment,
                        -config_.
                            max_abs_step_adjustment,
                        config_.
                            max_abs_step_adjustment);
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
                strategy.context_adjustment +
                strategy.step_adjustment +
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
