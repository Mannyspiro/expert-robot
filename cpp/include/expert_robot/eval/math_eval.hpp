#pragma once

#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

struct sqlite3;

namespace expert_robot::eval {

struct MathEvalRecord {
    std::string run_id;
    std::string variant;
    std::string case_id;
    std::string domain;

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

struct VariantSummary {
    std::string variant;
    long long cases{0};
    long long verified{0};
    long long dead_end_escapes{0};

    long long total_wall_time_ms{0};
    long long total_model_calls{0};
    long long total_proof_attempts{0};
    long long total_lemmas_generated{0};
    long long total_ideas_generated{0};
    long long total_duplicate_candidates{0};

    double total_resource_cost{0.0};

    [[nodiscard]] double verified_rate() const noexcept;
    [[nodiscard]] double average_resource_cost() const noexcept;
    [[nodiscard]] double resource_cost_per_verified() const noexcept;
    [[nodiscard]] double duplicate_rate() const noexcept;
};

struct AblationPolicy {
    long long minimum_cases{10};

    // Candidate must not regress verification success beyond this tolerance.
    double maximum_verified_rate_regression{0.0};

    // Candidate may spend somewhat more compute if it solves more cases.
    double maximum_cost_multiplier_without_accuracy_gain{1.10};

    // Meaningful verified-rate gain that permits extra compute.
    double meaningful_verified_rate_gain{0.05};

    // Avoid retaining a system that creates substantially more duplicates.
    double maximum_duplicate_rate_increase{0.10};
};

struct AblationResult {
    VariantSummary baseline;
    VariantSummary candidate;

    double verified_rate_delta{0.0};
    double cost_per_verified_ratio{0.0};
    double duplicate_rate_delta{0.0};

    bool enough_cases{false};
    bool verification_ok{false};
    bool efficiency_ok{false};
    bool diversity_ok{false};

    // Recommendation only. It never changes capability qualification.
    bool recommend_keep{false};
};

void validate_eval_record(const MathEvalRecord& record);
void validate_ablation_policy(const AblationPolicy& policy);

[[nodiscard]] AblationResult compare_variants(
    const VariantSummary& baseline,
    const VariantSummary& candidate,
    const AblationPolicy& policy = {});

class MathEvalLedger {
public:
    explicit MathEvalLedger(std::filesystem::path path);
    ~MathEvalLedger();

    MathEvalLedger(const MathEvalLedger&) = delete;
    MathEvalLedger& operator=(const MathEvalLedger&) = delete;

    void record(const MathEvalRecord& record);

    [[nodiscard]] VariantSummary summarize(
        std::string_view variant) const;

    [[nodiscard]] std::vector<MathEvalRecord> records(
        std::string_view variant = {}) const;

private:
    void initialize();

    std::filesystem::path path_;
    sqlite3* db_{nullptr};
};

} // namespace expert_robot::eval
