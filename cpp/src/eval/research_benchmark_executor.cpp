#include "expert_robot/eval/research_benchmark_executor.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <set>
#include <stdexcept>
#include <utility>

namespace expert_robot::eval {
namespace {

bool has(
    const BenchmarkVariantProfile& variant,
    std::string_view layer) {
    return variant.has_layer(layer);
}

void validate_layer_dependencies(
    const BenchmarkVariantProfile& variant) {
    if (!has(variant, "proof_search")) {
        throw std::invalid_argument(
            "benchmark variant must include proof_search");
    }

    if (has(variant, "route_memory") &&
        !has(variant, "theorem_graph")) {
        throw std::invalid_argument(
            "route_memory benchmark layer requires theorem_graph");
    }

    if (has(variant, "sequence_memory") &&
        !has(variant, "route_memory")) {
        throw std::invalid_argument(
            "sequence_memory benchmark layer requires route_memory");
    }

    if (has(variant, "strategy_memory") &&
        !has(variant, "sequence_memory")) {
        throw std::invalid_argument(
            "strategy_memory benchmark layer requires sequence_memory");
    }

    if (has(variant, "imagination") !=
        has(variant, "decomposition")) {
        throw std::invalid_argument(
            "benchmark imagination/decomposition layers must be paired");
    }
}

double normalized_resource_cost(
    const research::ResearchUsage& usage,
    const research::ResearchBudget& budget) {
    const auto ratio = [](
        std::size_t used,
        std::size_t maximum) {
        if (maximum == 0U) return 1.0;
        return std::min(
            1.0,
            static_cast<double>(used) /
                static_cast<double>(maximum));
    };

    return 0.25 * (
        ratio(
            usage.model_calls,
            budget.max_model_calls) +
        ratio(
            usage.proof_attempts,
            budget.max_proof_attempts) +
        ratio(
            usage.generated_ideas,
            budget.max_generated_ideas) +
        ratio(
            usage.generated_lemmas,
            budget.max_generated_lemmas));
}

long long duplicate_ideas(
    const research::ResearchOutcome& outcome) {
    if (!outcome.last_imagination) {
        return 0;
    }

    std::set<std::string> ids;
    long long duplicates = 0;

    for (const auto& idea :
         outcome.last_imagination->generated) {
        if (!ids.insert(
                idea.idea_id).second) {
            ++duplicates;
        }
    }

    return duplicates;
}

bool escaped_dead_end(
    const research::ResearchOutcome& outcome) {
    if (!outcome.target_verified) {
        return false;
    }

    return std::any_of(
        outcome.final_state.history.begin(),
        outcome.final_state.history.end(),
        [](const research::ResearchTransition& transition) {
            return
                transition.from ==
                    research::ResearchPhase::DirectProof &&
                transition.to !=
                    research::ResearchPhase::Consolidate;
        });
}

} // namespace

research::ResearchFeatureFlags
benchmark_feature_flags(
    const BenchmarkVariantProfile& variant) {
    validate_layer_dependencies(variant);

    const bool theorem_graph =
        has(variant, "theorem_graph");
    const bool route_memory =
        has(variant, "route_memory");
    const bool sequence_memory =
        has(variant, "sequence_memory");
    const bool strategy_memory =
        has(variant, "strategy_memory");
    const bool adaptive =
        has(variant, "imagination");

    return research::ResearchFeatureFlags{
        .theorem_graph =
            theorem_graph,
        .route_planning =
            theorem_graph,
        .imagination =
            adaptive,
        .decomposition =
            adaptive,
        .route_memory =
            route_memory,
        .sequence_memory =
            sequence_memory,
        .strategy_planning =
            strategy_memory,
        .strategy_memory =
            strategy_memory,
    };
}

ResearchBenchmarkExecutor::ResearchBenchmarkExecutor(
    ILeanRunner& lean_runner,
    ITextGenerationBackend& freeform_math_backend,
    ITextGenerationBackend& lemma_json_backend,
    ITextGenerationBackend& formalization_json_backend,
    ResearchBenchmarkExecutorConfig config)
    : lean_runner_(lean_runner),
      freeform_math_backend_(
          freeform_math_backend),
      lemma_json_backend_(
          lemma_json_backend),
      formalization_json_backend_(
          formalization_json_backend),
      config_(std::move(config)) {
    if (config_.state_root.empty()) {
        throw std::invalid_argument(
            "research benchmark state_root must be non-empty");
    }

    if (config_.reset_state_root) {
        std::filesystem::remove_all(
            config_.state_root);
    }

    std::filesystem::create_directories(
        config_.state_root);
}

app::MathResearchService&
ResearchBenchmarkExecutor::service_for(
    const BenchmarkVariantProfile& variant) {
    const auto found =
        services_.find(
            variant.variant_id);
    if (found != services_.end()) {
        return *found->second;
    }

    auto service_config =
        config_.service;

    service_config.state_dir =
        config_.state_root /
        variant.variant_id;

    service_config.theorem_graph_path =
        service_config.state_dir /
        "theorem_graph.json";

    service_config.research_engine.features =
        benchmark_feature_flags(
            variant);

    auto service =
        std::make_unique<
            app::MathResearchService>(
                lean_runner_,
                freeform_math_backend_,
                lemma_json_backend_,
                formalization_json_backend_,
                service_config);

    auto* raw =
        service.get();

    services_.emplace(
        variant.variant_id,
        std::move(service));

    return *raw;
}

research::ResearchProblem
ResearchBenchmarkExecutor::problem_for(
    const BenchmarkCase& benchmark_case,
    std::string episode_id) const {
    std::vector<Binder> binders;
    binders.reserve(
        benchmark_case.binders.size());

    for (const auto& binder :
         benchmark_case.binders) {
        binders.push_back(
            Binder{
                .name = binder.name,
                .type = binder.type,
            });
    }

    FormalizationProposal target{
        .name =
            benchmark_case.declaration_name,
        .name_space =
            benchmark_case.name_space,
        .binders =
            std::move(binders),
        .proposition =
            benchmark_case.proposition,
        .imports =
            benchmark_case.imports,
        .domain =
            benchmark_case.domain,
        .rationale =
            "paired train/holdout benchmark case " +
            benchmark_case.case_id,
    };

    cognition::InteroceptiveSensors sensors;
    sensors.cpu_load = 0.10;
    sensors.gpu_load = 0.10;
    sensors.ram_pressure = 0.10;
    sensors.vram_pressure = 0.10;
    sensors.context_utilization = 0.10;
    sensors.work_queue_pressure = 0.10;
    sensors.recent_proof_success_rate = 0.0;
    sensors.verified_progress = 0.0;
    sensors.expected_verified_progress = 0.50;
    sensors.theorem_novelty =
        benchmark_case.split ==
                BenchmarkSplit::Holdout
            ? 0.80
            : 0.40;
    sensors.theorem_graph_coverage = 0.50;
    sensors.route_repetition = 0.0;
    sensors.uncertainty = 0.35;
    sensors.contradiction_rate = 0.0;
    sensors.goal_persistence = 0.80;

    cognition::LogicalAssessment logic;
    logic.evidence_strength = 0.60;
    logic.expected_success = 0.55;
    logic.expected_information_gain = 0.45;
    logic.contradiction_risk = 0.05;
    logic.decomposition_value = 0.50;
    logic.counterexample_value = 0.20;
    logic.abstraction_value = 0.35;
    logic.compression_value = 0.45;
    logic.representation_switch_value = 0.35;
    logic.current_route_progress = 0.0;
    logic.branch_cost = 0.25;

    return research::ResearchProblem{
        .episode_id =
            std::move(episode_id),
        .target =
            std::move(target),
        .focus_theorem =
            benchmark_case.focus_theorem,
        .context = {},
        .sensors =
            sensors,
        .logic =
            logic,
        .evaluation_mode = true,
        .experimental_skills = {},
    };
}

BenchmarkCaseResult
ResearchBenchmarkExecutor::run(
    const BenchmarkVariantProfile& variant,
    const BenchmarkCase& benchmark_case) {
    auto& service =
        service_for(variant);

    const long long index =
        ++case_counters_[
            variant.variant_id];

    const std::string episode_id =
        "benchmark:" +
        variant.variant_id +
        ":" +
        benchmark_case.case_id +
        ":" +
        std::to_string(index);

    const auto started =
        std::chrono::steady_clock::now();

    const auto outcome =
        service.run(
            problem_for(
                benchmark_case,
                episode_id));

    const auto elapsed =
        std::chrono::duration_cast<
            std::chrono::milliseconds>(
                std::chrono::steady_clock::now() -
                started);

    const auto& usage =
        outcome.final_state.usage;
    const auto& budget =
        config_.service.
            research_engine.budget;

    return BenchmarkCaseResult{
        .verified =
            outcome.target_verified,
        .dead_end_escaped =
            escaped_dead_end(
                outcome),
        .wall_time_ms =
            elapsed.count(),
        .model_calls =
            static_cast<long long>(
                usage.model_calls),
        .proof_attempts =
            static_cast<long long>(
                usage.proof_attempts),
        .lemmas_generated =
            static_cast<long long>(
                usage.generated_lemmas),
        .ideas_generated =
            static_cast<long long>(
                usage.generated_ideas),
        .duplicate_candidates =
            duplicate_ideas(
                outcome),
        .resource_cost =
            normalized_resource_cost(
                usage,
                budget),
    };
}

} // namespace expert_robot::eval
