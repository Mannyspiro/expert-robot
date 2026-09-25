#include "expert_robot/cognition/controller.hpp"
#include "expert_robot/imagination/controller.hpp"
#include "expert_robot/lemma_factory.hpp"
#include "expert_robot/research/candidate_verifier.hpp"
#include "expert_robot/research/engine.hpp"
#include "expert_robot/research/episode_ledger.hpp"
#include "expert_robot/research/knowledge_consolidator.hpp"
#include "expert_robot/research/route_memory.hpp"
#include "expert_robot/research/route_planner.hpp"
#include "expert_robot/research/strategy_planner.hpp"
#include "expert_robot/swarm/supervisor.hpp"

#include <cassert>
#include <filesystem>

namespace {

class TwoPassSearcher final
    : public expert_robot::IProofSearcher {
public:
    expert_robot::SearchResult search(
        const expert_robot::SearchProblem& problem) override {
        using namespace expert_robot;

        SearchResult result;
        result.problem = problem;
        ++calls;

        if (calls == 1) {
            result.attempts.push_back(
                SearchAttempt{
                    .tactic = "simp",
                    .success = false,
                    .exit_code = 1,
                    .output = "first direct attempt intentionally fails"
                });
            return result;
        }

        result.success = true;
        result.tactic = "trivial";
        result.proof = "by\n  trivial";
        result.attempts.push_back(
            SearchAttempt{
                .tactic = "trivial",
                .success = true,
                .exit_code = 0,
                .output = "accepted on structured retry"
            });
        return result;
    }

    int calls{0};
};

class NoModelBackend final
    : public expert_robot::ITextGenerationBackend {
public:
    expert_robot::TextGenerationResult generate(
        const expert_robot::TextGenerationRequest&) override {
        ++calls;
        return {
            .ok = false,
            .exit_code = 1,
            .timed_out = false,
            .output = {},
            .diagnostics = "model should not be called"
        };
    }

    int calls{0};
};

} // namespace

