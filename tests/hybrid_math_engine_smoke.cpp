#include "expert_robot/imagination/controller.hpp"
#include "expert_robot/model_lemma_decomposer.hpp"
#include "expert_robot/model_server.hpp"
#include "expert_robot/skills/math_skill.hpp"
#include "expert_robot/skills/skill_ledger.hpp"
#include "expert_robot/swarm/aggregator.hpp"
#include "expert_robot/swarm/supervisor.hpp"

#include <algorithm>
#include <atomic>
#include <cassert>
#include <chrono>
#include <filesystem>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace {

class RecordingBackend final : public expert_robot::ITextGenerationBackend {
public:
    expert_robot::TextGenerationResult generate(
        const expert_robot::TextGenerationRequest& request) override {
        {
            std::scoped_lock lock(mu_);
            prompts_.push_back(request.user_prompt);
        }

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
            const bool reject =
                request.user_prompt.find("reject_me") != std::string::npos;
            return {
                .ok = true,
                .exit_code = 0,
                .timed_out = false,
                .output = reject
                    ? "DECISION=REJECT\nRISK=90\nCRITIQUE=too weak"
                    : "DECISION=KEEP\nRISK=20\nCRITIQUE=worth testing",
                .diagnostics = ""
            };
        }

        std::string lens = "generic";
        for (const std::string candidate : {
                 "analogy", "geometry", "algebra", "duality",
                 "inversion", "generalization", "simplification",
                 "boundary_case", "spectral", "topological",
                 "counterfactual", "construction", "lemma", "lacuna"}) {
            if (request.user_prompt.find(
                    "Imagination lens: " + candidate) !=
                std::string::npos) {
                lens = candidate;
                break;
            }
        }

        return {
            .ok = true,
            .exit_code = 0,
            .timed_out = false,
            .output =
                "Candidate " + lens +
                ": use a distinct structural mechanism and test it cheaply.",
            .diagnostics = ""
        };
    }

    [[nodiscard]] bool saw(std::string_view needle) const {
        std::scoped_lock lock(mu_);
        return std::any_of(
            prompts_.begin(),
            prompts_.end(),
            [&](const std::string& prompt) {
                return prompt.find(needle) != std::string::npos;
            });
    }

private:
    mutable std::mutex mu_;
    std::vector<std::string> prompts_;
};

class ServerLikeConcurrencyBackend final : public expert_robot::ITextGenerationBackend {
public:
    expert_robot::TextGenerationResult generate(
        const expert_robot::TextGenerationRequest&) override {
        const int now = active_.fetch_add(1) + 1;
        int observed = max_active_.load();
        while (now > observed &&
               !max_active_.compare_exchange_weak(observed, now)) {}

        std::this_thread::sleep_for(
            std::chrono::milliseconds(30));

        active_.fetch_sub(1);

        return {
            .ok = true,
            .exit_code = 0,
            .timed_out = false,
            .output = "server-shared candidate",
            .diagnostics = ""
        };
    }

    [[nodiscard]] bool supports_concurrent_requests() const noexcept override {
        return true;
    }

    int max_active() const noexcept {
        return max_active_.load();
    }

private:
    std::atomic<int> active_{0};
    std::atomic<int> max_active_{0};
};

class ConcurrencyBackend final : public expert_robot::ITextGenerationBackend {
public:
    expert_robot::TextGenerationResult generate(
        const expert_robot::TextGenerationRequest&) override {
        const int now = active_.fetch_add(1) + 1;
        int observed = max_active_.load();
        while (now > observed &&
               !max_active_.compare_exchange_weak(observed, now)) {}

        std::this_thread::sleep_for(
            std::chrono::milliseconds(15));

        active_.fetch_sub(1);

        return {
            .ok = true,
            .exit_code = 0,
            .timed_out = false,
            .output = "same candidate",
            .diagnostics = ""
        };
    }

    int max_active() const noexcept {
        return max_active_.load();
    }

private:
    std::atomic<int> active_{0};
    std::atomic<int> max_active_{0};
};

