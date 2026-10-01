#include "expert_robot/model_formalization_proposer.hpp"
#include "expert_robot/research/engine.hpp"
#include "expert_robot/skills/skill_ledger.hpp"
#include "expert_robot/swarm/supervisor.hpp"

#include <cassert>
#include <filesystem>
#include <string_view>

namespace {

class FeedbackSearcher final : public expert_robot::IProofSearcher {
public:
    expert_robot::SearchResult search(
        const expert_robot::SearchProblem& problem) override {
        using namespace expert_robot;

        SearchResult result;
        result.problem = problem;

        const bool helper =
            problem.statement.find(": x = x") !=
            std::string::npos;

        bool has_helper = false;
        for (const auto& declaration :
             problem.context_declarations) {
            if (declaration.find(
                    "theorem MathAI.Generated.") !=
                std::string::npos) {
                has_helper = true;
                break;
            }
        }

        const bool parent =
            problem.statement.find(
                ": x + 0 = x") !=
            std::string::npos;

        const bool success =
            helper ||
            (parent && has_helper);

        result.attempts.push_back(
            SearchAttempt{
                .tactic = success ? "rfl" : "simp",
                .success = success,
                .exit_code = success ? 0 : 1,
                .output =
                    success
                        ? "accepted"
                        : "needs verified helper",
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

class FeedbackSwarmBackend final
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
                    "DECISION=KEEP\n"
                    "RISK=10\n"
                    "CRITIQUE=cheap helper route",
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
                    "Formalize the identity helper first.",
                .diagnostics = ""
            };
        }

        return {
            .ok = true,
            .exit_code = 0,
            .timed_out = false,
            .output =
                "Use a structural analogy to isolate the identity helper x = x.",
            .diagnostics = ""
        };
    }
};

class FeedbackFormalizationBackend final
    : public expert_robot::ITextGenerationBackend {
public:
    expert_robot::TextGenerationResult generate(
        const expert_robot::TextGenerationRequest&) override {
        return {
            .ok = true,
            .exit_code = 0,
            .timed_out = false,
            .output = R"JSON({
              "name": "feedback_identity",
              "namespace": "MathAI.Generated",
              "binders": [
                {"name": "x", "type": "ℝ"}
              ],
              "proposition": "x = x",
              "imports": ["MathAI"],
              "domain": "algebra",
              "rationale": "Verified helper generated from an imagination candidate."
            })JSON",
            .diagnostics = ""
        };
    }
};

} // namespace

