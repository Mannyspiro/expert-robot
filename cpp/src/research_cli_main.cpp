#include "expert_robot/app/math_research_service.hpp"
#include "expert_robot/model_formalization_proposer.hpp"
#include "expert_robot/model_server.hpp"
#include "expert_robot/proof_search.hpp"
#include "expert_robot/protocol.hpp"
#include "expert_robot/text_generation.hpp"
#include "expert_robot/research/state_machine.hpp"

#include <filesystem>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {

struct Options {
    std::filesystem::path repo_root{"."};
    std::filesystem::path state_dir{"state/research-cli"};
    std::filesystem::path model;
    std::filesystem::path llama_cli{"llama-cli"};
    std::filesystem::path llama_server;
    std::string claim;
    std::string domain{"unknown"};
    std::string name_hint{"research_target"};
    int server_port{8081};
};

[[noreturn]] void usage() {
    throw std::invalid_argument(
        "usage: expert_robot_research --model MODEL.gguf --claim TEXT "
        "[--repo-root DIR] [--state-dir DIR] [--domain NAME] "
        "[--name-hint NAME] [--llama-cli PATH] "
        "[--llama-server PATH] [--server-port PORT]");
}

Options parse_args(int argc, char** argv) {
    Options o;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto value = [&]() -> std::string {
            if (i + 1 >= argc) usage();
            return argv[++i];
        };
        if (arg == "--model") o.model = value();
        else if (arg == "--claim") o.claim = value();
        else if (arg == "--repo-root") o.repo_root = value();
        else if (arg == "--state-dir") o.state_dir = value();
        else if (arg == "--domain") o.domain = value();
        else if (arg == "--name-hint") o.name_hint = value();
        else if (arg == "--llama-cli") o.llama_cli = value();
        else if (arg == "--llama-server") o.llama_server = value();
        else if (arg == "--server-port") o.server_port = std::stoi(value());
        else usage();
    }
    if (o.model.empty() || o.claim.empty()) usage();
    if (o.server_port <= 0 || o.server_port > 65535) {
        throw std::invalid_argument("server port must be in 1..65535");
    }
    return o;
}

expert_robot::LlamaCliConfig backend_config(
    const Options& o,
    const std::string& server_base,
    const std::filesystem::path& schema,
    int max_tokens,
    double temperature) {
    expert_robot::LlamaCliConfig c;
    c.executable = o.llama_cli;
    if (server_base.empty()) {
        c.model_path = o.model;
    } else {
        c.server_base = server_base;
    }
    c.json_schema_path = schema;
    c.max_tokens = max_tokens;
    c.temperature = temperature;
    c.top_p = 0.90;
    c.seed = 1;
    c.timeout_seconds = 180;
    c.max_output_bytes = 262144;
    c.max_diagnostic_bytes = 32768;
    return c;
}

expert_robot::cognition::InteroceptiveSensors default_sensors() {
    expert_robot::cognition::InteroceptiveSensors s;
    s.cpu_load = 0.10;
    s.gpu_load = 0.10;
    s.ram_pressure = 0.10;
    s.vram_pressure = 0.10;
    s.context_utilization = 0.10;
    s.work_queue_pressure = 0.10;
    s.recent_proof_success_rate = 0.0;
    s.verified_progress = 0.0;
    s.expected_verified_progress = 0.30;
    s.theorem_novelty = 0.75;
    s.theorem_graph_coverage = 0.25;
    s.route_repetition = 0.0;
    s.uncertainty = 0.80;
    s.contradiction_rate = 0.0;
    s.consecutive_failures = 0;
    s.attempts_since_verified_progress = 0;
    s.seconds_since_verified_progress = 0.0;
    s.goal_persistence = 0.90;
    return s;
}

expert_robot::cognition::LogicalAssessment default_logic() {
    expert_robot::cognition::LogicalAssessment x;
    x.evidence_strength = 0.10;
    x.expected_success = 0.30;
    x.expected_information_gain = 0.80;
    x.contradiction_risk = 0.10;
    x.decomposition_value = 0.70;
    x.counterexample_value = 0.50;
    x.abstraction_value = 0.65;
    x.compression_value = 0.45;
    x.representation_switch_value = 0.75;
    x.current_route_progress = 0.0;
    x.branch_cost = 0.25;
    return x;
}

