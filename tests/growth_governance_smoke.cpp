#include "expert_robot/knowledge_graph.hpp"
#include "expert_robot/skills/math_skill.hpp"
#include "expert_robot/skills/skill_ledger.hpp"

#include <cassert>
#include <filesystem>

int main() {
    using namespace expert_robot;
    using namespace expert_robot::skills;

    KnowledgeGraph graph({
        {
            .name = "A",
            .source = "A.lean",
            .status = "verified",
            .statement = "A",
            .domain = "analysis",
            .tags = {}
        },
        {
            .name = "B",
            .source = "B.lean",
            .status = "verified",
            .statement = "B",
            .domain = "geometry",
            .tags = {}
        },
        {
            .name = "C",
            .source = "C.lean",
            .status = "verified",
            .statement = "C",
            .domain = "topology",
            .tags = {}
        },
        {
            .name = "D",
            .source = "D.lean",
            .status = "verified",
            .statement = "D",
            .domain = "spectral",
            .tags = {}
        }
    });

    graph.add_edge({
        .source = "A",
        .relation = "ANALOGOUS_TO",
        .target = "B"
    });
    graph.add_edge({
        .source = "B",
        .relation = "GENERALIZES",
        .target = "C"
    });
    graph.add_edge({
        .source = "C",
        .relation = "IMPLIES",
        .target = "A"
    });
    graph.add_edge({
        .source = "B",
        .relation = "USES",
        .target = "D"
    });

    const auto paths =
        graph.bounded_paths("A", 3, 12);
    assert(!paths.empty());

    bool saw_depth_two = false;
    for (const auto& path : paths) {
        assert(path.nodes.front() == "A");
        assert(path.depth() <= 3);
        assert(path.nodes.size() == path.relations.size() + 1U);

        for (std::size_t i = 0; i < path.nodes.size(); ++i) {
            for (std::size_t j = i + 1U; j < path.nodes.size(); ++j) {
                assert(path.nodes[i] != path.nodes[j]);
            }
        }

        if (path.depth() >= 2U) {
            saw_depth_two = true;
        }
    }
    assert(saw_depth_two);

    const auto bounded =
        graph.bounded_paths("A", 3, 2);
    assert(bounded.size() == 2);

    const auto catalog =
        MathSkillCatalog::builtins();

    assert(!catalog.all().empty());
    for (const auto& skill : catalog.all()) {
        assert(skill.stage == SkillStage::Qualified);
        assert(
            skill_stage_name(skill.stage) ==
            "qualified");
    }

    MathSkill experimental{
        .skill_id = "math.experimental.test",
        .title = "Experimental test",
        .lens = imagination::ImaginationLens::Analogy,
        .preferred_role = swarm::AgentRole::Analogist,
        .procedure = "Try an experimental mathematical transformation.",
        .requires_lean_verification = true,
        .stage = SkillStage::Experimental
    };

    MathSkillCatalog mixed({
        catalog.get("math.analogy.transfer"),
        experimental
    });

    assert(
        mixed.for_lens(
            imagination::ImaginationLens::Analogy).size() == 2);
    const auto qualified =
        mixed.qualified_for_lens(
            imagination::ImaginationLens::Analogy);
    assert(qualified.size() == 1);
    assert(
        qualified[0].skill_id ==
        "math.analogy.transfer");

    const auto db =
        std::filesystem::temp_directory_path() /
        "expert-robot-skill-ledger.sqlite3";
    std::filesystem::remove(db);

    {
        SkillLedger ledger(db);

        for (int i = 0; i < 20; ++i) {
            ledger.record_generation(
                experimental.skill_id,
                i < 10,
                i < 8);
        }

        for (int i = 0; i < 4; ++i) {
            ledger.record_downstream(
                experimental.skill_id,
                true);
        }
        for (int i = 0; i < 2; ++i) {
            ledger.record_downstream(
                experimental.skill_id,
                false);
        }

        const auto stats =
            ledger.stats(
                experimental.skill_id);
        assert(stats.attempts == 20);
        assert(stats.skeptic_passes == 10);
        assert(stats.shortlisted == 8);
        assert(stats.downstream_verified == 4);
        assert(stats.downstream_failed == 2);
        assert(stats.verified_rate() == 0.20);
        assert(stats.shortlist_rate() == 0.40);

        assert(
            recommended_stage(stats) ==
            SkillStage::Qualified);

        // Evidence recommends a stage, but the catalog remains unchanged.
        assert(
            mixed.get(experimental.skill_id).stage ==
            SkillStage::Experimental);
    }

    std::filesystem::remove(db);
    return 0;
}
