#include "expert_robot/eval/math_benchmark.hpp"
#include "expert_robot/eval/research_benchmark_executor.hpp"

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
    const auto* graph_holdout =
        summary(
            run,
            "theorem_graph",
            BenchmarkSplit::Holdout);

    assert(baseline_train != nullptr);
    assert(baseline_holdout != nullptr);
    assert(graph_train != nullptr);
    assert(graph_holdout != nullptr);

    assert(baseline_train->verified == 0);
    assert(baseline_holdout->verified == 0);

    // Only cases with explicit safe USES dependencies can pass the fake Lean
    // runner, proving graph retrieval is both enabled and relation-aware.
    assert(graph_train->verified == 1);
    assert(graph_holdout->verified == 1);
    assert(graph_train->zero_model_verified == 1);
    assert(graph_holdout->zero_model_verified == 1);

    assert(model.calls == 0);
    assert(lean.calls > 0);

    std::filesystem::remove_all(root);
    return 0;
}