expert_robot::FormalizationResult failed_formalization() {
    using namespace expert_robot;

    FormalizationProposal parent{
        .name = "parent",
        .name_space = "MathAI.Generated",
        .binders = {{"x", "ℝ"}},
        .proposition = "x + 0 = x",
        .imports = {"MathAI"},
        .domain = "algebra",
        .rationale = "parent"
    };

    SearchProblem problem;
    problem.statement = parent.statement();

    SearchResult search;
    search.problem = problem;
    search.success = false;
    search.attempts.push_back({
        .tactic = "simp",
        .success = false,
        .exit_code = 1,
        .output = "failed"
    });

    return FormalizationResult{
        .proposal = parent,
        .search = search,
        .lean_source = std::nullopt,
        .lean_declaration = std::nullopt,
        .trusted = false
    };
}

} // namespace

int main() {
    using namespace expert_robot;
    using namespace expert_robot::swarm;
    using namespace expert_robot::imagination;
    using namespace expert_robot::cognition;

    LlamaServerConfig server_config{
        .executable = "llama-server",
        .model_path = "models/math/test.gguf",
        .host = "127.0.0.1",
        .port = 18081,
        .parallel_slots = 2,
        .context_size = 8192,
        .startup_timeout_seconds = 30,
        .offline = true
    };
    validate_llama_server_config(server_config);
    LlamaServerProcess server(server_config);
    assert(!server.running());
    assert(server.server_base() == "http://127.0.0.1:18081");

    bool remote_rejected = false;
    try {
        auto invalid = server_config;
        invalid.host = "0.0.0.0";
        validate_llama_server_config(invalid);
    } catch (const std::invalid_argument&) {
        remote_rejected = true;
    }
    assert(remote_rejected);

    LlamaCliConfig server_backend_config;
    server_backend_config.server_base =
        "http://127.0.0.1:18081";
    validate_llama_cli_config(server_backend_config);
    LlamaCliBackend server_client(
        server_backend_config);
    assert(
        server_client.supports_concurrent_requests());

    LlamaCliConfig direct_backend_config;
    direct_backend_config.model_path =
        "models/math/test.gguf";
    validate_llama_cli_config(
        direct_backend_config);
    LlamaCliBackend direct_client(
        direct_backend_config);
    assert(
        !direct_client.supports_concurrent_requests());

    bool remote_backend_rejected = false;
    try {
        auto invalid_backend = server_backend_config;
        invalid_backend.server_base = "http://example.com:8080";
        validate_llama_cli_config(invalid_backend);
    } catch (const std::invalid_argument&) {
        remote_backend_rejected = true;
    }
    assert(remote_backend_rejected);

    const auto skill_catalog =
        expert_robot::skills::MathSkillCatalog::builtins();
    assert(
        skill_catalog.all().size() ==
        static_cast<std::size_t>(ImaginationLens::Count));
    assert(
        !skill_catalog.for_lens(
             ImaginationLens::Geometry).empty());
    assert(
        skill_catalog.get(
            "math.lemma.high_leverage").requires_lean_verification);
    assert(
        !skill_catalog.for_lens(ImaginationLens::Lacuna).empty());
    assert(lens_name(ImaginationLens::Lacuna) == "lacuna");
    assert(
        lens_instruction(ImaginationLens::Lacuna).find(
            "falsifiable test") != std::string::npos);

    ConcurrencyBackend concurrency_backend;
    SwarmSupervisor serialized_swarm(
        {
            {AgentRole::Mathematician, &concurrency_backend}
        },
        SwarmLimits{
            .max_parallel_agents = 4,
            .max_total_tasks = 8,
            .max_depth = 3,
            .max_children_per_parent = 6,
            .serialize_shared_backend = true
        });

    const auto serialized_results =
        serialized_swarm.run_batch({
            {
                .task_id = "a",
                .role = AgentRole::Mathematician,
                .goal = "g"
            },
            {
                .task_id = "b",
                .role = AgentRole::Analogist,
                .goal = "g"
            },
            {
                .task_id = "c",
                .role = AgentRole::Skeptic,
                .goal = "g"
            },
            {
                .task_id = "d",
                .role = AgentRole::GeometrySpecialist,
                .goal = "g"
            }
        });
    assert(serialized_results.size() == 4);
    assert(concurrency_backend.max_active() == 1);

    ServerLikeConcurrencyBackend server_like_backend;
    SwarmSupervisor concurrent_server_swarm(
        {
            {AgentRole::Mathematician, &server_like_backend}
        },
        SwarmLimits{
            .max_parallel_agents = 4,
            .max_total_tasks = 8,
            .max_depth = 3,
            .max_children_per_parent = 6,
            .serialize_shared_backend = true
        });

    const auto concurrent_results =
        concurrent_server_swarm.run_batch({
            {
                .task_id = "server-a",
                .role = AgentRole::Mathematician,
                .goal = "g"
            },
            {
                .task_id = "server-b",
                .role = AgentRole::Analogist,
                .goal = "g"
            },
            {
                .task_id = "server-c",
                .role = AgentRole::Skeptic,
                .goal = "g"
            },
            {
                .task_id = "server-d",
                .role = AgentRole::GeometrySpecialist,
                .goal = "g"
            }
        });

    assert(concurrent_results.size() == 4);
    assert(server_like_backend.max_active() >= 2);

    const auto aggregated =
        aggregate_results(serialized_results);
    assert(aggregated.size() == 1);
    assert(aggregated[0].support_count == 4);
    assert(aggregated[0].supporting_roles.size() == 4);

    RecordingBackend backend;
    SwarmSupervisor swarm(
        {
            {AgentRole::Mathematician, &backend}
        },
        SwarmLimits{
            .max_parallel_agents = 4,
            .max_total_tasks = 16,
            .max_depth = 3,
            .max_children_per_parent = 8,
            .serialize_shared_backend = true
        });

    KnowledgeGraph graph({
        {
            .name = "MathAI.Target",
            .source = "Target.lean",
            .status = "candidate",
            .statement = "target theorem",
            .domain = "analysis",
            .tags = {"target"}
        },
        {
            .name = "MathAI.Related",
            .source = "Related.lean",
            .status = "verified",
            .statement = "related invariant",
            .domain = "geometry",
            .tags = {"geometry"}
        },
        {
            .name = "MathAI.Speculative",
            .source = "Speculative.lean",
            .status = "candidate",
            .statement = "unverified speculative bridge",
            .domain = "topology",
            .tags = {"candidate"}
        }
    });
    graph.add_edge({
        .source = "MathAI.Target",
        .relation = "ANALOGOUS_TO",
        .target = "MathAI.Related"
    });
    graph.add_edge({
        .source = "MathAI.Target",
        .relation = "ANALOGOUS_TO",
        .target = "MathAI.Speculative"
    });

    const auto imagination_db =
        std::filesystem::temp_directory_path() /
        "expert-robot-hybrid-imagination.sqlite3";
    const auto skill_db =
        std::filesystem::temp_directory_path() /
        "expert-robot-hybrid-skills.sqlite3";
    std::filesystem::remove(imagination_db);
    std::filesystem::remove(skill_db);
    ImaginationMemory imagination_memory(
        imagination_db);
    expert_robot::skills::SkillLedger skill_ledger(
        skill_db);

    ImaginationController imagination(
        swarm,
        ImaginationConfig{
            .normal_lens_budget = 4,
            .breakthrough_lens_budget = 8,
            .skeptic_budget = 4,
            .max_expensive_candidates = 3,
            .archive_capacity_per_lens = 2,
            .minimum_imagination_drive = 0.18,
            .maximum_skeptic_risk = 65
        },
        &graph,
        skill_catalog,
        &imagination_memory,
        &skill_ledger);

    CognitionCycle cycle;
    cycle.interoception.state.resource_pressure = 0.10;
    cycle.interoception.state.stagnation = 0.80;
    cycle.interoception.state.novelty = 0.80;
    cycle.interoception.state.uncertainty = 0.55;
    cycle.interoception.state.route_repetition = 0.70;
    cycle.affect.exploration_drive = 0.85;
    cycle.affect.persistence_drive = 0.60;
    cycle.affect.attention_allocation = 0.70;
    cycle.affect.strategy_switch_pressure = 0.75;
    cycle.affect.compute_conservation = 0.10;
    cycle.decision.action = CognitiveAction::ExploreNovelRoute;
    cycle.decision.breakthrough_mode = false;

    LogicalAssessment logic;
    logic.expected_information_gain = 0.90;
    logic.expected_success = 0.35;
    logic.current_route_progress = 0.10;
    logic.branch_cost = 0.20;

    ImaginationRequest request{
        .request_id = "imagination-1",
        .goal = "Find a new route to prove the target theorem.",
        .context = {"current route stalled"},
        .focus_theorem = "MathAI.Target",
        .personality = math_researcher_personality(),
        .cognition = cycle,
        .logic = logic
    };

    const auto run = imagination.run(request);
    assert(!run.skipped);
    assert(run.imagination_drive >= 0.18);
    assert(run.selected_lenses.size() == 4);
    assert(run.generated.size() == 4);
    assert(!run.archive_elites.empty());
    assert(!run.shortlisted.empty());
    assert(run.shortlisted.size() <= 3);
    assert(run.synthesis_ok);
    assert(!run.synthesis.empty());
    assert(backend.saw("Synthesize the shortlisted mathematical research ideas below."));
    assert(backend.saw("Selected reusable math skill:"));
    assert(
        backend.saw(
            "verified_theorem_graph_path:"));
    assert(
        backend.saw(
            "trust=verified"));
    assert(
        backend.saw(
            "unverified_theorem_graph_path:"));
    assert(
        backend.saw(
            "trust=unverified_candidate; inspiration_only=true"));
    assert(backend.saw("Critique this candidate mathematical idea independently."));
    assert(
        imagination_memory.count() >=
        static_cast<long long>(run.generated.size()));

    for (const auto& idea : run.generated) {
        assert(!idea.skill_id.empty());
        const auto stats =
            skill_ledger.stats(idea.skill_id);
        assert(stats.attempts >= 1);
    }

    ImaginationController restored_imagination(
        swarm,
        ImaginationConfig{
            .normal_lens_budget = 4,
            .breakthrough_lens_budget = 8,
            .skeptic_budget = 4,
            .max_expensive_candidates = 3,
            .archive_capacity_per_lens = 2,
            .minimum_imagination_drive = 0.18,
            .maximum_skeptic_risk = 65
        },
        &graph,
        skill_catalog,
        &imagination_memory,
        &skill_ledger);
    assert(restored_imagination.archive().size() > 0);

    for (const auto& idea : run.generated) {
        assert(idea.novelty_score >= 0.0 &&
               idea.novelty_score <= 1.0);
        assert(idea.quality_diversity_score >= 0.0 &&
               idea.quality_diversity_score <= 1.0);
    }

    ImaginationController pressure_imagination(
        swarm,
        ImaginationConfig{
            .normal_lens_budget = 4,
            .breakthrough_lens_budget = 8,
            .minimum_lens_budget = 1,
            .skeptic_budget = 4,
            .max_expensive_candidates = 2,
            .archive_capacity_per_lens = 1,
            .minimum_imagination_drive = 0.0,
            .maximum_skeptic_risk = 65,
            .enable_synthesis = false
        },
        nullptr,
        skill_catalog,
        nullptr,
        nullptr);

    auto pressured_cycle = cycle;
    pressured_cycle.interoception.state.resource_pressure = 0.85;
    pressured_cycle.affect.compute_conservation = 0.85;
    pressured_cycle.decision.action =
        CognitiveAction::ExploreNovelRoute;
    pressured_cycle.decision.breakthrough_mode = false;

    const auto pressured_run =
        pressure_imagination.run(
            ImaginationRequest{
                .request_id = "pressure-budget",
                .goal = "Explore under high resource pressure.",
                .context = {},
                .focus_theorem = "",
                .personality =
                    math_researcher_personality(),
                .cognition = pressured_cycle,
                .logic = logic
            });

    assert(pressured_run.selected_lenses.size() == 1);

    auto conserve_cycle = cycle;
    conserve_cycle.decision.action =
        CognitiveAction::ConserveCompute;

    const auto conserve_run =
        pressure_imagination.run(
            ImaginationRequest{
                .request_id = "conserve-budget",
                .goal = "Use minimum exploration budget.",
                .context = {},
                .focus_theorem = "",
                .personality =
                    math_researcher_personality(),
                .cognition = conserve_cycle,
                .logic = logic
            });

    assert(conserve_run.selected_lenses.size() == 1);

    // Skill selection learns from downstream evidence without changing
    // verification authority. Two qualified skills compete in the same lens.
    expert_robot::skills::MathSkill good_skill{
        .skill_id = "math.test.simplify.good",
        .title = "Good simplifier",
        .lens = ImaginationLens::Simplification,
        .preferred_role = AgentRole::Mathematician,
        .procedure = "Use the empirically successful simplification route.",
        .requires_lean_verification = true,
        .stage = expert_robot::skills::SkillStage::Qualified
    };
    expert_robot::skills::MathSkill weak_skill{
        .skill_id = "math.test.simplify.weak",
        .title = "Weak simplifier",
        .lens = ImaginationLens::Simplification,
        .preferred_role = AgentRole::Mathematician,
        .procedure = "Use the historically weak simplification route.",
        .requires_lean_verification = true,
        .stage = expert_robot::skills::SkillStage::Qualified
    };

    for (int i = 0; i < 4; ++i) {
        skill_ledger.record_generation(
            good_skill.skill_id,
            true,
            true);
        skill_ledger.record_downstream(
            good_skill.skill_id,
            true);

        skill_ledger.record_generation(
            weak_skill.skill_id,
            true,
            true);
        skill_ledger.record_downstream(
            weak_skill.skill_id,
            false);
    }

    expert_robot::skills::MathSkillCatalog adaptive_catalog(
        {good_skill, weak_skill});

    auto adaptive_cycle = cycle;
    adaptive_cycle.decision.action =
        CognitiveAction::CompressSimplify;
    adaptive_cycle.decision.breakthrough_mode =
        false;

    ImaginationController adaptive_imagination(
        swarm,
        ImaginationConfig{
            .normal_lens_budget = 1,
            .breakthrough_lens_budget = 1,
            .skeptic_budget = 1,
            .max_expensive_candidates = 1,
            .archive_capacity_per_lens = 1,
            .minimum_imagination_drive = 0.0,
            .maximum_skeptic_risk = 65,
            .enable_synthesis = false
        },
        nullptr,
        adaptive_catalog,
        nullptr,
        &skill_ledger);

    const auto adaptive_run =
        adaptive_imagination.run(
            ImaginationRequest{
                .request_id = "adaptive-skill-1",
                .goal = "Simplify a stalled proof route.",
                .context = {},
                .focus_theorem = "",
                .personality =
                    math_researcher_personality(),
                .cognition = adaptive_cycle,
                .logic = logic
            });

    assert(adaptive_run.generated.size() == 1);
    assert(
        adaptive_run.generated.front().lens ==
        ImaginationLens::Simplification);
    assert(
        adaptive_run.generated.front().skill_id ==
        good_skill.skill_id);
    assert(
        backend.saw(
            "math.test.simplify.good"));

    ModelLemmaDecomposer model_decomposer(
        backend,
        ModelLemmaDecomposerConfig{
            .max_children = 2
        });

    const auto failed = failed_formalization();
    const auto helpers =
        model_decomposer.decompose(
            failed.proposal,
            failed);
    assert(helpers.size() == 1);
    assert(
        helpers[0].qualified_name() ==
        "MathAI.Generated.generated_helper");
    assert(helpers[0].proposition == "x = x");

    std::filesystem::remove(imagination_db);
    std::filesystem::remove(skill_db);
    return 0;
}
