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
ResearchBenchmarkExecutor::training_service_for(
    const BenchmarkVariantProfile& variant) {
    if (frozen_variants_.contains(
            variant.variant_id)) {
        throw std::logic_error(
            "training case encountered after benchmark state was frozen");
    }

    const auto found =
        training_services_.find(
            variant.variant_id);
    if (found != training_services_.end()) {
        return *found->second;
    }

    auto service_config =
        config_.service;

    service_config.state_dir =
        config_.state_root /
        variant.variant_id /
        "train";

    service_config.theorem_graph_path =
        service_config.state_dir /
        "theorem_graph.json";

    service_config.research_engine.features =
        benchmark_feature_flags(
            variant);
    service_config.research_engine.learning_writes =
        true;

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

    training_services_.emplace(
        variant.variant_id,
        std::move(service));

    return *raw;
}

void ResearchBenchmarkExecutor::freeze_training_state(
    const BenchmarkVariantProfile& variant) {
    if (frozen_variants_.contains(
            variant.variant_id)) {
        return;
    }

    const auto found =
        training_services_.find(
            variant.variant_id);
    if (found ==
        training_services_.end()) {
        throw std::logic_error(
            "holdout evaluation requires completed training state");
    }

    // Close SQLite-backed stores before copying the training snapshot.
    training_services_.erase(found);

    const auto variant_root =
        config_.state_root /
        variant.variant_id;
    const auto train_dir =
        variant_root /
        "train";
    const auto frozen_dir =
        variant_root /
        "frozen_train";

    if (!std::filesystem::exists(
            train_dir)) {
        throw std::runtime_error(
            "training state directory is missing at freeze boundary");
    }

    std::filesystem::remove_all(
        frozen_dir);
    std::filesystem::copy(
        train_dir,
        frozen_dir,
        std::filesystem::copy_options::recursive |
            std::filesystem::copy_options::overwrite_existing);

    frozen_variants_.insert(
        variant.variant_id);
}

std::unique_ptr<app::MathResearchService>
ResearchBenchmarkExecutor::evaluation_service_for(
    const BenchmarkVariantProfile& variant,
    BenchmarkSplit split,
    long long case_index) {
    if (split == BenchmarkSplit::Train) {
        throw std::invalid_argument(
            "evaluation service cannot be created for training split");
    }

    freeze_training_state(
        variant);

    const auto variant_root =
        config_.state_root /
        variant.variant_id;
    const auto frozen_dir =
        variant_root /
        "frozen_train";
    const auto case_dir =
        variant_root /
        std::string(
            benchmark_split_name(
                split)) /
        ("case-" +
         std::to_string(case_index));

    std::filesystem::remove_all(
        case_dir);
    std::filesystem::create_directories(
        case_dir.parent_path());
    std::filesystem::copy(
        frozen_dir,
        case_dir,
        std::filesystem::copy_options::recursive |
            std::filesystem::copy_options::overwrite_existing);

    auto service_config =
        config_.service;
    service_config.state_dir =
        case_dir;
    service_config.theorem_graph_path =
        case_dir /
        "theorem_graph.json";
    service_config.research_engine.features =
        benchmark_feature_flags(
            variant);

    // Validation and holdout cases consume independent clones of the exact
    // same frozen training state. Neither evaluation split may feed results
    // back into proof/imagination/skill/theorem/route/strategy memory.
    service_config.research_engine.learning_writes =
        false;

    return std::make_unique<
        app::MathResearchService>(
            lean_runner_,
            freeform_math_backend_,
            lemma_json_backend_,
            formalization_json_backend_,
            service_config);
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
    switch (benchmark_case.split) {
        case BenchmarkSplit::Train:
            sensors.theorem_novelty = 0.40;
            break;
        case BenchmarkSplit::Validation:
            sensors.theorem_novelty = 0.65;
            break;
        case BenchmarkSplit::Holdout:
            sensors.theorem_novelty = 0.80;
            break;
    }
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
            benchmark_case.knowledge_mode ==
                    BenchmarkKnowledgeMode::KnownTheoremRetrieval
                ? benchmark_case.focus_theorem
                : std::string{},
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
    const long long index =
        ++case_counters_[
            variant.variant_id];

    std::unique_ptr<app::MathResearchService>
        evaluation_service;
    app::MathResearchService* service = nullptr;

    if (benchmark_case.split ==
        BenchmarkSplit::Train) {
        service =
            &training_service_for(
                variant);
    } else {
        evaluation_service =
            evaluation_service_for(
                variant,
                benchmark_case.split,
                index);
        service =
            evaluation_service.get();
    }

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
        service->run(
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
