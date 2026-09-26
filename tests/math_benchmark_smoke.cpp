#include "expert_robot/eval/math_benchmark.hpp"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <filesystem>
#include <stdexcept>
#include <string>

namespace {

class DeterministicExecutor final
    : public expert_robot::eval::IMathBenchmarkExecutor {
public:
    expert_robot::eval::BenchmarkCaseResult run(
        const expert_robot::eval::BenchmarkVariantProfile& variant,
        const expert_robot::eval::BenchmarkCase& benchmark_case) override {
        using expert_robot::eval::BenchmarkCaseResult;

        const bool evaluation =
            benchmark_case.split !=
            expert_robot::eval::BenchmarkSplit::Train;

        long long level = 0;
        if (variant.has_layer("proof_search")) ++level;
        if (variant.has_layer("theorem_graph")) ++level;
        if (variant.has_layer("route_memory")) ++level;
        if (variant.has_layer("sequence_memory")) ++level;
        if (variant.has_layer("strategy_memory")) ++level;

        // Stable synthetic capability profile for harness testing:
        // training cases are intentionally easier; holdouts require
        // progressively deeper architecture.
        const bool verified =
            evaluation
                ? (level >= 2 &&
                   (level >= 4 ||
                    benchmark_case.case_id.find("symm") !=
                        std::string::npos))
                : level >= 1;

        const long long model_calls =
            variant.has_layer("theorem_graph") &&
            benchmark_case.tags.end() !=
                std::find(
                    benchmark_case.tags.begin(),
                    benchmark_case.tags.end(),
                    "lean_verified")
                ? 0
                : std::max<long long>(
                    0,
                    5 - level);

        return BenchmarkCaseResult{
            .verified = verified,
            .dead_end_escaped =
                verified && level >= 3,
            .wall_time_ms =
                120 + 20 * (5 - level),
            .model_calls =
                model_calls,
            .proof_attempts =
                std::max<long long>(
                    1,
                    7 - level),
            .lemmas_generated =
                level >= 4 ? 1 : 0,
            .ideas_generated =
                level >= 4 ? 3 : 0,
            .duplicate_candidates =
                level >= 4 ? 1 : 0,
            .resource_cost =
                1.20 -
                0.10 *
                    static_cast<double>(level)
        };
    }
};

const expert_robot::eval::BenchmarkVariantSummary*
find_summary(
    const expert_robot::eval::BenchmarkRun& run,
    const std::string& variant,
    expert_robot::eval::BenchmarkSplit split,
    const std::string& domain = "all") {
    const auto it =
        std::find_if(
            run.summaries.begin(),
            run.summaries.end(),
            [&](const auto& summary) {
                return
                    summary.variant_id == variant &&
                    summary.split == split &&
                    summary.domain == domain;
            });

    return it == run.summaries.end()
        ? nullptr
        : &*it;
}

} // namespace

