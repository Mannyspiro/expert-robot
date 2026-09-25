#pragma once

#include "expert_robot/cognition/controller.hpp"
#include "expert_robot/imagination/controller.hpp"
#include "expert_robot/imagination/memory.hpp"
#include "expert_robot/model_formalization_proposer.hpp"
#include "expert_robot/model_lemma_decomposer.hpp"
#include "expert_robot/proof_memory.hpp"
#include "expert_robot/research/candidate_verifier.hpp"
#include "expert_robot/research/engine.hpp"
#include "expert_robot/research/episode_ledger.hpp"
#include "expert_robot/research/knowledge_consolidator.hpp"
#include "expert_robot/research/route_memory.hpp"
#include "expert_robot/research/route_planner.hpp"
#include "expert_robot/research/strategy_planner.hpp"
#include "expert_robot/skills/skill_ledger.hpp"
#include "expert_robot/swarm/supervisor.hpp"

#include <filesystem>

namespace expert_robot::app {

struct MathResearchServiceConfig {
    std::filesystem::path state_dir{"state"};
    std::filesystem::path proof_search_config{
        "config/proof_search.json"};
    std::filesystem::path theorem_registry{
        "formal/theorem_registry.json"};
    std::filesystem::path theorem_graph_path{
        "state/theorem_graph.json"};

    cognition::PersonalityProfile personality{
        cognition::math_researcher_personality()};
    cognition::InteroceptionConfig interoception;
    cognition::NeuromodulationConfig neuromodulation;

    swarm::SwarmLimits swarm_limits;
    imagination::ImaginationConfig imagination;
    LemmaFactoryConfig lemma_factory;
    research::CandidateVerifierConfig candidate_verifier;
    research::RoutePlannerConfig route_planner;
    research::ResearchStrategyPlannerConfig strategy_planner;
    research::MathResearchEngineConfig research_engine;
};

class MathResearchService {
public:
    MathResearchService(
        ILeanRunner& lean_runner,
        ITextGenerationBackend& freeform_math_backend,
        ITextGenerationBackend& lemma_json_backend,
        ITextGenerationBackend& formalization_json_backend,
        MathResearchServiceConfig config = {});

    [[nodiscard]] research::ResearchOutcome run(
        research::ResearchProblem problem);

    [[nodiscard]] const KnowledgeGraph& graph() const noexcept;
    [[nodiscard]] const research::RouteOutcomeLedger&
    route_memory() const noexcept;
    [[nodiscard]] const skills::SkillLedger&
    skill_ledger() const noexcept;

private:
    MathResearchServiceConfig config_;

    ILeanRunner& lean_runner_;
    ITextGenerationBackend& freeform_math_backend_;
    ITextGenerationBackend& lemma_json_backend_;
    ITextGenerationBackend& formalization_json_backend_;

    ProofSearchConfig proof_config_;
    ProofMemory proof_memory_;
    MemoryGuidedProofSearch searcher_;

    KnowledgeGraph graph_;
    skills::SkillLedger skill_ledger_;
    imagination::ImaginationMemory imagination_memory_;
    research::RouteOutcomeLedger route_memory_;
    research::ResearchEpisodeLedger episode_ledger_;

    swarm::SwarmSupervisor swarm_;
    imagination::ImaginationController imagination_;

    ModelLemmaDecomposer lemma_decomposer_;
    RecursiveLemmaFactory lemma_factory_;

    cognition::CognitionController cognition_;

    ModelFormalizationProposer formalization_proposer_;
    research::CandidateVerifier candidate_verifier_;

    research::VerifiedKnowledgeConsolidator consolidator_;
    research::ProofRoutePlanner route_planner_;
    research::ResearchStrategyPlanner strategy_planner_;
    research::MathResearchEngine engine_;
};

} // namespace expert_robot::app
