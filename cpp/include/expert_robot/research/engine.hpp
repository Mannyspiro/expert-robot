#pragma once

#include "expert_robot/cognition/controller.hpp"
#include "expert_robot/formalizer.hpp"
#include "expert_robot/imagination/controller.hpp"
#include "expert_robot/lemma_factory.hpp"
#include "expert_robot/research/candidate_verifier.hpp"
#include "expert_robot/research/episode_ledger.hpp"
#include "expert_robot/research/knowledge_consolidator.hpp"
#include "expert_robot/research/route_memory.hpp"
#include "expert_robot/research/route_planner.hpp"
#include "expert_robot/research/state_machine.hpp"
#include "expert_robot/research/strategy_planner.hpp"
#include "expert_robot/skills/skill_ledger.hpp"

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

namespace expert_robot::research {

struct ResearchProblem {
    std::string episode_id;
    FormalizationProposal target;

    std::string focus_theorem;
    std::vector<std::string> context;

    cognition::InteroceptiveSensors sensors;
    cognition::LogicalAssessment logic;

    bool evaluation_mode{false};
    std::vector<skills::MathSkill> experimental_skills;
};

struct ResearchFeatureFlags {
    bool theorem_graph{true};
    bool route_planning{true};
    bool imagination{true};
    bool decomposition{true};
    bool route_memory{true};
    bool sequence_memory{true};
    bool strategy_planning{true};
    bool strategy_memory{true};
};

struct MathResearchEngineConfig {
    ResearchBudget budget;
    std::size_t max_dispatch_steps{64};
    ResearchFeatureFlags features;
};

struct ResearchOutcome {
    bool target_verified{false};
    ResearchState final_state;

    std::optional<FormalizationResult> target_result;
    std::vector<std::string> helper_declarations;
    std::vector<CandidateVerification> candidate_verifications;
    std::vector<ConsolidationResult> consolidations;

    std::optional<imagination::ImaginationRun> last_imagination;
    std::vector<ProofRoute> planned_routes;
    std::vector<ProofRouteSequence> planned_sequences;
    std::vector<ResearchStrategyPlan> planned_strategies;
    std::optional<ResearchStrategyPlan> dispatched_strategy;
    std::size_t dispatched_strategy_steps_attempted{0};
    bool dispatched_strategy_complete{false};
    std::optional<ProofRouteSequence> dispatched_sequence;
    std::optional<ProofRoute> dispatched_route;

    std::string episode_root_hash;
};

class MathResearchEngine {
public:
    MathResearchEngine(
        IProofSearcher& searcher,
        cognition::CognitionController& cognition,
        imagination::ImaginationController& imagination,
        RecursiveLemmaFactory& lemma_factory,
        CandidateVerifier& candidate_verifier,
        VerifiedKnowledgeConsolidator& consolidator,
        ResearchEpisodeLedger& episode_ledger,
        MathResearchEngineConfig config = {},
        ProofRoutePlanner* route_planner = nullptr,
        RouteOutcomeLedger* route_memory = nullptr,
        skills::SkillLedger* skill_ledger = nullptr,
        ResearchStrategyPlanner* strategy_planner = nullptr);

    [[nodiscard]] ResearchOutcome run(
        ResearchProblem problem);

private:
    IProofSearcher& searcher_;
    cognition::CognitionController& cognition_;
    imagination::ImaginationController& imagination_;
    RecursiveLemmaFactory& lemma_factory_;
    CandidateVerifier& candidate_verifier_;
    VerifiedKnowledgeConsolidator& consolidator_;
    ResearchEpisodeLedger& episode_ledger_;
    MathResearchEngineConfig config_;
    ProofRoutePlanner* route_planner_{nullptr};
    RouteOutcomeLedger* route_memory_{nullptr};
    skills::SkillLedger* skill_ledger_{nullptr};
    ResearchStrategyPlanner* strategy_planner_{nullptr};
};

} // namespace expert_robot::research
