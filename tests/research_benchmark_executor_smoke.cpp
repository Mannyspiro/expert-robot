#include "expert_robot/eval/math_benchmark.hpp"
#include "expert_robot/eval/research_benchmark_executor.hpp"
#include "expert_robot/proof_memory.hpp"
#include "expert_robot/research/route_memory.hpp"

#include <algorithm>
#include <cassert>
#include <filesystem>
#include <stdexcept>
#include <string>

namespace {

class GraphHintLeanRunner final
    : public expert_robot::ILeanRunner {
public:
    expert_robot::LeanRunResult run(
        std::string_view source) override {
        ++calls;

        if (source.find(
                "simp [MathAI.Geometry.dot_comm]") !=
                std::string_view::npos ||
            source.find(
                "rw [MathAI.Geometry.dot_comm] <;> aesop") !=
                std::string_view::npos ||
            source.find(
                "simp [MathAI.Geometry.dot_zero_left]") !=
                std::string_view::npos ||
            source.find(
                "rw [MathAI.Geometry.dot_zero_left] <;> aesop") !=
                std::string_view::npos) {
            return {
                .exit_code = 0,
                .output = "accepted verified graph dependency"
            };
        }

        return {
            .exit_code = 1,
            .output = "generic tactic intentionally rejected"
        };
    }

    long long calls{0};
};

class RejectModelBackend final
    : public expert_robot::ITextGenerationBackend {
public:
    expert_robot::TextGenerationResult generate(
        const expert_robot::TextGenerationRequest&) override {
        ++calls;
        throw std::runtime_error(
            "model backend must not be reached in deterministic architecture benchmark");
    }

    long long calls{0};
};

expert_robot::eval::BenchmarkCase make_case(
    std::string id,
    std::string family,
    expert_robot::eval::BenchmarkSplit split,
    std::string focus,
    std::string name,
    std::vector<expert_robot::eval::BenchmarkBinder> binders,
    std::string proposition) {
    return expert_robot::eval::BenchmarkCase{
        .case_id = std::move(id),
        .family = std::move(family),
        .domain = "geometry",
        .focus_theorem = std::move(focus),
        .declaration_name = std::move(name),
        .name_space = "MathAI.Benchmark",
        .binders = std::move(binders),
        .proposition = std::move(proposition),
        .imports = {"MathAI"},
        .split = split,
        .tags = {"lean_verified"}
    };
}

const expert_robot::eval::BenchmarkVariantSummary*
summary(
    const expert_robot::eval::BenchmarkRun& run,
    const std::string& variant,
    expert_robot::eval::BenchmarkSplit split) {
    const auto it =
        std::find_if(
            run.summaries.begin(),
            run.summaries.end(),
            [&](const auto& item) {
                return
                    item.variant_id == variant &&
                    item.split == split &&
                    item.domain == "all";
            });

    return it == run.summaries.end()
        ? nullptr
        : &*it;
}

} // namespace

