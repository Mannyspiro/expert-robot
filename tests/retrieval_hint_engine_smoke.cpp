#include "expert_robot/cognition/controller.hpp"
#include "expert_robot/imagination/controller.hpp"
#include "expert_robot/lemma_factory.hpp"
#include "expert_robot/research/candidate_verifier.hpp"
#include "expert_robot/research/engine.hpp"
#include "expert_robot/research/episode_ledger.hpp"
#include "expert_robot/research/knowledge_consolidator.hpp"
#include "expert_robot/research/route_memory.hpp"
#include "expert_robot/research/route_planner.hpp"
#include "expert_robot/swarm/supervisor.hpp"

#include <cassert>
#include <filesystem>
#include <stdexcept>

namespace {

class HintAwareSearcher final : public expert_robot::IProofSearcher {
public:
    expert_robot::SearchResult search(
        const expert_robot::SearchProblem& problem) override {
        using namespace expert_robot;

        SearchResult result;
        result.problem = problem;

        for (const auto& tactic :
             problem.preferred_strategies) {
            if (tactic ==
                "simp [MathAI.Helper]") {
                saw_verified_hint = true;
                result.success = true;
                result.tactic = tactic;
                result.proof =
                    "by\n  simp [MathAI.Helper]";
                result.attempts.push_back(
                    SearchAttempt{
                        .tactic = tactic,
                        .success = true,
                        .exit_code = 0,
                        .output =
                            "verified dependency rewrite accepted"
                    });
                return result;
            }
        }

        result.attempts.push_back(
            SearchAttempt{
                .tactic = "simp",
                .success = false,
                .exit_code = 1,
                .output =
                    "generic direct proof intentionally fails"
            });
        return result;
    }

    bool saw_verified_hint{false};
};

class CountingBackend final
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
            .diagnostics =
                "model should not be needed for verified retrieval route"
        };
    }

    int calls{0};
};

class NeverDecompose final
    : public expert_robot::ILemmaDecomposer {
public:
    std::vector<expert_robot::FormalizationProposal>
    decompose(
        const expert_robot::FormalizationProposal&,
        const expert_robot::FormalizationResult&) override {
        ++calls;
        return {};
    }

    int calls{0};
};

class NeverFormalizeBackend final
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
            .diagnostics =
                "candidate formalizer should not be called"
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
        "expert-robot-retrieval-hint-engine";
    std::filesystem::remove_all(root);
    std::filesystem::create_directories(root);

    FormalizationProposal target{
        .name = "retrieval_target",
        .name_space = "MathAI.Generated",
        .binders = {},
        .proposition = "True",
        .imports = {"MathAI"},
        .domain = "logic",
        .rationale =
            "verified-retrieval integration target"
    };

    KnowledgeGraph graph({
        TheoremNode{
            .name = target.qualified_name(),
            .source = "Target.lean",
            .status = "candidate",
            .statement = target.statement(),
            .domain = "logic",
            .tags = {"target"}
        },
        TheoremNode{
            .name = "MathAI.Helper",
            .source = "Helper.lean",
            .status = "verified",
            .statement =
                "A verified rewrite lemma used by the target.",
            .domain = "logic",
            .tags = {"lean_verified"}
        }
    });

    graph.add_edge(
        TheoremEdge{
            .source = target.qualified_name(),
            .relation = "USES",
            .target = "MathAI.Helper"
        });

    HintAwareSearcher searcher;

    CountingBackend swarm_backend;
    swarm::SwarmSupervisor swarm(
        {
            {
                swarm::AgentRole::Mathematician,
                &swarm_backend
            }
        },
        swarm::SwarmLimits{
            .max_parallel_agents = 2,
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

    NeverDecompose decomposer;
    RecursiveLemmaFactory lemma_factory(
        searcher,
        decomposer,
        LemmaFactoryConfig{
            .max_depth = 1,
            .max_children = 1,
            .max_nodes = 2
        });

    cognition::CognitionController cognition(
        cognition::math_researcher_personality(),
        cognition::InteroceptionConfig{
            .smoothing = 1.0
        },
        cognition::NeuromodulationConfig{
            .smoothing = 1.0
        });

    NeverFormalizeBackend formalization_backend;
    ModelFormalizationProposer proposer(
        formalization_backend);

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

    RouteOutcomeLedger route_memory(
        root / "routes.sqlite3");

    ProofRoutePlanner route_planner(
        graph,
        RoutePlannerConfig{},
        &route_memory);

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
                    .max_cycles = 8,
                    .max_model_calls = 8,
                    .max_proof_attempts = 16,
                    .max_generated_ideas = 8,
                    .max_generated_lemmas = 8
                },
            .max_dispatch_steps = 8
        },
        &route_planner,
        &route_memory,
        nullptr);

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
    sensors.theorem_graph_coverage = 0.8;
    sensors.route_repetition = 0.0;
    sensors.uncertainty = 0.2;
    sensors.contradiction_rate = 0.0;
    sensors.goal_persistence = 0.8;

    cognition::LogicalAssessment logic;
    logic.evidence_strength = 0.8;
    logic.expected_success = 0.8;
    logic.expected_information_gain = 0.2;
    logic.contradiction_risk = 0.0;
    logic.decomposition_value = 0.1;
    logic.counterexample_value = 0.0;
    logic.abstraction_value = 0.1;
    logic.compression_value = 0.1;
    logic.representation_switch_value = 0.0;
    logic.current_route_progress = 0.5;
    logic.branch_cost = 0.1;

    const auto outcome =
        engine.run(
            ResearchProblem{
                .episode_id =
                    "retrieval-hint-episode",
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
    assert(searcher.saw_verified_hint);
    assert(outcome.dispatched_route.has_value());
    assert(
        outcome.dispatched_route->kind ==
        ProofRouteKind::ReuseVerifiedTheorem);

    assert(swarm_backend.calls == 0);
    assert(formalization_backend.calls == 0);
    assert(decomposer.calls == 0);
    assert(!outcome.last_imagination.has_value());

    const auto& consolidated =
        graph.get(
            target.qualified_name());
    assert(consolidated.status == "verified");

    const auto events =
        ledger.events(
            "retrieval-hint-episode");

    bool saw_retrieval_hint = false;
    for (const auto& event : events) {
        if (event.event_type ==
            "retrieval_route_hint") {
            saw_retrieval_hint = true;
            break;
        }
    }
    assert(saw_retrieval_hint);

    std::filesystem::remove_all(root);
    return 0;
}
