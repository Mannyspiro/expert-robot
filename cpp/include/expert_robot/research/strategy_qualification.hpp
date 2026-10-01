#pragma once

#include "expert_robot/eval/math_eval.hpp"
#include "expert_robot/research/route_memory.hpp"
#include "expert_robot/research/strategy_ablation.hpp"
#include "expert_robot/research/strategy_planner.hpp"

#include <optional>
#include <string>
#include <vector>

namespace expert_robot::research {

struct StrategyQualificationPolicy {
    long long minimum_completed_executions{8};
    double minimum_smoothed_verified_rate{0.55};
    double maximum_average_resource_cost{0.75};

    bool require_validation_keep{true};
    bool require_holdout_keep{true};
    bool require_all_multistep_ablation_credit{true};
};

struct StrategyQualificationPacket {
    std::string strategy_id;
    std::string signature;
    std::string title;

    ResearchStrategyExperience experience;
    eval::AblationResult validation_ablation;
    std::optional<eval::AblationResult> holdout_ablation;
    std::vector<StrategyStepCredit> step_credits;

    std::string experience_hash;
    std::string validation_hash;
    std::string holdout_hash;
    std::string step_credit_hash;
    std::string packet_hash;

    bool experience_sufficient{false};
    bool validation_sufficient{false};
    bool holdout_sufficient{false};
    bool step_evidence_sufficient{false};
    bool ready_for_holdout_confirmation{false};
    bool ready_for_external_review{false};
    bool requires_explicit_promotion{true};

    std::string rationale;
};

void validate_strategy_qualification_policy(
    const StrategyQualificationPolicy& policy);

[[nodiscard]] StrategyQualificationPacket
build_strategy_qualification_packet(
    const ResearchStrategyPlan& strategy,
    const ResearchStrategyExperience& experience,
    const eval::AblationResult& validation_ablation,
    std::vector<StrategyStepCredit> step_credits,
    const StrategyQualificationPolicy& policy = {});

[[nodiscard]] StrategyQualificationPacket
confirm_strategy_holdout(
    StrategyQualificationPacket packet,
    const eval::AblationResult& holdout_ablation,
    const StrategyQualificationPolicy& policy = {});

} // namespace expert_robot::research
