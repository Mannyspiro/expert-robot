#include "expert_robot/research/knowledge_consolidator.hpp"

#include <cassert>
#include <filesystem>
#include <optional>
#include <stdexcept>

namespace {

expert_robot::research::CandidateVerification
proven_candidate() {
    using namespace expert_robot;

    FormalizationProposal proposal{
        .name = "verified_helper",
        .name_space = "MathAI.Generated",
        .binders = {
            {"x", "ℝ"}
        },
        .proposition = "x = x",
        .imports = {"MathAI"},
        .domain = "algebra",
        .rationale = "verified helper"
    };

    SearchProblem problem;
    problem.statement =
        proposal.statement();

    SearchResult search;
    search.problem = problem;
    search.success = true;
    search.tactic = "rfl";
    search.proof = "by\n  rfl";
    search.attempts.push_back(
        SearchAttempt{
            .tactic = "rfl",
            .success = true,
            .exit_code = 0,
            .output = "accepted"
        });

    FormalizationResult formal{
        .proposal = proposal,
        .search = search,
        .lean_source =
            "import MathAI\n"
            "theorem MathAI.Generated.verified_helper "
            "(x : ℝ) : x = x := by\n  rfl\n",
        .lean_declaration =
            "theorem MathAI.Generated.verified_helper "
            "(x : ℝ) : x = x := by\n  rfl",
        .trusted = false
    };

    return research::CandidateVerification{
        .idea_id = "idea-verified",
        .proposal_generated = true,
        .proposal = proposal,
        .formalization = formal,
        .error = ""
    };
}

} // namespace

int main() {
    using namespace expert_robot;
    using namespace expert_robot::research;

    KnowledgeGraph graph({
        TheoremNode{
            .name = "MathAI.Target",
            .source = "Target.lean",
            .status = "verified",
            .statement = "(x : ℝ) : x = x",
            .domain = "algebra",
            .tags = {"target"}
        }
    });

    const auto episode_db =
        std::filesystem::temp_directory_path() /
        "expert-robot-consolidator-episode.sqlite3";
    const auto graph_json =
        std::filesystem::temp_directory_path() /
        "expert-robot-consolidated-graph.json";

    std::filesystem::remove(
        episode_db);
    std::filesystem::remove(
        graph_json);

    ResearchEpisodeLedger ledger(
        episode_db);

    VerifiedKnowledgeConsolidator consolidator(
        graph,
        &ledger,
        graph_json);

    const auto candidate =
        proven_candidate();

    const auto result =
        consolidator.consolidate(
            "episode-verified",
            "MathAI.Target",
            candidate);

    assert(
        result.theorem_name ==
        "MathAI.Generated.verified_helper");
    assert(result.node_created);
    assert(!result.node_upgraded);
    assert(result.linked_to_target);
    assert(!result.episode_event_hash.empty());

    const auto& node =
        graph.get(
            "MathAI.Generated.verified_helper");
    assert(node.status == "verified");
    assert(node.domain == "algebra");
    assert(
        node.statement ==
        "(x : ℝ) : x = x");

    const auto related =
        graph.related(
            "MathAI.Target",
            "USES");
    assert(related.size() == 1);
    assert(
        related[0].target ==
        "MathAI.Generated.verified_helper");

    assert(
        std::filesystem::exists(
            graph_json));

    const auto reloaded =
        KnowledgeGraph::load(
            graph_json);
    assert(
        reloaded.get(
            "MathAI.Generated.verified_helper").status ==
        "verified");

    const auto episode_verified =
        ledger.verify(
            "episode-verified");
    assert(episode_verified.valid);
    assert(episode_verified.event_count == 1);
    assert(
        episode_verified.root_hash ==
        result.episode_event_hash);

    CandidateVerification unproven;
    unproven.idea_id = "not-proven";

    bool unproven_rejected = false;
    try {
        (void)consolidator.consolidate(
            "episode-unproven",
            "MathAI.Target",
            unproven);
    } catch (const std::invalid_argument&) {
        unproven_rejected = true;
    }
    assert(unproven_rejected);

    bool absent = false;
    try {
        (void)graph.get(
            "MathAI.Generated.not_proven");
    } catch (const std::out_of_range&) {
        absent = true;
    }
    assert(absent);

    // Re-consolidating the same theorem does not create a conflicting node.
    const auto again =
        consolidator.consolidate(
            "episode-verified",
            "MathAI.Target",
            candidate);
    assert(!again.node_created);
    assert(again.linked_to_target);

    const auto second_episode_check =
        ledger.verify(
            "episode-verified");
    assert(second_episode_check.valid);
    assert(second_episode_check.event_count == 2);

    std::filesystem::remove(
        graph_json);
    std::filesystem::remove(
        episode_db);

    return 0;
}
