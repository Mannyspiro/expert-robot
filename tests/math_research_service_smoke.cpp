#include "expert_robot/app/math_research_service.hpp"

#include <cassert>
#include <filesystem>
#include <string_view>

namespace {

class ServiceLeanRunner final
    : public expert_robot::ILeanRunner {
public:
    expert_robot::LeanRunResult run(
        std::string_view source) override {
        const bool helper_goal =
            source.find(
                ": x = x") !=
            std::string_view::npos;

        const bool parent_goal =
            source.find(
                ": x + 0 = x") !=
            std::string_view::npos;

        const bool has_helper =
            source.find(
                "MathAI.Generated.generated_helper") !=
            std::string_view::npos;

        if (helper_goal ||
            (parent_goal && has_helper)) {
            return {
                0,
                "accepted"
            };
        }

        return {
            1,
            "needs helper"
        };
    }
};

class ServiceBackend final
    : public expert_robot::ITextGenerationBackend {
public:
    expert_robot::TextGenerationResult generate(
        const expert_robot::TextGenerationRequest& request) override {
        if (request.user_prompt.find(
                "A Lean theorem candidate failed deterministic proof search.") !=
            std::string::npos) {
            return {
                .ok = true,
                .exit_code = 0,
                .timed_out = false,
                .output = R"JSON({
                  "lemmas": [{
                    "name": "generated_helper",
                    "namespace": "MathAI.Generated",
                    "binders": [{"name": "x", "type": "ℝ"}],
                    "proposition": "x = x",
                    "imports": ["MathAI"],
                    "domain": "algebra",
                    "rationale": "identity helper"
                  }]
                })JSON",
                .diagnostics = ""
            };
        }

        if (request.user_prompt.find(
                "Critique this candidate mathematical idea independently.") !=
            std::string::npos) {
            return {
                .ok = true,
                .exit_code = 0,
                .timed_out = false,
                .output =
                    "DECISION=KEEP\n"
                    "RISK=20\n"
                    "CRITIQUE=worth checking",
                .diagnostics = ""
            };
        }

        if (request.user_prompt.find(
                "Synthesize the shortlisted mathematical research ideas below.") !=
            std::string::npos) {
            return {
                .ok = true,
                .exit_code = 0,
                .timed_out = false,
                .output =
                    "Prefer the cheapest formally testable route.",
                .diagnostics = ""
            };
        }

        if (request.user_prompt.find(
                "formalization") !=
            std::string::npos ||
            request.user_prompt.find(
                "Lean theorem statement") !=
            std::string::npos) {
            return {
                .ok = true,
                .exit_code = 0,
                .timed_out = false,
                .output = R"JSON({
                  "name": "candidate_identity",
                  "namespace": "MathAI.Generated",
                  "binders": [{"name": "x", "type": "ℝ"}],
                  "proposition": "x = x",
                  "imports": ["MathAI"],
                  "domain": "algebra",
                  "rationale": "small formal helper"
                })JSON",
                .diagnostics = ""
            };
        }

        return {
            .ok = true,
            .exit_code = 0,
            .timed_out = false,
            .output =
                "Try a small identity lemma before retrying the parent.",
            .diagnostics = ""
        };
    }
};

} // namespace

