#pragma once

#include "expert_robot/eval/math_eval.hpp"

#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

namespace expert_robot::eval {

enum class BenchmarkSplit {
    Train,
    Validation,
    Holdout
};

enum class BenchmarkKnowledgeMode {
    KnownTheoremRetrieval,
    BlindGeneralization
};

[[nodiscard]] std::string_view benchmark_split_name(
    BenchmarkSplit split);

[[nodiscard]] std::string_view benchmark_knowledge_mode_name(
    BenchmarkKnowledgeMode mode);

struct BenchmarkBinder {
    std::string name;
    std::string type;
};

struct BenchmarkCase {
    std::string case_id;
    std::string family;
    std::string domain;

    // focus_theorem is optional routing context. The executable target below
    // remains fully specified so a graph-disabled variant never needs registry
    // lookup to know what proposition it is proving.
    std::string focus_theorem;

    std::string declaration_name;
    std::string name_space{"MathAI.Benchmark"};
    std::vector<BenchmarkBinder> binders;
    std::string proposition;
    std::vector<std::string> imports{"MathAI"};

    BenchmarkSplit split{BenchmarkSplit::Train};
    std::vector<std::string> tags;
    BenchmarkKnowledgeMode knowledge_mode{
        BenchmarkKnowledgeMode::BlindGeneralization
    };
};

struct BenchmarkVariantProfile {
    std::string variant_id;
    std::vector<std::string> enabled_layers;

    [[nodiscard]] bool has_layer(
        std::string_view layer) const;
};

struct BenchmarkCaseResult {
    bool verified{false};
    bool dead_end_escaped{false};

    long long wall_time_ms{0};
    long long model_calls{0};
    long long proof_attempts{0};
    long long lemmas_generated{0};
    long long ideas_generated{0};
    long long duplicate_candidates{0};

    double resource_cost{0.0};
};

class IMathBenchmarkExecutor {
public:
    virtual ~IMathBenchmarkExecutor() = default;

    [[nodiscard]] virtual BenchmarkCaseResult run(
        const BenchmarkVariantProfile& variant,
        const BenchmarkCase& benchmark_case) = 0;
};

class MathBenchmarkSuite {
public:
    MathBenchmarkSuite(
        std::vector<BenchmarkCase> cases,
        std::vector<BenchmarkVariantProfile> variants);

    [[nodiscard]] static MathBenchmarkSuite load_json(
        const std::filesystem::path& path);

    [[nodiscard]] const std::vector<BenchmarkCase>& cases() const noexcept;
    [[nodiscard]] const std::vector<BenchmarkVariantProfile>& variants() const noexcept;

    [[nodiscard]] std::vector<BenchmarkCase> cases_for_split(
        BenchmarkSplit split) const;

private:
    std::vector<BenchmarkCase> cases_;
    std::vector<BenchmarkVariantProfile> variants_;
};

struct BenchmarkVariantSummary {
    std::string run_id;
    std::string variant_id;
    BenchmarkSplit split{BenchmarkSplit::Train};
    std::string domain{"all"};

    long long cases{0};
    long long verified{0};
    long long zero_model_verified{0};
    long long dead_end_escapes{0};

    long long total_wall_time_ms{0};
    long long total_model_calls{0};
    long long total_proof_attempts{0};
    long long total_lemmas_generated{0};
    long long total_ideas_generated{0};
    long long total_duplicate_candidates{0};

    double total_resource_cost{0.0};

    [[nodiscard]] double verified_rate() const noexcept;
    [[nodiscard]] double zero_model_verified_rate() const noexcept;
    [[nodiscard]] double average_model_calls() const noexcept;
    [[nodiscard]] double average_proof_attempts() const noexcept;
    [[nodiscard]] double average_resource_cost() const noexcept;
};

struct BenchmarkRun {
    std::string run_id;
    std::vector<MathEvalRecord> records;
    std::vector<BenchmarkVariantSummary> summaries;
};

class MathBenchmarkRunner {
public:
    explicit MathBenchmarkRunner(
        MathEvalLedger* ledger = nullptr);

    [[nodiscard]] BenchmarkRun run(
        std::string run_id,
        const MathBenchmarkSuite& suite,
        IMathBenchmarkExecutor& executor) const;

private:
    MathEvalLedger* ledger_{nullptr};
};

} // namespace expert_robot::eval