std::string outcome_json(
    const expert_robot::research::ResearchOutcome& out) {
    const auto& usage = out.final_state.usage;
    std::string declaration;
    if (out.target_result.has_value() &&
        out.target_result->lean_declaration.has_value()) {
        declaration = *out.target_result->lean_declaration;
    }

    std::string result = "{";
    result += "\"schema_version\":1,";
    result += "\"target_verified\":" +
        std::string(out.target_verified ? "true" : "false") + ",";
    result += "\"final_phase\":\"" +
        expert_robot::json_escape(
            std::string(expert_robot::research::research_phase_name(
                out.final_state.phase))) + "\",";
    result += "\"completed\":" +
        std::string(out.final_state.completed ? "true" : "false") + ",";
    result += "\"exhausted\":" +
        std::string(out.final_state.exhausted ? "true" : "false") + ",";
    result += "\"usage\":{";
    result += "\"cycles\":" + std::to_string(usage.cycles) + ",";
    result += "\"model_calls\":" + std::to_string(usage.model_calls) + ",";
    result += "\"proof_attempts\":" + std::to_string(usage.proof_attempts) + ",";
    result += "\"generated_ideas\":" + std::to_string(usage.generated_ideas) + ",";
    result += "\"generated_lemmas\":" + std::to_string(usage.generated_lemmas);
    result += "},";
    result += "\"episode_root_hash\":\"" +
        expert_robot::json_escape(out.episode_root_hash) + "\",";
    result += "\"lean_declaration\":\"" +
        expert_robot::json_escape(declaration) + "\"";
    result += "}";
    return result;
}

} // namespace

int main(int argc, char** argv) {
    try {
        const Options o = parse_args(argc, argv);
        const auto repo = std::filesystem::absolute(o.repo_root);
        const auto formal_root = repo / "formal";
        const auto formal_schema =
            repo / "config/schemas/formalization_proposal.schema.json";
        const auto lemma_schema =
            repo / "config/schemas/lemma_decomposition.schema.json";

        if (!std::filesystem::exists(o.model)) {
            throw std::invalid_argument("model file does not exist");
        }
        if (!std::filesystem::exists(formal_root / "lakefile.toml")) {
            throw std::invalid_argument("repo-root does not contain formal/lakefile.toml");
        }

        std::unique_ptr<expert_robot::LlamaServerProcess> server;
        std::string server_base;
        if (!o.llama_server.empty()) {
            expert_robot::LlamaServerConfig sc;
            sc.executable = o.llama_server;
            sc.model_path = o.model;
            sc.host = "127.0.0.1";
            sc.port = o.server_port;
            sc.parallel_slots = 2;
            sc.context_size = 8192;
            sc.startup_timeout_seconds = 120;
            sc.offline = true;
            server = std::make_unique<expert_robot::LlamaServerProcess>(sc);
            server->start();
            server_base = server->server_base();
        }

        expert_robot::LlamaCliBackend freeform(
            backend_config(o, server_base, {}, 1024, 0.25));
        expert_robot::LlamaCliBackend lemma(
            backend_config(o, server_base, lemma_schema, 1024, 0.10));
        expert_robot::LlamaCliBackend formal(
            backend_config(o, server_base, formal_schema, 1024, 0.05));

        expert_robot::LeanSubprocessRunner lean(formal_root, 20);

        expert_robot::ModelFormalizationProposer intake(formal);
        const auto proposed = intake.propose(
            expert_robot::InformalFormalizationRequest{
                .name_hint = o.name_hint,
                .name_space = "MathAI.Generated",
                .informal_claim = o.claim,
                .domain = o.domain,
                .imports = {"MathAI"},
                .context = {
                    "Use only the supplied mathematical claim and non-evaluation context.",
                    "Do not assume any validation or holdout target."
                }
            });

        expert_robot::app::MathResearchServiceConfig config;
        config.state_dir = o.state_dir;
        config.proof_search_config = repo / "config/proof_search.json";
        config.theorem_registry = repo / "formal/theorem_registry.json";
        config.theorem_graph_path = o.state_dir / "theorem_graph.json";
        config.swarm_limits.max_parallel_agents = 2;
        config.imagination.normal_lens_budget = 3;
        config.imagination.breakthrough_lens_budget = 5;
        config.imagination.skeptic_budget = 4;
        config.imagination.max_expensive_candidates = 2;
        config.lemma_factory.max_depth = 3;
        config.lemma_factory.max_children = 4;
        config.lemma_factory.max_nodes = 24;
        config.research_engine.budget =
            expert_robot::research::ResearchBudget{
                .max_cycles = 32,
                .max_model_calls = 64,
                .max_proof_attempts = 128,
                .max_generated_ideas = 48,
                .max_generated_lemmas = 48,
            };
        config.research_engine.max_dispatch_steps = 48;
        config.research_engine.learning_writes = true;

        expert_robot::app::MathResearchService service(
            lean, freeform, lemma, formal, config);

        const auto outcome = service.run(
            expert_robot::research::ResearchProblem{
                .episode_id = "cli-" + o.name_hint,
                .target = proposed.proposal,
                .focus_theorem = proposed.proposal.qualified_name(),
                .context = {
                    "intake_claim=" + o.claim,
                    "domain=" + o.domain
                },
                .sensors = default_sensors(),
                .logic = default_logic(),
                .evaluation_mode = false,
                .experimental_skills = {}
            });

        std::cout << outcome_json(outcome) << std::endl;
        return outcome.target_verified ? 0 : 3;
    } catch (const std::exception& e) {
        std::cerr
            << "{\"ok\":false,\"error\":\""
            << expert_robot::json_escape(e.what())
            << "\"}" << std::endl;
        return 2;
    }
}
