#include "expert_robot/eval/math_eval.hpp"
#include "expert_robot/skills/experimental_skill_store.hpp"
#include "expert_robot/skills/promotion_packet.hpp"
#include "expert_robot/skills/skill_ledger.hpp"

#include <cassert>
#include <filesystem>

int main() {
    using namespace expert_robot;
    using namespace expert_robot::eval;
    using namespace expert_robot::skills;

    const auto root =
        std::filesystem::temp_directory_path() /
        "expert-robot-skill-promotion-packet";
    std::filesystem::remove_all(root);
    std::filesystem::create_directories(root);

    ExperimentalSkillStore store(
        root / "skills.sqlite3");
    SkillLedger ledger(
        root / "ledger.sqlite3");

    MathSkill skill{
        .skill_id =
            "math.experimental.promotion_probe",
        .title =
            "Promotion probe",
        .lens =
            imagination::ImaginationLens::Counterfactual,
        .preferred_role =
            swarm::AgentRole::Skeptic,
        .procedure =
            "Perturb one hypothesis at a time and track which invariants survive.",
        .requires_lean_verification = true,
        .stage = SkillStage::Experimental
    };

    store.propose(
        skill,
        "promotion-packet-smoke");

    for (int i = 0; i < 24; ++i) {
        ledger.record_generation(
            skill.skill_id,
            i < 18,
            i < 12);
    }

    for (int i = 0; i < 5; ++i) {
        ledger.record_downstream(
            skill.skill_id,
            true);
    }
    for (int i = 0; i < 2; ++i) {
        ledger.record_downstream(
            skill.skill_id,
            false);
    }

    VariantSummary baseline;
    baseline.variant = "baseline";
    baseline.cases = 20;
    baseline.verified = 10;
    baseline.total_resource_cost = 20.0;
    baseline.total_ideas_generated = 40;
    baseline.total_duplicate_candidates = 8;

    VariantSummary candidate;
    candidate.variant =
        "experimental-promotion-probe";
    candidate.cases = 20;
    candidate.verified = 13;
    candidate.total_resource_cost = 21.0;
    candidate.total_ideas_generated = 40;
    candidate.total_duplicate_candidates = 6;

    const auto ablation =
        compare_variants(
            baseline,
            candidate,
            AblationPolicy{
                .minimum_cases = 10,
                .maximum_verified_rate_regression = 0.0,
                .maximum_cost_multiplier_without_accuracy_gain = 1.10,
                .meaningful_verified_rate_gain = 0.05,
                .maximum_duplicate_rate_increase = 0.10
            });

    assert(ablation.recommend_keep);

    const auto packet =
        build_skill_promotion_packet(
            store,
            ledger,
            skill.skill_id,
            ablation);

    assert(
        packet.recommended ==
        SkillStage::Qualified);
    assert(packet.evidence_sufficient);
    assert(packet.ready_for_external_review);
    assert(packet.requires_explicit_promotion);
    assert(packet.skill_evidence_hash.size() == 64);
    assert(packet.ablation_evidence_hash.size() == 64);
    assert(packet.packet_hash.size() == 64);

    const auto packet_again =
        build_skill_promotion_packet(
            store,
            ledger,
            skill.skill_id,
            ablation);

    assert(
        packet.packet_hash ==
        packet_again.packet_hash);

    // Review readiness must not mutate the experimental store.
    assert(
        store.get(skill.skill_id).stage ==
        SkillStage::Experimental);

    VariantSummary tiny_baseline =
        baseline;
    tiny_baseline.cases = 2;
    tiny_baseline.verified = 1;

    VariantSummary tiny_candidate =
        candidate;
    tiny_candidate.cases = 2;
    tiny_candidate.verified = 2;

    const auto weak_ablation =
        compare_variants(
            tiny_baseline,
            tiny_candidate);

    const auto weak_packet =
        build_skill_promotion_packet(
            store,
            ledger,
            skill.skill_id,
            weak_ablation);

    assert(!weak_packet.evidence_sufficient);
    assert(!weak_packet.ready_for_external_review);
    assert(weak_packet.requires_explicit_promotion);

    std::filesystem::remove_all(root);
    return 0;
}
