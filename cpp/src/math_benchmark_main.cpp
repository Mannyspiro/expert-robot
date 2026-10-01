#include "expert_robot/eval/math_benchmark.hpp"
#include "expert_robot/eval/research_benchmark_executor.hpp"
#include "expert_robot/json_util.hpp"
#include "expert_robot/proof_search.hpp"
#include "expert_robot/text_generation.hpp"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

class RejectModelBackend final
    : public expert_robot::ITextGenerationBackend {
public:
    expert_robot::TextGenerationResult generate(
        const expert_robot::TextGenerationRequest&) override {
        throw std::runtime_error(
            "deterministic architecture benchmark attempted a model call");
    }
};

std::string render_json(
    const expert_robot::eval::BenchmarkRun& run) {
    using expert_robot::json_util::escape;

    std::string out;
    out += "{\n";
    out += "  \"run_id\": \"" +
           escape(run.run_id) + "\",\n";
    out += "  \"summaries\": [\n";

    for (std::size_t i = 0;
         i < run.summaries.size();
         ++i) {
        const auto& s =
            run.summaries[i];

        out += "    {";
        out += "\"variant\":\"" +
               escape(s.variant_id) + "\",";
        out += "\"split\":\"" +
               std::string(
                   expert_robot::eval::
                       benchmark_split_name(
                           s.split)) +
               "\",";
        out += "\"domain\":\"" +
               escape(s.domain) + "\",";
        out += "\"cases\":" +
               std::to_string(s.cases) + ",";
        out += "\"verified\":" +
               std::to_string(s.verified) + ",";
        out += "\"zero_model_verified\":" +
               std::to_string(
                   s.zero_model_verified) + ",";
        out += "\"verified_rate\":" +
               std::to_string(
                   s.verified_rate()) + ",";
        out += "\"average_model_calls\":" +
               std::to_string(
                   s.average_model_calls()) + ",";
        out += "\"average_proof_attempts\":" +
               std::to_string(
                   s.average_proof_attempts()) + ",";
        out += "\"average_resource_cost\":" +
               std::to_string(
                   s.average_resource_cost());
        out += "}";

        if (i + 1U <
            run.summaries.size()) {
            out += ",";
        }
        out += "\n";
    }

    out += "  ],\n";
    out += "  \"records\": [\n";

    for (std::size_t i = 0;
         i < run.records.size();
         ++i) {
        const auto& r =
            run.records[i];

        out += "    {";
        out += "\"variant\":\"" +
               escape(r.variant) + "\",";
        out += "\"case_id\":\"" +
               escape(r.case_id) + "\",";
        out += "\"domain\":\"" +
               escape(r.domain) + "\",";
        out += "\"verified\":" +
               std::string(
                   r.verified ? "true" : "false") + ",";
        out += "\"dead_end_escaped\":" +
               std::string(
                   r.dead_end_escaped ? "true" : "false") + ",";
        out += "\"wall_time_ms\":" +
               std::to_string(r.wall_time_ms) + ",";
        out += "\"model_calls\":" +
               std::to_string(r.model_calls) + ",";
        out += "\"proof_attempts\":" +
               std::to_string(r.proof_attempts) + ",";
        out += "\"lemmas_generated\":" +
               std::to_string(r.lemmas_generated) + ",";
        out += "\"ideas_generated\":" +
               std::to_string(r.ideas_generated) + ",";
        out += "\"duplicate_candidates\":" +
               std::to_string(
                   r.duplicate_candidates) + ",";
        out += "\"resource_cost\":" +
               std::to_string(r.resource_cost);
        out += "}";

        if (i + 1U <
            run.records.size()) {
            out += ",";
        }
        out += "\n";
    }

    out += "  ]\n";
    out += "}\n";
    return out;
}

} // namespace

int main(int argc, char** argv) {
    try {
        const std::filesystem::path suite_path =
            argc > 1
                ? argv[1]
                : "config/benchmarks/core_math_holdout.json";

        const std::filesystem::path state_root =
            argc > 2
                ? argv[2]
                : "build/math-benchmark-state";

        const std::filesystem::path output_path =
            argc > 3
                ? argv[3]
                : "build/math-benchmark-results.json";

        const std::string run_id =
            argc > 4
                ? argv[4]
                : "manual-real-lean";

        const auto loaded_suite =
            expert_robot::eval::
                MathBenchmarkSuite::load_json(
                    suite_path);

        const std::string variant_filter =
            argc > 5
                ? argv[5]
                : "";

        const auto suite =
            [&]() {
                if (variant_filter.empty()) {
                    return loaded_suite;
                }

                const auto found =
                    std::find_if(
                        loaded_suite.variants().begin(),
                        loaded_suite.variants().end(),
                        [&](const auto& variant) {
                            return
                                variant.variant_id ==
                                variant_filter;
                        });

                if (found ==
                    loaded_suite.variants().end()) {
                    throw std::invalid_argument(
                        "unknown benchmark variant filter: " +
                        variant_filter);
                }

                return expert_robot::eval::
                    MathBenchmarkSuite(
                        loaded_suite.cases(),
                        {*found});
            }();

        expert_robot::LeanSubprocessRunner lean(
            "formal",
            20);
        RejectModelBackend no_model;

        expert_robot::app::
            MathResearchServiceConfig
                service_config;

        service_config.proof_search_config =
            "config/proof_search.json";
        service_config.theorem_registry =
            "formal/theorem_registry.json";

        service_config.research_engine.budget =
            expert_robot::research::
                ResearchBudget{
                    .max_cycles = 3,
                    .max_model_calls = 1,
                    .max_proof_attempts = 48,
                    .max_generated_ideas = 1,
                    .max_generated_lemmas = 1
                };

        service_config.research_engine.
            max_dispatch_steps = 8;

        expert_robot::eval::
            ResearchBenchmarkExecutor executor(
                lean,
                no_model,
                no_model,
                no_model,
                expert_robot::eval::
                    ResearchBenchmarkExecutorConfig{
                        .state_root =
                            state_root,
                        .service =
                            service_config,
                        .reset_state_root =
                            true
                    });

        expert_robot::eval::MathEvalLedger ledger(
            state_root / "math_eval.sqlite3");

        expert_robot::eval::MathBenchmarkRunner runner(
            &ledger);

        const auto run =
            runner.run(
                run_id,
                suite,
                executor);

        const std::string json =
            render_json(run);

        if (!output_path.parent_path().empty()) {
            std::filesystem::create_directories(
                output_path.parent_path());
        }

        std::ofstream out(
            output_path,
            std::ios::binary |
            std::ios::trunc);
        if (!out) {
            throw std::runtime_error(
                "cannot open benchmark output file");
        }
        out << json;

        std::cout << json;
        return 0;
    } catch (const std::exception& error) {
        std::cerr
            << "math benchmark failed: "
            << error.what()
            << "\n";
        return 1;
    }
}
