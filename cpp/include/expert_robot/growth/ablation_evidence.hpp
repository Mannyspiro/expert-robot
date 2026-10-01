#pragma once

#include "expert_robot/eval/math_eval.hpp"
#include "expert_robot/growth/generation_lineage.hpp"

#include <string>
#include <string_view>

namespace expert_robot::growth {

[[nodiscard]] std::string ablation_evidence_hash(
    const eval::AblationResult& result);

[[nodiscard]] EvaluationRecord record_ablation_evidence(
    GenerationLineageStore& store,
    std::string_view generation_id,
    std::string_view evaluator,
    const eval::AblationResult& result);

} // namespace expert_robot::growth
