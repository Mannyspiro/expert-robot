#pragma once

#include "expert_robot/growth/generation_lineage.hpp"

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
    bool qualification_evidence{false};

    std::string authority{"qualification-only"};
    bool promotion_authority{false};
    std::string monetary_cost{"free"};

    long long wall_seconds{0};
    long long lean_checks{0};
};

void validate_cace_evaluation_evidence(
    const CaceEvaluationEvidence& evidence);

/**
 * Record broker-validated CACE evidence in generation lineage.
 *
 * The returned EvaluationRecord is deliberately non-recommending:
 * recommend_keep, efficiency_ok, and diversity_ok are always false.
 * Therefore CACE verification evidence cannot make a generation promotable
 * and cannot substitute for hidden ablation evidence or external approval.
 */
[[nodiscard]] EvaluationRecord record_cace_evaluation_evidence(
    GenerationLineageStore& store,
    std::string_view generation_id,
    const CaceEvaluationEvidence& evidence);

} // namespace expert_robot::growth