int main() {
    using namespace expert_robot;
    using namespace expert_robot::app;
    using namespace expert_robot::research;

    const auto temp =
        std::filesystem::temp_directory_path() /
        "expert-robot-math-service-smoke";
    std::filesystem::remove_all(temp);
    std::filesystem::create_directories(temp);

    const auto graph_path =
        temp / "theorem_graph.json";

    ServiceLeanRunner lean;
    ServiceBackend backend;

    MathResearchServiceConfig config;
    config.state_dir =
        temp / "state";
    config.proof_search_config =
        "config/proof_search.json";
    config.theorem_registry =
        "formal/theorem_registry.json";
    config.theorem_graph_path =
        graph_path;

    config.personality =
        cognition::PersonalityProfile{
            .openness = 0.20,
            .conscientiousness = 0.98,
            .persistence = 1.00,
            .skepticism = 0.30,
            .novelty_seeking = 0.15,
            .risk_tolerance = 0.10,
            .abstraction_bias = 0.20,
            .compression_drive = 0.30
        };

    config.interoception.smoothing = 1.0;
    config.neuromodulation.smoothing = 1.0;
    config.swarm_limits.max_parallel_agents = 2;
    config.imagination.normal_lens_budget = 2;
    config.imagination.breakthrough_lens_budget = 3;
    config.imagination.skeptic_budget = 2;
    config.imagination.max_expensive_candidates = 2;
    config.imagination.minimum_imagination_drive = 0.0;
    config.lemma_factory.max_depth = 3;
    config.lemma_factory.max_children = 4;
    config.lemma_factory.max_nodes = 16;
    config.research_engine.budget =
        ResearchBudget{
            .max_cycles = 24,
            .max_model_calls = 64,
            .max_proof_attempts = 128,
            .max_generated_ideas = 32,
            .max_generated_lemmas = 32
        };
    config.research_engine.max_dispatch_steps = 32;

    MathResearchService service(
        lean,
        backend,
        backend,
        backend,
        config);

    assert(
        service.graph().get(
            "MathAI.Trust.add_zero_verified").status ==
        "verified");
    assert(
        service.graph().get(
            "MathAI.Geometry.origin_on_xy_plane").status ==
        "verified");

    FormalizationProposal target{
        .name = "service_parent",
        .name_space = "MathAI.Generated",
        .binders = {
            {"x", "ℝ"}
        },
        .proposition = "x + 0 = x",
        .imports = {"MathAI"},
        .domain = "algebra",
        .rationale =
            "composition-root integration target"
    };

    cognition::InteroceptiveSensors sensors;
    sensors.cpu_load = 0.2;
    sensors.gpu_load = 0.2;
    sensors.ram_pressure = 0.2;
    sensors.vram_pressure = 0.2;
    sensors.context_utilization = 0.2;
    sensors.work_queue_pressure = 0.1;
    sensors.recent_proof_success_rate = 0.0;
    sensors.verified_progress = 0.0;
    sensors.expected_verified_progress = 0.2;
    sensors.theorem_novelty = 0.5;
    sensors.theorem_graph_coverage = 0.2;
    sensors.route_repetition = 0.9;
    sensors.uncertainty = 0.8;
    sensors.contradiction_rate = 0.1;
    sensors.consecutive_failures = 12;
    sensors.attempts_since_verified_progress = 20;
    sensors.seconds_since_verified_progress = 180.0;
    sensors.goal_persistence = 0.95;

    cognition::LogicalAssessment logic;
    logic.evidence_strength = 0.10;
    logic.expected_success = 0.20;
    logic.expected_information_gain = 0.30;
    logic.contradiction_risk = 0.10;
    logic.decomposition_value = 1.00;
    logic.counterexample_value = 0.10;
    logic.abstraction_value = 0.10;
    logic.compression_value = 0.20;
    logic.representation_switch_value = 0.10;
    logic.current_route_progress = 0.0;
    logic.branch_cost = 0.20;

    const auto outcome =
        service.run(
            ResearchProblem{
                .episode_id =
                    "service-episode-001",
                .target = target,
                .focus_theorem =
                    target.qualified_name(),
                .context = {
                    "service_smoke=true"
                },
                .sensors = sensors,
                .logic = logic,
                .evaluation_mode = false,
                .experimental_skills = {}
            });

    assert(outcome.target_verified);
    assert(outcome.target_result.has_value());
    assert(outcome.target_result->proven());
    assert(outcome.final_state.completed);
    assert(outcome.dispatched_route.has_value());
    assert(!outcome.episode_root_hash.empty());

    assert(
        std::filesystem::exists(
            config.state_dir /
            "proof_memory.sqlite3"));
    assert(
        std::filesystem::exists(
            config.state_dir /
            "imagination.sqlite3"));
    assert(
        std::filesystem::exists(
            config.state_dir /
            "route_memory.sqlite3"));
    assert(
        std::filesystem::exists(
            config.state_dir /
            "skill_ledger.sqlite3"));
    assert(
        std::filesystem::exists(
            config.state_dir /
            "research_episodes.sqlite3"));
    assert(
        std::filesystem::exists(
            graph_path));

    const auto exp =
        service.route_memory().experience(
            outcome.dispatched_route->kind,
            "algebra");
    assert(exp.attempts >= 1);
    assert(exp.target_verifications >= 1);

    const auto& verified =
        service.graph().get(
            target.qualified_name());
    assert(verified.status == "verified");

    std::filesystem::remove_all(temp);
    return 0;
}