int main() {
    using namespace expert_robot;
    using namespace expert_robot::research;

    const auto temp =
        std::filesystem::temp_directory_path() /
        "expert-robot-skill-feedback-smoke";
    std::filesystem::remove_all(temp);
    std::filesystem::create_directories(temp);

    const auto skill_db =
        temp / "skills.sqlite3";
    const auto episode_db =
        temp / "episodes.sqlite3";
    const auto graph_file =
        temp / "graph.json";

    FormalizationProposal target{
        .name = "feedback_parent",
        .name_space = "MathAI.Generated",
        .binders = {{"x", "ℝ"}},
        .proposition = "x + 0 = x",
        .imports = {"MathAI"},
        .domain = "algebra",
        .rationale = "skill attribution integration target"
    };

    FeedbackSearcher searcher;

    StaticLemmaDecomposer no_decomposition({});
    RecursiveLemmaFactory lemma_factory(
        searcher,
        no_decomposition,
        LemmaFactoryConfig{
            .max_depth = 2,
            .max_children = 2,
            .max_nodes = 8
        });

    FeedbackSwarmBackend swarm_backend;
    swarm::SwarmSupervisor swarm(
        {
            {
                swarm::AgentRole::Mathematician,
                &swarm_backend
            }
        },
        swarm::SwarmLimits{
            .max_parallel_agents = 2,
            .max_total_tasks = 8,
            .max_depth = 2,
            .max_children_per_parent = 4,
            .serialize_shared_backend = true
        });

    KnowledgeGraph graph({
        TheoremNode{
            .name = target.qualified_name(),
            .source = "FeedbackTarget.lean",
            .status = "candidate",
            .statement = target.statement(),
            .domain = "algebra",
            .tags = {"target"}
        }
    });

    skills::SkillLedger skill_ledger(
        skill_db);

    imagination::ImaginationController imagination(
        swarm,
        imagination::ImaginationConfig{
            .normal_lens_budget = 1,
            .breakthrough_lens_budget = 1,
            .skeptic_budget = 1,
            .max_expensive_candidates = 1,
            .archive_capacity_per_lens = 1,
            .minimum_imagination_drive = 0.0,
            .maximum_skeptic_risk = 65,
            .enable_synthesis = false,
            .theorem_graph_max_depth = 2,
            .theorem_graph_max_paths = 4
        },
        &graph,
        skills::MathSkillCatalog::builtins(),
        nullptr,
        &skill_ledger);

    cognition::PersonalityProfile profile{
        .openness = 1.00,
        .conscientiousness = 0.20,
        .persistence = 0.10,
        .skepticism = 0.10,
        .novelty_seeking = 1.00,
        .risk_tolerance = 0.80,
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

    FeedbackFormalizationBackend formalization_backend;
    ModelFormalizationProposer proposer(
        formalization_backend);

    CandidateVerifier verifier(
        proposer,
        searcher,
        CandidateVerifierConfig{
            .max_candidates = 1
        });

    ResearchEpisodeLedger episode_ledger(
        episode_db);

    VerifiedKnowledgeConsolidator consolidator(
        graph,
        &episode_ledger,
        graph_file);

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
    sensors.theorem_novelty = 0.95;
    sensors.theorem_graph_coverage = 0.10;
    sensors.route_repetition = 0.95;
    sensors.uncertainty = 0.80;
    sensors.contradiction_rate = 0.05;
    sensors.consecutive_failures = 10;
    sensors.attempts_since_verified_progress = 16;
    sensors.seconds_since_verified_progress = 180.0;
    sensors.goal_persistence = 0.50;

    cognition::LogicalAssessment logic;
    logic.evidence_strength = 0.10;
    logic.expected_success = 0.10;
    logic.expected_information_gain = 1.00;
    logic.contradiction_risk = 0.05;
    logic.decomposition_value = 0.05;
    logic.counterexample_value = 0.05;
    logic.abstraction_value = 0.05;
    logic.compression_value = 0.05;
    logic.representation_switch_value = 0.05;
    logic.current_route_progress = 0.0;
    logic.branch_cost = 0.10;

    const auto predicted =
        cognition.step(
            sensors,
            logic);
    assert(
        predicted.decision.action ==
        cognition::CognitiveAction::ExploreNovelRoute);

    MathResearchEngine engine(
        searcher,
        cognition,
        imagination,
        lemma_factory,
        verifier,
        consolidator,
        episode_ledger,
        MathResearchEngineConfig{
            .budget =
                ResearchBudget{
                    .max_cycles = 20,
                    .max_model_calls = 32,
                    .max_proof_attempts = 64,
                    .max_generated_ideas = 16,
                    .max_generated_lemmas = 16
                },
            .max_dispatch_steps = 24
        },
        nullptr,
        nullptr,
        &skill_ledger);

    const auto outcome =
        engine.run(
            ResearchProblem{
                .episode_id =
                    "skill-feedback-episode",
                .target = target,
                .focus_theorem =
                    target.qualified_name(),
                .context = {},
                .sensors = sensors,
                .logic = logic,
                .evaluation_mode = false,
                .experimental_skills = {}
            });

    assert(outcome.target_verified);
    assert(outcome.last_imagination.has_value());
    assert(
        outcome.last_imagination->
            generated.size() == 1);

    const auto& idea =
        outcome.last_imagination->
            generated.front();

    assert(
        idea.lens ==
        imagination::ImaginationLens::Analogy);
    assert(
        idea.skill_id ==
        "math.analogy.transfer");

    const auto stats =
        skill_ledger.stats(
            idea.skill_id);

    assert(stats.attempts == 1);
    assert(stats.skeptic_passes == 1);
    assert(stats.shortlisted == 1);
    assert(stats.downstream_verified == 1);
    assert(stats.downstream_failed == 0);
    assert(stats.verified_rate() == 1.0);

    std::filesystem::remove_all(temp);
    return 0;
}
