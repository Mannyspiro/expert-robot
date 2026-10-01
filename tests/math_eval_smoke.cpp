#include "expert_robot/eval/math_eval.hpp"

#include <cassert>
#include <cmath>
#include <filesystem>
#include <stdexcept>

int main() {
    using namespace expert_robot::eval;

    const auto db =
        std::filesystem::temp_directory_path() /
        "expert-robot-math-eval.sqlite3";
    std::filesystem::remove(db);

    MathEvalLedger ledger(db);

    for (int i = 0; i < 20; ++i) {
        ledger.record(MathEvalRecord{
            .run_id = "baseline-run",
            .variant = "baseline",
            .case_id = "case-" + std::to_string(i),
            .domain = i % 2 == 0 ? "algebra" : "geometry",
            .verified = i < 10,
            .dead_end_escaped = i < 2,
            .wall_time_ms = 1000,
            .model_calls = 1,
            .proof_attempts = 5,
            .lemmas_generated = 0,
            .ideas_generated = 2,
            .duplicate_candidates = i % 4 == 0 ? 1 : 0,
            .resource_cost = 1.0
        });

        ledger.record(MathEvalRecord{
            .run_id = "candidate-run",
            .variant = "hybrid",
            .case_id = "case-" + std::to_string(i),
            .domain = i % 2 == 0 ? "algebra" : "geometry",
            .verified = i < 13,
            .dead_end_escaped = i < 7,
            .wall_time_ms = 1200,
            .model_calls = 4,
            .proof_attempts = 4,
            .lemmas_generated = 2,
            .ideas_generated = 6,
            .duplicate_candidates = i % 5 == 0 ? 1 : 0,
            .resource_cost = 1.5
        });
    }

    const auto baseline =
        ledger.summarize("baseline");
    const auto candidate =
        ledger.summarize("hybrid");

    assert(baseline.cases == 20);
    assert(baseline.verified == 10);
    assert(candidate.cases == 20);
    assert(candidate.verified == 13);
    assert(
        std::abs(baseline.verified_rate() - 0.5) <
        1e-12);
    assert(
        std::abs(candidate.verified_rate() - 0.65) <
        1e-12);

    const auto comparison =
        compare_variants(
            baseline,
            candidate);

    assert(comparison.enough_cases);
    assert(comparison.verification_ok);
    assert(comparison.efficiency_ok);
    assert(comparison.diversity_ok);
    assert(comparison.recommend_keep);
    assert(comparison.verified_rate_delta > 0.0);

    VariantSummary regressed = candidate;
    regressed.variant = "regressed";
    regressed.verified = 8;

    const auto bad =
        compare_variants(
            baseline,
            regressed);

    assert(!bad.verification_ok);
    assert(!bad.recommend_keep);

    VariantSummary duplicate_heavy = candidate;
    duplicate_heavy.variant = "duplicate-heavy";
    duplicate_heavy.total_duplicate_candidates =
        duplicate_heavy.total_ideas_generated;

    const auto duplicate_bad =
        compare_variants(
            baseline,
            duplicate_heavy);

    assert(!duplicate_bad.diversity_ok);
    assert(!duplicate_bad.recommend_keep);

    bool duplicate_record_rejected = false;
    try {
        validate_eval_record(MathEvalRecord{
            .run_id = "invalid",
            .variant = "invalid",
            .case_id = "bad",
            .domain = "test",
            .verified = false,
            .dead_end_escaped = false,
            .wall_time_ms = 0,
            .model_calls = 0,
            .proof_attempts = 0,
            .lemmas_generated = 0,
            .ideas_generated = 1,
            .duplicate_candidates = 2,
            .resource_cost = 0.0
        });
    } catch (const std::invalid_argument&) {
        duplicate_record_rejected = true;
    }
    assert(duplicate_record_rejected);

    const auto all =
        ledger.records();
    assert(all.size() == 40);

    std::filesystem::remove(db);
    return 0;
}
