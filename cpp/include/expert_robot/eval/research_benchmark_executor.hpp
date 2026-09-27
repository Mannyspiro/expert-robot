#pragma once

#include "expert_robot/app/math_research_service.hpp"
#include "expert_robot/eval/math_benchmark.hpp"

#include <filesystem>
#include <memory>
#include <string>
#include <unordered_map>
#include <unordered_set>

namespace expert_robot::eval {

[[nodiscard]] research::ResearchFeatureFlags
benchmark_feature_flags(
    const BenchmarkVariantProfile& variant);

struct ResearchBenchmarkExecutorConfig {
    std::filesystem::path state_root;
    app::MathResearchServiceConfig service;
    bool reset_state_root{true};
};

class ResearchBenchmarkExecutor final
    : public IMathBenchmarkExecutor {
public:
    ResearchBenchmarkExecutor(
        ILeanRunner& lean_runner,
        ITextGenerationBackend& freeform_math_backend,
        ITextGenerationBackend& lemma_json_backend,
        ITextGenerationBackend& formalization_json_backend,
        ResearchBenchmarkExecutorConfig config);

    [[nodiscard]] BenchmarkCaseResult run(
        const BenchmarkVariantProfile& variant,
        const BenchmarkCase& benchmark_case) override;

private:
    [[nodiscard]] app::MathResearchService& training_service_for(
        const BenchmarkVariantProfile& variant);

    void freeze_training_state(
        const BenchmarkVariantProfile& variant);

    [[nodiscard]] std::unique_ptr<app::MathResearchService>
    evaluation_service_for(
        const BenchmarkVariantProfile& variant,
        BenchmarkSplit split,
        long long case_index);

    [[nodiscard]] research::ResearchProblem problem_for(
        const BenchmarkCase& benchmark_case,
        std::string episode_id) const;

    ILeanRunner& lean_runner_;
    ITextGenerationBackend& freeform_math_backend_;
    ITextGenerationBackend& lemma_json_backend_;
    ITextGenerationBackend& formalization_json_backend_;

    ResearchBenchmarkExecutorConfig config_;
    std::unordered_map<
        std::string,
        std::unique_ptr<app::MathResearchService>>
        training_services_;
    std::unordered_set<std::string>
        frozen_variants_;
    std::unordered_map<std::string, long long>
        case_counters_;
};

} // namespace expert_robot::eval
