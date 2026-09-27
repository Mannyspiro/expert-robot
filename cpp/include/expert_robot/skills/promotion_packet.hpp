#pragma once

#include "expert_robot/eval/math_eval.hpp"
#include "expert_robot/skills/experimental_skill_store.hpp"

#include <string>
#include <string_view>

namespace expert_robot::skills {

struct SkillPromotionPacket {
    MathSkill skill;
    SkillStats stats;
    SkillStage recommended{
        SkillStage::Experimental};

    eval::AblationResult ablation;

    std::string skill_evidence_hash;
    std::string ablation_evidence_hash;
    std::string packet_hash;

    bool evidence_sufficient{false};
    bool ready_for_external_review{false};
    bool requires_explicit_promotion{true};

    std::string rationale;
};

[[nodiscard]] std::string skill_evidence_hash(
    const MathSkill& skill,
    const SkillStats& stats);

[[nodiscard]] std::string skill_promotion_packet_hash(
    const SkillPromotionPacket& packet);

[[nodiscard]] SkillPromotionPacket build_skill_promotion_packet(
    const ExperimentalSkillStore& store,
    const SkillLedger& ledger,
    std::string_view skill_id,
    const eval::AblationResult& ablation,
    const SkillQualificationPolicy& skill_policy = {});

} // namespace expert_robot::skills