int main() {
    using namespace expert_robot::eval;

    const auto suite =
        MathBenchmarkSuite::load_json(
            "config/benchmarks/core_math_holdout.json");

    assert(suite.cases().size() == 12);
    assert(suite.variants().size() == 5);
    assert(
        suite.cases_for_split(
            BenchmarkSplit::Train).size() == 5);
    assert(
        suite.cases_for_split(
            BenchmarkSplit::Validation).size() == 2);
    assert(
        suite.cases_for_split(
            BenchmarkSplit::Holdout).size() == 5);

    for (const auto& benchmark_case : suite.cases()) {
        if (benchmark_case.split == BenchmarkSplit::Train) {
            assert(
                benchmark_case.knowledge_mode ==
                BenchmarkKnowledgeMode::KnownTheoremRetrieval);
            assert(!benchmark_case.focus_theorem.empty());
        } else {
            assert(
                benchmark_case.knowledge_mode ==
                BenchmarkKnowledgeMode::BlindGeneralization);
            assert(benchmark_case.focus_theorem.empty());
        }
    }

    bool evaluation_identity_leak_rejected = false;
    try {
        (void)MathBenchmarkSuite(
            {
                BenchmarkCase{
                    .case_id = "train-known",
                    .family = "train-known-family",
                    .domain = "geometry",
                    .focus_theorem = "MathAI.Geometry.dot_comm",
                    .declaration_name = "train_known",
                    .name_space = "MathAI.Benchmark",
                    .binders = {},
                    .proposition = "True",
                    .imports = {"MathAI"},
                    .split = BenchmarkSplit::Train,
                    .tags = {},
                    .knowledge_mode =
                        BenchmarkKnowledgeMode::KnownTheoremRetrieval
                },
                BenchmarkCase{
                    .case_id = "validation-leak",
                    .family = "validation-leak-family",
                    .domain = "geometry",
                    .focus_theorem = "MathAI.Geometry.cross_self",
                    .declaration_name = "validation_leak",
                    .name_space = "MathAI.Benchmark",
                    .binders = {},
                    .proposition = "True",
                    .imports = {"MathAI"},
                    .split = BenchmarkSplit::Validation,
                    .tags = {},
                    .knowledge_mode =
                        BenchmarkKnowledgeMode::KnownTheoremRetrieval
                },
                BenchmarkCase{
                    .case_id = "holdout-blind",
                    .family = "holdout-blind-family",
                    .domain = "geometry",
                    .focus_theorem = "",
                    .declaration_name = "holdout_blind",
                    .name_space = "MathAI.Benchmark",
                    .binders = {},
                    .proposition = "True",
                    .imports = {"MathAI"},
                    .split = BenchmarkSplit::Holdout,
                    .tags = {},
                    .knowledge_mode =
                        BenchmarkKnowledgeMode::BlindGeneralization
                }
            },
            {
                BenchmarkVariantProfile{
                    .variant_id = "baseline",
                    .enabled_layers = {"proof_search"}
                }
            });
    } catch (const std::invalid_argument&) {
        evaluation_identity_leak_rejected = true;
    }
    assert(evaluation_identity_leak_rejected);

    const auto db =
        std::filesystem::temp_directory_path() /
        "expert-robot-benchmark-smoke.sqlite3";
    std::filesystem::remove(db);

    MathEvalLedger ledger(db);
    MathBenchmarkRunner runner(&ledger);
    DeterministicExecutor executor;

    const auto run =
        runner.run(
            "benchmark-smoke-run",
            suite,
            executor);

    assert(run.records.size() == 60);

    const auto* baseline_validation =
        find_summary(
            run,
            "proof_search",
            BenchmarkSplit::Validation);
    const auto* strategy_validation =
        find_summary(
            run,
            "strategy_memory",
            BenchmarkSplit::Validation);
    const auto* baseline_holdout =
        find_summary(
            run,
            "proof_search",
            BenchmarkSplit::Holdout);
    const auto* graph_holdout =
        find_summary(
            run,
            "theorem_graph",
            BenchmarkSplit::Holdout);
    const auto* strategy_holdout =
        find_summary(
            run,
            "strategy_memory",
            BenchmarkSplit::Holdout);
    const auto* strategy_geometry =
        find_summary(
            run,
            "strategy_memory",
            BenchmarkSplit::Holdout,
            "geometry");

    assert(baseline_validation != nullptr);
    assert(strategy_validation != nullptr);
    assert(baseline_holdout != nullptr);
    assert(graph_holdout != nullptr);
    assert(strategy_holdout != nullptr);
    assert(strategy_geometry != nullptr);

    assert(baseline_validation->cases == 2);
    assert(strategy_validation->cases == 2);
    assert(baseline_holdout->cases == 5);
    assert(strategy_holdout->cases == 5);
    assert(strategy_geometry->cases == 5);

    assert(
        graph_holdout->zero_model_verified >
        baseline_holdout->zero_model_verified);
    assert(
        strategy_holdout->verified_rate() >
        baseline_holdout->verified_rate());
    assert(
        strategy_holdout->average_proof_attempts() <
        baseline_holdout->average_proof_attempts());

    assert(
        std::abs(
            strategy_holdout->
                verified_rate() -
            1.0) < 1e-12);

    const auto validation_persisted =
        ledger.records(
            "strategy_memory::validation");
    assert(validation_persisted.size() == 2);

    const auto persisted =
        ledger.records(
            "strategy_memory::holdout");
    assert(persisted.size() == 5);

    // Same family in train and holdout is forbidden even if case IDs differ.
    bool leakage_rejected = false;
    try {
        (void)MathBenchmarkSuite(
            {
                BenchmarkCase{
                    .case_id = "train-a",
                    .family = "same-family",
                    .domain = "algebra",
                    .focus_theorem = "",
                    .declaration_name = "train_a",
                    .name_space = "MathAI.Benchmark",
                    .binders = {},
                    .proposition = "True",
                    .imports = {"MathAI"},
                    .split = BenchmarkSplit::Train
                },
                BenchmarkCase{
                    .case_id = "holdout-b",
                    .family = "same-family",
                    .domain = "algebra",
                    .focus_theorem = "",
                    .declaration_name = "holdout_b",
                    .name_space = "MathAI.Benchmark",
                    .binders = {},
                    .proposition = "True",
                    .imports = {"MathAI"},
                    .split = BenchmarkSplit::Holdout
                }
            },
            {
                BenchmarkVariantProfile{
                    .variant_id = "baseline",
                    .enabled_layers = {"proof_search"}
                }
            });
    } catch (const std::invalid_argument&) {
        leakage_rejected = true;
    }
    assert(leakage_rejected);

    // A train+holdout suite without validation is invalid.
    bool missing_validation_rejected = false;
    try {
        (void)MathBenchmarkSuite(
            {
                BenchmarkCase{
                    .case_id = "train-validation-check",
                    .family = "train-validation-family",
                    .domain = "geometry",
                    .focus_theorem = "",
                    .declaration_name = "train_validation_check",
                    .name_space = "MathAI.Benchmark",
                    .binders = {},
                    .proposition = "True",
                    .imports = {"MathAI"},
                    .split = BenchmarkSplit::Train
                },
                BenchmarkCase{
                    .case_id = "holdout-validation-check",
                    .family = "holdout-validation-family",
                    .domain = "geometry",
                    .focus_theorem = "",
                    .declaration_name = "holdout_validation_check",
                    .name_space = "MathAI.Benchmark",
                    .binders = {},
                    .proposition = "True",
                    .imports = {"MathAI"},
                    .split = BenchmarkSplit::Holdout
                }
            },
            {
                BenchmarkVariantProfile{
                    .variant_id = "baseline",
                    .enabled_layers = {"proof_search"}
                }
            });
    } catch (const std::invalid_argument&) {
        missing_validation_rejected = true;
    }
    assert(missing_validation_rejected);

    // Missing one split is also invalid; all three phases are mandatory.
    bool missing_holdout_rejected = false;
    try {
        (void)MathBenchmarkSuite(
            {
                BenchmarkCase{
                    .case_id = "train-only",
                    .family = "train-only-family",
                    .domain = "geometry",
                    .focus_theorem = "",
                    .declaration_name = "train_only",
                    .name_space = "MathAI.Benchmark",
                    .binders = {},
                    .proposition = "True",
                    .imports = {"MathAI"},
                    .split = BenchmarkSplit::Train
                }
            },
            {
                BenchmarkVariantProfile{
                    .variant_id = "baseline",
                    .enabled_layers = {"proof_search"}
                }
            });
    } catch (const std::invalid_argument&) {
        missing_holdout_rejected = true;
    }
    assert(missing_holdout_rejected);

    std::filesystem::remove(db);
    return 0;
}