int main() {
    using namespace expert_robot;
    using namespace expert_robot::eval;

    const std::vector<BenchmarkVariantProfile> variants{
        {
            .variant_id = "proof_search",
            .enabled_layers = {"proof_search"}
        },
        {
            .variant_id = "theorem_graph",
            .enabled_layers = {
                "proof_search",
                "theorem_graph"
            }
        },
        {
            .variant_id = "route_memory",
            .enabled_layers = {
                "proof_search",
                "theorem_graph",
                "route_memory"
            }
        },
        {
            .variant_id = "sequence_memory",
            .enabled_layers = {
                "proof_search",
                "theorem_graph",
                "route_memory",
                "sequence_memory"
            }
        },
        {
            .variant_id = "strategy_memory",
            .enabled_layers = {
                "proof_search",
                "theorem_graph",
                "route_memory",
                "sequence_memory",
                "strategy_memory"
            }
        }
    };

    const auto baseline_flags =
        benchmark_feature_flags(
            variants[0]);
    assert(!baseline_flags.theorem_graph);
    assert(!baseline_flags.route_planning);
    assert(!baseline_flags.imagination);
    assert(!baseline_flags.decomposition);
    assert(!baseline_flags.route_memory);
    assert(!baseline_flags.sequence_memory);
    assert(!baseline_flags.strategy_planning);
    assert(!baseline_flags.strategy_memory);

    const auto graph_flags =
        benchmark_feature_flags(
            variants[1]);
    assert(graph_flags.theorem_graph);
    assert(graph_flags.route_planning);
    assert(!graph_flags.route_memory);
    assert(!graph_flags.sequence_memory);
    assert(!graph_flags.strategy_memory);

    const auto strategy_flags =
        benchmark_feature_flags(
            variants[4]);
    assert(strategy_flags.theorem_graph);
    assert(strategy_flags.route_planning);
    assert(strategy_flags.route_memory);
    assert(strategy_flags.sequence_memory);
    assert(strategy_flags.strategy_planning);
    assert(strategy_flags.strategy_memory);
    assert(!strategy_flags.imagination);
    assert(!strategy_flags.decomposition);

    bool bad_hierarchy_rejected = false;
    try {
        (void)benchmark_feature_flags(
            BenchmarkVariantProfile{
                .variant_id = "bad",
                .enabled_layers = {
                    "proof_search",
                    "sequence_memory"
                }
            });
    } catch (const std::invalid_argument&) {
        bad_hierarchy_rejected = true;
    }
    assert(bad_hierarchy_rejected);

    MathBenchmarkSuite suite(
        {
            make_case(
                "train-orthogonal-symm",
                "orthogonal-symmetry-train",
                BenchmarkSplit::Train,
                "MathAI.Geometry.orthogonal_symm",
                "train_orthogonal_symm",
                {
                    {"a", "MathAI.Geometry.Vec3"},
                    {"b", "MathAI.Geometry.Vec3"}
                },
                "MathAI.Geometry.orthogonal a b ↔ MathAI.Geometry.orthogonal b a"),
            make_case(
                "train-no-graph-proof",
                "distance-self-train",
                BenchmarkSplit::Train,
                "MathAI.Geometry.squaredDistance_self",
                "train_distance_self",
                {
                    {"p", "MathAI.Geometry.Point3"}
                },
                "MathAI.Geometry.squaredDistance p p = 0"),
            make_case(
                "validation-dot-zero-left",
                "dot-zero-left-validation",
                BenchmarkSplit::Validation,
                "MathAI.Geometry.dot_zero_left",
                "validation_dot_zero_left",
                {
                    {"a", "MathAI.Geometry.Vec3"}
                },
                "MathAI.Geometry.dot MathAI.Geometry.zeroVec a = 0"),
            make_case(
                "holdout-zero-orthogonal",
                "zero-orthogonality-holdout",
                BenchmarkSplit::Holdout,
                "MathAI.Geometry.zero_orthogonal_left",
                "holdout_zero_orthogonal",
                {
                    {"a", "MathAI.Geometry.Vec3"}
                },
                "MathAI.Geometry.orthogonal MathAI.Geometry.zeroVec a"),
            make_case(
                "holdout-no-graph-proof",
                "distance-symmetry-holdout",
                BenchmarkSplit::Holdout,
                "MathAI.Geometry.squaredDistance_symm",
                "holdout_distance_symm",
                {
                    {"a", "MathAI.Geometry.Point3"},
                    {"b", "MathAI.Geometry.Point3"}
                },
                "MathAI.Geometry.squaredDistance a b = MathAI.Geometry.squaredDistance b a")
        },
        variants);

    const auto root =
        std::filesystem::temp_directory_path() /
        "expert-robot-engine-benchmark";
    std::filesystem::remove_all(root);

    GraphHintLeanRunner lean;
    RejectModelBackend model;

    app::MathResearchServiceConfig service_config;
    service_config.proof_search_config =
        "config/proof_search.json";
    service_config.theorem_registry =
        "formal/theorem_registry.json";
    service_config.research_engine.budget =
        research::ResearchBudget{
            .max_cycles = 4,
            .max_model_calls = 4,
            .max_proof_attempts = 64,
            .max_generated_ideas = 4,
            .max_generated_lemmas = 4
        };
    service_config.research_engine.max_dispatch_steps = 8;

    ResearchBenchmarkExecutor executor(
        lean,
        model,
        model,
        model,
        ResearchBenchmarkExecutorConfig{
            .state_root = root,
            .service = service_config,
            .reset_state_root = true
        });

    MathBenchmarkRunner runner;
    const auto run =
        runner.run(
            "engine-benchmark-smoke",
            suite,
            executor);

    const auto* baseline_train =
        summary(
            run,
            "proof_search",
            BenchmarkSplit::Train);
    const auto* baseline_validation =
        summary(
            run,
            "proof_search",
            BenchmarkSplit::Validation);
    const auto* baseline_holdout =
        summary(
            run,
            "proof_search",
            BenchmarkSplit::Holdout);
    const auto* graph_train =
        summary(
            run,
            "theorem_graph",
            BenchmarkSplit::Train);
    const auto* graph_validation =
        summary(
            run,
            "theorem_graph",
            BenchmarkSplit::Validation);
    const auto* graph_holdout =
        summary(
            run,
            "theorem_graph",
            BenchmarkSplit::Holdout);

    assert(baseline_train != nullptr);
    assert(baseline_validation != nullptr);
    assert(baseline_holdout != nullptr);
    assert(graph_train != nullptr);
    assert(graph_validation != nullptr);
    assert(graph_holdout != nullptr);

    assert(baseline_train->verified == 0);
    assert(baseline_validation->verified == 0);
    assert(baseline_holdout->verified == 0);

    // Only cases with explicit safe USES dependencies can pass the fake Lean
    // runner, proving graph retrieval is both enabled and relation-aware.
    assert(graph_train->verified == 1);
    assert(graph_validation->verified == 1);
    assert(graph_holdout->verified == 1);
    assert(graph_train->zero_model_verified == 1);
    assert(graph_validation->zero_model_verified == 1);
    assert(graph_holdout->zero_model_verified == 1);

    assert(model.calls == 0);
    assert(lean.calls > 0);

    // Holdout cases must all start from the exact same frozen training state.
    // They may read learned proof/route/strategy evidence but must not write
    // any of their own outcomes back into those stores.
    const auto frozen_state =
        root / "strategy_memory" / "frozen_train";
    const auto validation_three =
        root / "strategy_memory" / "validation" / "case-3";
    const auto holdout_four =
        root / "strategy_memory" / "holdout" / "case-4";
    const auto holdout_five =
        root / "strategy_memory" / "holdout" / "case-5";

    for (const auto& state :
         {frozen_state,
          validation_three,
          holdout_four,
          holdout_five}) {
        assert(
            std::filesystem::exists(
                state / "proof_memory.sqlite3"));
        assert(
            std::filesystem::exists(
                state / "route_memory.sqlite3"));
    }

    ProofMemory frozen_proof(
        frozen_state / "proof_memory.sqlite3");
    ProofMemory validation_three_proof(
        validation_three / "proof_memory.sqlite3");
    ProofMemory holdout_four_proof(
        holdout_four / "proof_memory.sqlite3");
    ProofMemory holdout_five_proof(
        holdout_five / "proof_memory.sqlite3");

    const auto frozen_proof_summary =
        frozen_proof.summary();
    const auto validation_three_summary =
        validation_three_proof.summary();
    const auto holdout_four_summary =
        holdout_four_proof.summary();
    const auto holdout_five_summary =
        holdout_five_proof.summary();

    assert(
        frozen_proof_summary.attempts ==
        validation_three_summary.attempts);
    assert(
        frozen_proof_summary.attempts ==
        holdout_four_summary.attempts);
    assert(
        frozen_proof_summary.attempts ==
        holdout_five_summary.attempts);
    assert(
        frozen_proof_summary.successful_attempts ==
        validation_three_summary.successful_attempts);
    assert(
        frozen_proof_summary.successful_attempts ==
        holdout_four_summary.successful_attempts);
    assert(
        frozen_proof_summary.successful_attempts ==
        holdout_five_summary.successful_attempts);

    research::RouteOutcomeLedger frozen_routes(
        frozen_state / "route_memory.sqlite3");
    research::RouteOutcomeLedger validation_three_routes(
        validation_three / "route_memory.sqlite3");
    research::RouteOutcomeLedger holdout_four_routes(
        holdout_four / "route_memory.sqlite3");
    research::RouteOutcomeLedger holdout_five_routes(
        holdout_five / "route_memory.sqlite3");

    const auto route_attempts =
        [](const research::RouteOutcomeLedger& ledger) {
            long long total = 0;
            for (const auto& experience :
                 ledger.all_experience()) {
                total += experience.attempts;
            }
            return total;
        };

    const auto strategy_attempts =
        [](const research::RouteOutcomeLedger& ledger) {
            long long total = 0;
            for (const auto& experience :
                 ledger.all_strategy_experience()) {
                total += experience.attempts;
            }
            return total;
        };

    const auto step_attempts =
        [](const research::RouteOutcomeLedger& ledger) {
            long long total = 0;
            for (const auto& experience :
                 ledger.all_strategy_step_experience()) {
                total += experience.attempts;
            }
            return total;
        };

    assert(
        route_attempts(frozen_routes) ==
        route_attempts(validation_three_routes));
    assert(
        route_attempts(frozen_routes) ==
        route_attempts(holdout_four_routes));
    assert(
        route_attempts(frozen_routes) ==
        route_attempts(holdout_five_routes));
    assert(
        strategy_attempts(frozen_routes) ==
        strategy_attempts(validation_three_routes));
    assert(
        strategy_attempts(frozen_routes) ==
        strategy_attempts(holdout_four_routes));
    assert(
        strategy_attempts(frozen_routes) ==
        strategy_attempts(holdout_five_routes));
    assert(
        step_attempts(frozen_routes) ==
        step_attempts(validation_three_routes));
    assert(
        step_attempts(frozen_routes) ==
        step_attempts(holdout_four_routes));
    assert(
        step_attempts(frozen_routes) ==
        step_attempts(holdout_five_routes));

    std::filesystem::remove_all(root);
    return 0;
}
