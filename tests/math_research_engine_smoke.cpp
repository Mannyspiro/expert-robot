#include "expert_robot/research/engine.hpp"

#include "expert_robot/model_formalization_proposer.hpp"
#include "expert_robot/swarm/supervisor.hpp"

#include <cassert>
#include <filesystem>
#include <string>
#include <string_view>

namespace {

class ContextProofSearcher final
    : public expert_robot::IProofSearcher {
public:
    expert_robot::SearchResult search(
        const expert_robot::SearchProblem& problem) override {
        using namespace expert_robot;

        SearchResult result;
        result.problem = problem;

        const bool helper =
            problem.statement.find(": x = x") !=
            std::string::npos;

        bool has_verified_helper = false;
        for (const auto& declaration :
             problem.context_declarations) {
            if (declaration.find(
                    "theorem MathAI.Generated.") !=
                std::string::npos) {
                has_verified_helper = true;
                break;
            }
        }

        const bool parent =
            problem.statement.find(
                ": x + 0 = x") !=
            std::string::npos;

        const bool success =
            helper ||
            (parent && has_verified_helper);

        result.attempts.push_back(
            SearchAttempt{
                .tactic = success ? "rfl" : "simp",
                .success = success,
                .exit_code = success ? 0 : 1,
                .output =
                    success
                        ? "accepted"
                        : "parent needs helper",
            });

        if (success) {
            result.success = true;
            result.tactic =
                helper ? "rfl" : "simp";
            result.proof =
                helper
                    ? "by\n  rfl"
                    : "by\n  simp";
        }

        return result;
    }
};

class SwarmBackend final
    : public expert_robot::ITextGenerationBackend {
public:
    expert_robot::TextGenerationResult generate(
        const expert_robot::TextGenerationRequest& request) override {
        if (request.user_prompt.find(
                "Critique this candidate mathematical idea independently.") !=
            std::string::npos) {
            return {
                .ok = true,
                .exit_code = 0,
                .timed_out = false,
                .output =
                    "DECISION=KEEP\nRISK=20\nCRITIQUE=worth formal testing",
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
                    "Formalize the smallest helper claim first.",
                .diagnostics = ""
            };
        }

        return {
            .ok = true,
            .exit_code = 0,
            .timed_out = false,
            .output =
                "Introduce a small identity helper and retry the parent theorem.",
            .diagnostics = ""
        };
    }
};

class FormalizationBackend final
    : public expert_robot::ITextGenerationBackend {
public:
    expert_robot::TextGenerationResult generate(
        const expert_robot::TextGenerationRequest&) override {
        return {
            .ok = true,
            .exit_code = 0,
            .timed_out = false,
            .output = R"JSON({
              "name": "candidate_identity",
              "namespace": "MathAI.Generated",
              "binders": [
                {"name": "x", "type": "ℝ"}
              ],
              "proposition": "x = x",
              "imports": ["MathAI"],
              "domain": "algebra",
              "rationale": "Small helper extracted from the research candidate."
            })JSON",
            .diagnostics = ""
        };
    }
};

} // namespace

