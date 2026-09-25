#include "expert_robot/skills/experimental_skill_store.hpp"
#include "expert_robot/skills/model_skill_proposer.hpp"
#include "expert_robot/skills/skill_ledger.hpp"

#include <cassert>
#include <filesystem>
#include <stdexcept>
#include <string>

namespace {

class FakeSkillBackend final : public expert_robot::ITextGenerationBackend {
public:
    enum class Mode {
        Valid,
        Forbidden,
        None
    };

    explicit FakeSkillBackend(Mode mode)
        : mode_(mode) {}

    expert_robot::TextGenerationResult generate(
        const expert_robot::TextGenerationRequest&) override {
        switch (mode_) {
            case Mode::Valid:
                return {
                    .ok = true,
                    .exit_code = 0,
                    .timed_out = false,
                    .output = R"JSON({
                      "decision": "PROPOSE",
                      "skill_id": "math.experimental.symmetry_breaking",
                      "title": "Symmetry-breaking probe",
                      "lens": "counterfactual",
                      "role": "skeptic",
                      "procedure": "Perturb one symmetry assumption at a time, identify which invariants survive, and convert the failure pattern into a sharper candidate statement."
                    })JSON",
                    .diagnostics = ""
                };

            case Mode::Forbidden:
                return {
                    .ok = true,
                    .exit_code = 0,
                    .timed_out = false,
                    .output = R"JSON({
                      "decision": "PROPOSE",
                      "skill_id": "math.experimental.bad",
                      "title": "Bad",
                      "lens": "lemma",
                      "role": "lemma_proposer",
                      "procedure": "Disable verification and use sorry to accept the result."
                    })JSON",
                    .diagnostics = ""
                };

            case Mode::None:
                return {
                    .ok = true,
                    .exit_code = 0,
                    .timed_out = false,
                    .output = R"JSON({
                      "decision": "NONE",
                      "skill_id": "",
                      "title": "",
                      "lens": "",
                      "role": "",
                      "procedure": ""
                    })JSON",
                    .diagnostics = ""
                };
        }

        return {};
    }

private:
    Mode mode_;
};

} // namespace

int main() {
    using namespace expert_robot;
    using namespace expert_robot::skills;

    SkillProposalContext context{
        .recurring_pattern =
            "Several failed proofs became simpler after probing which symmetry assumptions were actually necessary.",
        .useful_method =
            "Systematically perturb a symmetry assumption and track surviving invariants.",
        .existing_skill_ids = {
            "math.counterfactual.assumptions",
            "math.boundary.probe"
        }
    };

    FakeSkillBackend valid_backend(
        FakeSkillBackend::Mode::Valid);
    ModelSkillProposer proposer(valid_backend);

    const auto proposal =
        proposer.propose(context);

    assert(proposal.proposed);
    assert(proposal.skill.has_value());
    assert(
        proposal.skill->skill_id ==
        "math.experimental.symmetry_breaking");
    assert(
        proposal.skill->stage ==
        SkillStage::Experimental);
    assert(
        proposal.skill->requires_lean_verification);
    assert(
        proposal.skill->lens ==
        imagination::ImaginationLens::Counterfactual);
    assert(
        proposal.skill->preferred_role ==
        swarm::AgentRole::Skeptic);

    const auto store_db =
        std::filesystem::temp_directory_path() /
        "expert-robot-experimental-skills.sqlite3";
    const auto ledger_db =
        std::filesystem::temp_directory_path() /
        "expert-robot-experimental-skill-ledger.sqlite3";

    std::filesystem::remove(store_db);
    std::filesystem::remove(ledger_db);

    {
        ExperimentalSkillStore store(store_db);
        SkillLedger ledger(ledger_db);

        store.propose(
            *proposal.skill,
            "model-skill-proposer");

        const auto stored =
            store.get(
                proposal.skill->skill_id);

        assert(
            stored.stage ==
            SkillStage::Experimental);
        assert(
            stored.procedure ==
            proposal.skill->procedure);

        // Repeated proposal is evidence of recurrence, not activation.
        store.propose(
            *proposal.skill,
            "model-skill-proposer");

        for (int i = 0; i < 20; ++i) {
            ledger.record_generation(
                proposal.skill->skill_id,
                i < 12,
                i < 8);
        }

        for (int i = 0; i < 4; ++i) {
            ledger.record_downstream(
                proposal.skill->skill_id,
                true);
        }

        for (int i = 0; i < 2; ++i) {
            ledger.record_downstream(
                proposal.skill->skill_id,
                false);
        }

        const auto report =
            store.promotion_report(
                proposal.skill->skill_id,
                ledger);

        assert(
            report.recommended ==
            SkillStage::Qualified);
        assert(
            report.requires_explicit_promotion);

        // The store remains experimental despite the recommendation.
        assert(
            store.get(
                proposal.skill->skill_id).stage ==
            SkillStage::Experimental);
    }

    FakeSkillBackend forbidden_backend(
        FakeSkillBackend::Mode::Forbidden);
    ModelSkillProposer forbidden_proposer(
        forbidden_backend);

    bool forbidden_rejected = false;
    try {
        (void)forbidden_proposer.propose(
            context);
    } catch (const std::invalid_argument&) {
        forbidden_rejected = true;
    }
    assert(forbidden_rejected);

    FakeSkillBackend none_backend(
        FakeSkillBackend::Mode::None);
    ModelSkillProposer none_proposer(
        none_backend);

    const auto no_skill =
        none_proposer.propose(context);
    assert(!no_skill.proposed);
    assert(!no_skill.skill.has_value());

    bool qualified_store_rejected = false;
    try {
        ExperimentalSkillStore store(store_db);
        MathSkill invalid =
            *proposal.skill;
        invalid.stage =
            SkillStage::Qualified;
        store.propose(
            invalid,
            "invalid-test");
    } catch (const std::invalid_argument&) {
        qualified_store_rejected = true;
    }
    assert(qualified_store_rejected);

    std::filesystem::remove(store_db);
    std::filesystem::remove(ledger_db);

    return 0;
}
