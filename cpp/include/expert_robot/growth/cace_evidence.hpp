#pragma once

#include "expert_robot/growth/generation_lineage.hpp"

#include <optional>
#include <string>

namespace expert_robot::growth {

struct CaceValidatedEvidence {
    std::string generation_id;
    std::string capability_id;
    std::string evaluation_evidence_hash;

    bool passed{false};
    bool qualification_capability{false};
};

struct CaceEvidenceReceipt {
    EvaluationRecord evaluation;
    std::optional<VerificationGateRecord> verification_gate;
};

/**
 * Records evidence that has already passed the external CACE broker validator.
 *
 * This adapter cannot grant external approval or promotion authority. A
 * qualifying CACE capability contributes a required verification gate whose
 * latest result controls whether promotion is blocked.
 */
[[nodiscard]] CaceEvidenceReceipt record_cace_evidence(
    GenerationLineageStore& store,
    CaceValidatedEvidence evidence);

} // namespace expert_robot::growth