int main() {
    using namespace expert_robot;
    using namespace expert_robot::research;

    FormalizationProposal target{
        .name = "parent",
        .name_space = "MathAI.Generated",
        .binders = {
            {"x", "ℝ"}
        },
        .proposition = "x + 0 = x",
        .imports = {"MathAI"},
        .domain = "algebra",
        .rationale = "integration test target"
    };

    FormalizationProposal helper{
        .name = "helper",
        .name_space = "MathAI.Generated",
        .binders = {
            {"x", "ℝ"}
        },
        .proposition = "x = x",
        .imports = {"MathAI"},
        .domain = "algebra",
        .rationale = "identity helper"
    };

    ContextProofSearcher searcher;

    StaticLemmaDecomposer decomposer({
        {
            target.qualified_name(),
            {helper}
        }
    });

    RecursiveLemmaFactory lemma_factory(
        searcher,
        decomposer,
        LemmaFactoryConfig{
            .max_depth = 3,
            .max_children = 4,
            .max_nodes = 16
        });

    SwarmBackend swarm_backend;
    swarm::SwarmSupervisor swarm(
        {
            {
                swarm::AgentRole::Mathematician,
                &swarm_backend
            }
        },
        swarm::SwarmLimits{
            .max_parallel_agents = 2,
            .max_total_tasks = 16,
            .max_depth = 3,
            .max_children_per_parent = 8,
            .serialize_shared_backend = true
        });

    KnowledgeGraph graph({
        TheoremNode{
            .name = target.qualified_name(),
            .source = "Target.lean",
            .status = "candidate",
            .statement = target.statement(),
            .domain = "algebra",
            .tags = {"target"}
        }
    });

    imagination::ImaginationController imagination(
        swarm,
        imagination::ImaginationConfig{
            .normal_lens_budget = 2,
            .breakthrough_lens_budget = 3,
            .skeptic_budget = 2,
            .max_expensive_candidates = 2,
            .archive_capacity_per_lens = 2,
            .minimum_imagination_drive = 0.0,
            .maximum_skeptic_risk = 65,
            .enable_synthesis = true,
            .theorem_graph_max_depth = 2,
            .theorem_graph_max_paths = 6
        },
        &graph);

    cognition::PersonalityProfile profile{
        .openness = 0.20,
        .conscientiousness = 0.95,
        .persistence = 1.00,
        .skepticism = 0.10,
        .novelty_seeking = 0.10,
        .risk_tolerance = 0.10,
        .abstraction_bias = 0.10,
        .compression_drive = 0.10
    };

    cognition::CognitionController cognition(
        profile,
        cognition::InteroceptionConfig{
            .smoothing = 1.0
        },
        cognition::NeuromodulationConfig{
            .smoothing = 1.0
        });

    FormalizationBackend formalization_backend;
    ModelFormalizationProposer formalization_proposer(
        formalization_backend);

    CandidateVerifier candidate_verifier(
        formalization_proposer,
        searcher,
        CandidateVerifierConfig{
            .max_candidates = 2
        });

    const auto episode_db =
        std::filesystem::temp_directory_path() /
        "expert-robot-research-engine-episode.sqlite3";
    const auto graph_file =
        std::filesystem::temp_directory_path() /
        "expert-robot-research-engine-graph.json";

    std::filesystem::remove(
        episode_db);
    std::filesystem::remove(
        graph_file);

    ResearchEpisodeLedger episode_ledger(
        episode_db);

    VerifiedKnowledgeConsolidator consolidator(
        graph,
        &episode_ledger,
        graph_file);

    MathResearchEngine engine(
        searcher,
        cognition,
        imagination,
        lemma_factory,
        candidate_verifier,
        consolidator,
        episode_ledger,
        MathResearchEngineConfig{
            .budget =
                ResearchBudget{
                    .max_cycles = 24,
                    .max_model_calls = 64,
                    .max_proof_attempts = 128,
                    .max_generated_ideas = 32,
                    .max_generated_lemmas = 32
                },
            .max_dispatch_steps = 32
        });

    cognition::InteroceptiveSensors sensors;
    sensors.cpu_load = 0.20;
    sensors.gpu_load = 0.20;
    sensors.ram_pressure = 0.20;
    sensors.vram_pressure = 0.20;
    sensors.context_utilization = 0.20;
    sensors.work_queue_pressure = 0.10;
    sensors.recent_proof_success_rate = 0.0;
    sensors.verified_progress = 0.0;
    sensors.expected_verified_progress = 0.20;
    sensors.theorem_novelty = 0.50;
    sensors.theorem_graph_coverage = 0.20;
    sensors.route_repetition = 0.80;
    sensors.uncertainty = 0.80;
    sensors.contradiction_rate = 0.10;
    sensors.consecutive_failures = 12;
    sensors.attempts_since_verified_progress = 20;
    sensors.seconds_since_verified_progress = 180.0;
    sensors.goal_persistence = 0.90;

    cognition::LogicalAssessment logic;
    logic.evidence_strength = 0.10;
    logic.expected_success = 0.20;
    logic.expected_information_gain = 0.20;
    logic.contradiction_risk = 0.10;
    logic.decomposition_value = 1.00;
    logic.counterexample_value = 0.10;
    logic.abstraction_value = 0.10;
    logic.compression_value = 0.10;
    logic.representation_switch_value = 0.10;
    logic.current_route_progress = 0.0;
    logic.branch_cost = 0.20;

    const auto outcome =
        engine.run(
            ResearchProblem{
                .episode_id =
                    "engine-episode-001",
                .target =
                    target,
                .focus_theorem =
                    target.qualified_name(),
                .context = {
                    "integration_test=true"
                },
                .sensors =
                    sensors,
                .logic =
                    logic,
                .evaluation_mode = false,
                .experimental_skills = {}
            });

    assert(outcome.target_verified);
    assert(outcome.target_result.has_value());
    assert(outcome.target_result->proven());
    assert(outcome.final_state.completed);
    assert(!outcome.final_state.exhausted);
    assert(!outcome.episode_root_hash.empty());

    const auto& target_node =
        graph.get(
            target.qualified_name());
    assert(target_node.status == "verified");

    const auto& helper_node =
        graph.get(
            helper.qualified_name());
    assert(helper_node.status == "verified");

    const auto uses =
        graph.related(
            target.qualified_name(),
            "USES");
    assert(!uses.empty());

    assert(
        std::filesystem::exists(
            graph_file));

    const auto lineage =
        episode_ledger.verify(
            "engine-episode-001");
    assert(lineage.valid);
    assert(lineage.event_count >= 5);
    assert(
        lineage.root_hash ==
        outcome.episode_root_hash);

    bool saw_decompose = false;
    bool saw_complete = false;

    for (const auto& transition :
         outcome.final_state.history) {
        if (transition.action ==
            ResearchAction::RunLemmaFactory) {
            saw_decompose = true;
        }
        if (transition.to ==
            ResearchPhase::Complete) {
            saw_complete = true;
        }
    }

    assert(saw_decompose);
    assert(saw_complete);

    std::filesystem::remove(
        graph_file);
    std::filesystem::remove(
        episode_db);

    return 0;
}
