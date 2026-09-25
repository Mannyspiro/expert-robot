#include "expert_robot/imagination/controller.hpp"
#include "expert_robot/skills/experimental_skill_store.hpp"
#include "expert_robot/swarm/supervisor.hpp"
#include "expert_robot/skills/model_skill_proposer.hpp"
#include "expert_robot/skills/skill_ledger.hpp"

#include <cassert>
#include <filesystem>
#include <mutex>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

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

class TrialBackend final : public expert_robot::ITextGenerationBackend {
public:
    expert_robot::TextGenerationResult generate(
        const expert_robot::TextGenerationRequest& request) override {
        {
            std::scoped_lock lock(mu_);
            prompts_.push_back(request.user_prompt);
        }

        if (request.user_prompt.find(
                "Critique this candidate mathematical idea independently.") !=
            std::string::npos) {
            return {
                .ok = true,
                .exit_code = 0,
                .timed_out = false,
                .output =
                    "DECISION=KEEP\nRISK=20\nCRITIQUE=useful evaluation candidate",
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
                    "Verify the experimental mechanism against the baseline and Lean.",
                .diagnostics = ""
            };
        }

        return {
            .ok = true,
            .exit_code = 0,
            .timed_out = false,
            .output =
                "Use the requested lens to produce a distinct candidate mechanism.",
            .diagnostics = ""
        };
    }

    [[nodiscard]] bool saw(
        std::string_view needle) const {
        std::scoped_lock lock(mu_);
        for (const auto& prompt : prompts_) {
            if (prompt.find(needle) !=
                std::string::npos) {
                return true;
            }
        }
        return false;
    }

private:
    mutable std::mutex mu_;
    std::vector<std::string> prompts_;
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

    const auto trial_ledger_db =
        std::filesystem::temp_directory_path() /
        "expert-robot-experimental-trial-ledger.sqlite3";
    std::filesystem::remove(trial_ledger_db);

    {
        TrialBackend trial_backend;
        swarm::SwarmSupervisor trial_swarm(
            {
                {
                    swarm::AgentRole::Mathematician,
                    &trial_backend
                }
            },
            swarm::SwarmLimits{
                .max_parallel_agents = 4,
                .max_total_tasks = 32,
                .max_depth = 3,
                .max_children_per_parent = 16,
                .serialize_shared_backend = true
            });

        SkillLedger trial_ledger(
            trial_ledger_db);

        imagination::ImaginationController trial_controller(
            trial_swarm,
            imagination::ImaginationConfig{
                .normal_lens_budget =
                    static_cast<std::size_t>(
                        imagination::ImaginationLens::Count),
                .breakthrough_lens_budget =
                    static_cast<std::size_t>(
                        imagination::ImaginationLens::Count),
                .skeptic_budget =
                    static_cast<std::size_t>(
                        imagination::ImaginationLens::Count),
                .max_expensive_candidates = 3,
                .archive_capacity_per_lens = 2,
                .minimum_imagination_drive = 0.0,
                .maximum_skeptic_risk = 65,
                .enable_synthesis = true,
                .theorem_graph_max_depth = 3,
                .theorem_graph_max_paths = 12
            },
            nullptr,
            MathSkillCatalog::builtins(),
            nullptr,
            &trial_ledger);

        cognition::CognitionCycle cycle;
        cycle.interoception.state.resource_pressure = 0.1;
        cycle.interoception.state.stagnation = 0.8;
        cycle.interoception.state.novelty = 0.8;
        cycle.interoception.state.uncertainty = 0.4;
        cycle.interoception.state.route_repetition = 0.5;
        cycle.affect.exploration_drive = 0.9;
        cycle.affect.persistence_drive = 0.6;
        cycle.affect.attention_allocation = 0.6;
        cycle.affect.strategy_switch_pressure = 0.7;
        cycle.affect.compute_conservation = 0.1;
        cycle.decision.action =
            cognition::CognitiveAction::ExploreNovelRoute;

        cognition::LogicalAssessment logic;
        logic.expected_information_gain = 0.9;
        logic.expected_success = 0.3;
        logic.current_route_progress = 0.1;
        logic.branch_cost = 0.2;

        imagination::ImaginationRequest production_request{
            .request_id = "production-must-reject",
            .goal = "Find a proof route.",
            .context = {},
            .focus_theorem = "",
            .personality =
                cognition::math_researcher_personality(),
            .cognition = cycle,
            .logic = logic,
            .evaluation_mode = false,
            .experimental_skills = {
                *proposal.skill
            }
        };

        bool production_rejected = false;
        try {
            (void)trial_controller.run(
                production_request);
        } catch (const std::invalid_argument&) {
            production_rejected = true;
        }
        assert(production_rejected);

        auto evaluation_request =
            production_request;
        evaluation_request.request_id =
            "explicit-evaluation";
        evaluation_request.evaluation_mode =
            true;

        const auto trial =
            trial_controller.run(
                evaluation_request);

        assert(!trial.skipped);
        assert(
            trial_backend.saw(
                "EXPERIMENTAL SKILL UNDER ABLATION: "
                "math.experimental.symmetry_breaking"));

        const auto trial_stats =
            trial_ledger.stats(
                proposal.skill->skill_id);
        assert(trial_stats.attempts >= 1);

        // Evaluation use still does not change the skill stage.
        assert(
            proposal.skill->stage ==
            SkillStage::Experimental);
    }

    std::filesystem::remove(
        trial_ledger_db);

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
