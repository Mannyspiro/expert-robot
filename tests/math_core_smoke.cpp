#include "expert_robot/knowledge_graph.hpp"
#include "expert_robot/proof_memory.hpp"
#include "expert_robot/proof_search.hpp"
#include "expert_robot/sha256.hpp"

#include <cassert>
#include <chrono>
#include <filesystem>
#include <string>

namespace {

class FakeLeanRunner final : public expert_robot::ILeanRunner {
public:
    expert_robot::LeanRunResult run(std::string_view source) override {
        if (source.find("  ring\n") != std::string_view::npos) {
            return {0, "accepted"};
        }
        return {1, "rejected"};
    }
};

std::filesystem::path temp_path(const char* stem, const char* suffix) {
    return std::filesystem::temp_directory_path() /
           (std::string(stem) + "-" + std::to_string(
               std::chrono::steady_clock::now().time_since_epoch().count()) + suffix);
}

} // namespace

int main() {
    using namespace expert_robot;

    assert(sha256_hex("abc") ==
           "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");

    SearchProblem problem;
    problem.statement = "(x : \xE2\x84\x9D) : x + 0 = x";
    assert(goal_fingerprint(problem) ==
           "0bc00462b228737a54d665b4ec2748db73ae0a81a9053095d034dba836f57645");

    const auto rendered = DeterministicProofSearch::render(problem, "ring");
    assert(rendered.find("import MathAI") != std::string::npos);
    assert(rendered.find("theorem MathAI_Search_Candidate") != std::string::npos);

    FakeLeanRunner runner;
    DeterministicProofSearch search({"simp", "ring"}, runner);
    const auto first = search.search(problem);
    assert(first.success);
    assert(first.tactic && *first.tactic == "ring");
    assert(first.attempts.size() == 2);

    const auto db_path = temp_path("expert-robot-proof-memory", ".sqlite3");
    {
        ProofMemory memory(db_path);
        memory.record_result(first);
        const auto stats = memory.stats_for(problem);
        assert(stats.size() == 2);

        const auto ordered = memory.order_strategies(problem, {"simp", "ring"});
        assert(ordered.size() == 2);
        assert(ordered[0] == "ring");
        assert(ordered[1] == "simp");

        MemoryGuidedProofSearch guided({"simp", "ring"}, runner, memory);
        const auto second = guided.search(problem);
        assert(second.success);
        assert(second.attempts.size() == 1);
        assert(second.attempts[0].tactic == "ring");

        const auto summary = memory.summary();
        assert(summary.schema_version == 1);
        assert(summary.goals == 1);
        assert(summary.attempts == 3);
        assert(summary.successful_attempts == 2);
    }
    std::filesystem::remove(db_path);

    TheoremNode seed{
        .name = "MathAI.Trust.add_zero_verified",
        .source = "MathAI/Trust/Seed.lean",
        .status = "candidate",
        .statement = "n + 0 = n",
        .domain = "algebra",
        .tags = {"seed", "algebra", "seed"},
    };
    TheoremNode geometry{
        .name = "MathAI.Geometry.origin_on_xy_plane",
        .source = "MathAI/Geometry/Exact.lean",
        .status = "candidate",
        .statement = "origin lies on xy plane",
        .domain = "geometry",
        .tags = {"geometry"},
    };

    KnowledgeGraph graph({seed, geometry});
    graph.add_edge({
        .source = seed.name,
        .relation = "ANALOGOUS_TO",
        .target = geometry.name,
    });
    assert(graph.related(seed.name).size() == 1);
    assert(graph.get(seed.name).tags.size() == 2);

    const auto graph_path = temp_path("expert-robot-theorem-graph", ".json");
    graph.save(graph_path);
    auto loaded = KnowledgeGraph::load(graph_path);
    assert(loaded.nodes().size() == 2);
    assert(loaded.edges().size() == 1);
    std::filesystem::remove(graph_path);

    return 0;
}
