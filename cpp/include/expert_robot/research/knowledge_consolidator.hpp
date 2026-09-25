#pragma once

#include "expert_robot/knowledge_graph.hpp"
#include "expert_robot/research/candidate_verifier.hpp"
#include "expert_robot/research/episode_ledger.hpp"

#include <filesystem>
#include <string>
#include <string_view>

namespace expert_robot::research {

struct ConsolidationResult {
    std::string theorem_name;
    bool node_created{false};
    bool node_upgraded{false};
    bool linked_to_target{false};
    std::string episode_event_hash;
};

class VerifiedKnowledgeConsolidator {
public:
    VerifiedKnowledgeConsolidator(
        KnowledgeGraph& graph,
        ResearchEpisodeLedger* episode_ledger = nullptr,
        std::filesystem::path persistence_path = {});

    [[nodiscard]] ConsolidationResult consolidate(
        std::string_view episode_id,
        std::string_view target_theorem,
        const CandidateVerification& candidate);

private:
    KnowledgeGraph& graph_;
    ResearchEpisodeLedger* episode_ledger_{nullptr};
    std::filesystem::path persistence_path_;
};

} // namespace expert_robot::research
