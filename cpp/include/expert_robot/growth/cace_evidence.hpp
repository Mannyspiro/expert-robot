#pragma once

#include "expert_robot/growth/generation_lineage.hpp"

#include <optional>
#include <string>
#include <string_view>

namespace expert_robot::growth {

struct CaceEvaluationEvidence {
    std::string request_id;
    std::string capability_id;

    std::string source_commit;
    std::string cace_commit;

    std::string evidence_sha256;
    std::string result_sha256;
    std::string evaluation_evidence_hash;

    bool passed{false};

    // True when the selected capability is a formal qualification gate.
    bool qualification_capability{false};

    // Must equal passed && qualification_capability. Kept explicit so drift
    // between the external validator and lineage adapter fails closed.
    bool qualification_evidence{false};

    std::string authority{"qualification-only"};
    bool promotion_authority{false};
    std::string monetary_cost{"free"};

    long long wall_seconds{0};
    long long lean_checks{0};
};

struct CaceEvidenceReceipt {
    EvaluationRecord evaluation;
    std::optional<VerificationGateRecord> verification_gate;
};

void validate_cace_evaluation_evidence(
    const CaceEvaluationEvidence& evidence);

/**
 * Record a planned required CACE gate before execution.
 *
 * The requirement is represented as the latest failing state for the gate,
 * hash-bound to the admitted request/plan. Promotion therefore remains blocked
 * until broker-validated evidence for the same capability records a pass.
 */
[[nodiscard]] VerificationGateRecord record_cace_verification_requirement(
    GenerationLineageStore& store,
    std::string_view generation_id,
    std::string_view capability_id,
    std::string_view request_evidence_hash);

/**
 * Record broker-validated CACE evidence in generation lineage.
 *
 * CACE evidence is deliberately non-recommending: recommend_keep,
 * efficiency_ok, and diversity_ok remain false. A qualifying capability only
 * updates its required verification gate. Hidden/ablation evaluation and the
 * external promotion boundary remain independent.
 */
[[nodiscard]] CaceEvidenceReceipt record_cace_evaluation_evidence(
    GenerationLineageStore& store,
    std::string_view generation_id,
    const CaceEvaluationEvidence& evidence);

} // namespace expert_robot::growth
