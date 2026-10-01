#include "expert_robot/skills/promotion_packet.hpp"

#include "expert_robot/growth/ablation_evidence.hpp"
#include "expert_robot/sha256.hpp"

#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace expert_robot::skills {

std::string skill_evidence_hash(
    const MathSkill& skill,
    const SkillStats& stats) {
    if (skill.skill_id.empty()) {
        throw std::invalid_argument(
            "skill evidence requires non-empty skill_id");
    }

    std::ostringstream canonical;
    canonical << std::boolalpha
        << "skill_id=" << skill.skill_id << "\n"
        << "title=" << skill.title << "\n"
        << "lens="
        << static_cast<int>(skill.lens) << "\n"
        << "role="
        << static_cast<int>(
            skill.preferred_role) << "\n"
        << "procedure_sha256="
        << sha256_hex(skill.procedure) << "\n"
        << "requires_lean_verification="
        << skill.requires_lean_verification << "\n"
        << "stage="
        << skill_stage_name(skill.stage) << "\n"
        << "attempts=" << stats.attempts << "\n"
        << "skeptic_passes="
        << stats.skeptic_passes << "\n"
        << "shortlisted="
        << stats.shortlisted << "\n"
        << "downstream_verified="
        << stats.downstream_verified << "\n"
        << "downstream_failed="
        << stats.downstream_failed << "\n"
        << "verified_rate="
        << std::setprecision(17)
        << stats.verified_rate() << "\n"
        << "shortlist_rate="
        << stats.shortlist_rate();

    return sha256_hex(
        canonical.str());
}

std::string skill_promotion_packet_hash(
    const SkillPromotionPacket& packet) {
    if (packet.skill_evidence_hash.size() != 64U ||
        packet.ablation_evidence_hash.size() != 64U) {
        throw std::invalid_argument(
            "promotion packet evidence hashes must be SHA-256 hex");
    }

    std::ostringstream canonical;
    canonical << std::boolalpha
        << "skill_id="
        << packet.skill.skill_id << "\n"
        << "skill_evidence_hash="
        << packet.skill_evidence_hash << "\n"
        << "ablation_evidence_hash="
        << packet.ablation_evidence_hash << "\n"
        << "recommended="
        << skill_stage_name(
            packet.recommended) << "\n"
        << "evidence_sufficient="
        << packet.evidence_sufficient << "\n"
        << "ready_for_external_review="
        << packet.ready_for_external_review << "\n"
        << "requires_explicit_promotion="
        << packet.requires_explicit_promotion;

    return sha256_hex(
        canonical.str());
}

SkillPromotionPacket build_skill_promotion_packet(
    const ExperimentalSkillStore& store,
    const SkillLedger& ledger,
    std::string_view skill_id,
    const eval::AblationResult& ablation,
    const SkillQualificationPolicy& skill_policy) {
    if (skill_id.empty()) {
        throw std::invalid_argument(
            "promotion packet skill_id must be non-empty");
    }

    const auto report =
        store.promotion_report(
            skill_id,
            ledger,
            skill_policy);

    SkillPromotionPacket packet;
    packet.skill = report.skill;
    packet.stats = report.stats;
    packet.recommended =
        report.recommended;
    packet.ablation = ablation;

    packet.skill_evidence_hash =
        skill_evidence_hash(
            packet.skill,
            packet.stats);

    packet.ablation_evidence_hash =
        growth::ablation_evidence_hash(
            ablation);

    packet.evidence_sufficient =
        packet.recommended ==
            SkillStage::Qualified &&
        ablation.enough_cases &&
        ablation.recommend_keep &&
        ablation.verification_ok &&
        ablation.efficiency_ok &&
        ablation.diversity_ok;

    packet.ready_for_external_review =
        packet.evidence_sufficient;

    packet.requires_explicit_promotion =
        true;

    if (packet.ready_for_external_review) {
        packet.rationale =
            "Skill evidence and ablation evidence satisfy qualification "
            "thresholds; external promotion approval is still required.";
    } else if (
        packet.recommended !=
        SkillStage::Qualified) {
        packet.rationale =
            "Skill outcome history has not reached qualification thresholds.";
    } else if (!ablation.enough_cases) {
        packet.rationale =
            "Ablation evidence does not contain enough cases.";
    } else {
        packet.rationale =
            "Ablation evidence does not satisfy verification, efficiency, "
            "or diversity requirements.";
    }

    packet.packet_hash =
        skill_promotion_packet_hash(
            packet);

    return packet;
}

} // namespace expert_robot::skills