int main() {
    using namespace expert_robot;
    using namespace expert_robot::research;

    const auto root =
        std::filesystem::temp_directory_path() /
        "expert-robot-complete-strategy";
    std::filesystem::remove_all(root);
    std::filesystem::create_directories(root);

    FormalizationProposal target{
        .name = "strategy_target",
        .name_space = "MathAI.Generated",
        .binders = {},
        .proposition = "True",
        .imports = {"MathAI"},
        .domain = "logic",
        .rationale = "complete strategy smoke target"
    };

    KnowledgeGraph graph({
        TheoremNode{
            .name = target.qualified_name(),
            .source = "Target.lean",
            .status = "candidate",
            .statement = target.statement(),
            .domain = "logic",
            .tags = {"target"}
        }
    });

    TwoPassSearcher searcher;

    NoModelBackend backend;
    swarm::SwarmSupervisor swarm(
        {
            {
                swarm::AgentRole::Mathematician,
                &backend
            }
        },
        swarm::SwarmLimits{
            .max_parallel_agents = 1,
            .max_total_tasks = 4,
            .max_depth = 2,
            .max_children_per_parent = 2,
            .serialize_shared_backend = true
        });

    imagination::ImaginationController imagination(
        swarm,
        imagination::ImaginationConfig{
            .normal_lens_budget = 1,
            .breakthrough_lens_budget = 1,
            .minimum_lens_budget = 1,
            .skeptic_budget = 1,
            .max_expensive_candidates = 1,
            .archive_capacity_per_lens = 1,
            .minimum_imagination_drive = 0.0,
            .maximum_skeptic_risk = 65,
            .enable_synthesis = false
        },
        &graph);

    StaticLemmaDecomposer decomposer({});
    RecursiveLemmaFactory lemma_factory(
        searcher,
        decomposer,
        LemmaFactoryConfig{
            .max_depth = 1,
            .max_children = 1,
            .max_nodes = 2
        });

    cognition::CognitionController cognition(
        cognition::PersonalityProfile{
            .openness = 0.10,
            .conscientiousness = 0.95,
            .persistence = 0.95,
            .skepticism = 0.30,
            .novelty_seeking = 0.05,
            .risk_tolerance = 0.05,
            .abstraction_bias = 0.05,
            .compression_drive = 0.90
        },
        cognition::InteroceptionConfig{
            .smoothing = 1.0
        },
        cognition::NeuromodulationConfig{
            .smoothing = 1.0
        });

    ModelFormalizationProposer proposer(
        backend);
    CandidateVerifier verifier(
        proposer,
        searcher,
        CandidateVerifierConfig{
            .max_candidates = 1
        });

    ResearchEpisodeLedger ledger(
        root / "episodes.sqlite3");
    VerifiedKnowledgeConsolidator consolidator(
        graph,
        &ledger,
        root / "graph.json");

    RouteOutcomeLedger memory(
        root / "routes.sqlite3");

    RoutePlannerConfig route_config;
    route_config.max_output_routes = 4;
    route_config.max_route_sequences = 4;

    ProofRoutePlanner route_planner(
        graph,
        route_config,
        &memory);

    ResearchStrategyPlanner strategy_planner(
        ResearchStrategyPlannerConfig{},
        &memory);

    MathResearchEngine engine(
        searcher,
        cognition,
        imagination,
        lemma_factory,
        verifier,
        consolidator,
        ledger,
        MathResearchEngineConfig{
            .budget =
                ResearchBudget{
                    .max_cycles = 12,
                    .max_model_calls = 8,
                    .max_proof_attempts = 24,
                    .max_generated_ideas = 8,
                    .max_generated_lemmas = 8
                },
            .max_dispatch_steps = 12
        },
        &route_planner,
        &memory,
        nullptr,
        &strategy_planner);

    cognition::InteroceptiveSensors sensors;
    sensors.cpu_load = 0.10;
    sensors.gpu_load = 0.10;
    sensors.ram_pressure = 0.10;
    sensors.vram_pressure = 0.10;
    sensors.context_utilization = 0.10;
    sensors.work_queue_pressure = 0.10;
    sensors.recent_proof_success_rate = 0.0;
    sensors.verified_progress = 0.0;
    sensors.expected_verified_progress = 0.5;
    sensors.theorem_novelty = 0.2;
    sensors.theorem_graph_coverage = 0.1;
    sensors.route_repetition = 0.5;
    sensors.uncertainty = 0.4;
    sensors.contradiction_rate = 0.0;
    sensors.consecutive_failures = 2;
    sensors.attempts_since_verified_progress = 2;
    sensors.seconds_since_verified_progress = 10.0;
    sensors.goal_persistence = 0.9;

    cognition::LogicalAssessment logic;
    logic.evidence_strength = 0.80;
    logic.expected_success = 0.45;
    logic.expected_information_gain = 0.30;
    logic.contradiction_risk = 0.0;
    logic.decomposition_value = 1.00;
    logic.counterexample_value = 0.0;
    logic.abstraction_value = 0.0;
    logic.compression_value = 0.85;
    logic.representation_switch_value = 0.0;
    logic.current_route_progress = 0.0;
    logic.branch_cost = 0.20;

    const auto outcome =
        engine.run(
            ResearchProblem{
                .episode_id =
                    "complete-strategy-episode",
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
    assert(outcome.dispatched_strategy.has_value());
    assert(
        outcome.dispatched_strategy->
            exemplar_sequence.steps.size() == 1);
    assert(
        outcome.dispatched_strategy_steps_attempted == 1);
    assert(outcome.dispatched_strategy_complete);

    const auto experience =
        memory.strategy_experience(
            outcome.dispatched_strategy->
                strategy_id,
            target.domain);

    assert(experience.attempts == 1);
    assert(experience.verified_progresses == 1);
    assert(experience.target_verifications == 1);

    bool saw_outcome = false;
    bool saw_partial = false;

    for (const auto& event :
         ledger.events(
             "complete-strategy-episode")) {
        if (event.event_type ==
            "research_strategy_outcome") {
            saw_outcome = true;
        }
        if (event.event_type ==
            "research_strategy_partial") {
            saw_partial = true;
        }
    }

    assert(saw_outcome);
    assert(!saw_partial);
    assert(backend.calls == 0);

    std::filesystem::remove_all(root);
    return 0;
}
