#include "expert_robot/research/strategy_qualification.hpp"

#include "expert_robot/growth/ablation_evidence.hpp"
#include "expert_robot/sha256.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace expert_robot::research {
namespace {

std::string experience_hash(
    const ResearchStrategyPlan& strategy,
    const ResearchStrategyExperience& experience) {
    std::ostringstream out;
    out << std::setprecision(17)
        << "strategy_id=" << strategy.strategy_id << "\n"
        << "signature=" << strategy.signature << "\n"
        << "domain=" << experience.domain << "\n"
        << "attempts=" << experience.attempts << "\n"
        << "verified_progresses="
        << experience.verified_progresses << "\n"
        << "target_verifications="
        << experience.target_verifications << "\n"
        << "dead_end_escapes="
        << experience.dead_end_escapes << "\n"
        << "total_resource_cost="
        << experience.total_resource_cost << "\n"
        << "smoothed_verified_rate="
        << experience.smoothed_verified_rate() << "\n"
        << "smoothed_target_rate="
        << experience.smoothed_target_rate();

    return sha256_hex(out.str());
}

std::string step_credit_hash(
    const std::vector<StrategyStepCredit>& credits) {
    std::ostringstream out;
    out << std::boolalpha
        << std::setprecision(17);

    for (const auto& credit : credits) {
        out
            << "removed_index="
            << credit.ablation.removed_index << "\n"
            << "removed_kind="
            << proof_route_kind_name(
                credit.ablation.removed_kind) << "\n"
            << "ablated_strategy_id="
            << credit.ablation.ablated_strategy_id << "\n"
            << "verified_rate_drop="
            << credit.verified_rate_drop << "\n"
            << "ablated_cost_ratio="
            << credit.ablated_cost_ratio << "\n"
            << "importance_score="
            << credit.importance_score << "\n"
            << "enough_cases="
            << credit.enough_cases << "\n"
            << "verification_critical="
            << credit.verification_critical << "\n"
            << "efficiency_critical="
            << credit.efficiency_critical << "\n"
            << "important="
            << credit.important << "\n";
    }

    return sha256_hex(out.str());
}

std::string packet_hash(
    const StrategyQualificationPacket& packet) {
    std::ostringstream out;
    out << std::boolalpha
        << "strategy_id=" << packet.strategy_id << "\n"
        << "signature=" << packet.signature << "\n"
        << "experience_hash=" << packet.experience_hash << "\n"
        << "holdout_hash=" << packet.holdout_hash << "\n"
        << "step_credit_hash=" << packet.step_credit_hash << "\n"
        << "experience_sufficient="
        << packet.experience_sufficient << "\n"
        << "holdout_sufficient="
        << packet.holdout_sufficient << "\n"
        << "step_evidence_sufficient="
        << packet.step_evidence_sufficient << "\n"
        << "ready_for_external_review="
        << packet.ready_for_external_review << "\n"
        << "requires_explicit_promotion="
        << packet.requires_explicit_promotion;

    return sha256_hex(out.str());
}

} // namespace

void validate_strategy_qualification_policy(
    const StrategyQualificationPolicy& p) {
    if (p.minimum_completed_executions <= 0) {
        throw std::invalid_argument(
            "strategy qualification minimum executions must be positive");
    }

    for (const double value : {
             p.minimum_smoothed_verified_rate,
             p.maximum_average_resource_cost}) {
        if (!std::isfinite(value) ||
            value < 0.0 ||
            value > 1.0) {
            throw std::invalid_argument(
                "strategy qualification thresholds must be in [0,1]");
        }
    }
}

StrategyQualificationPacket
build_strategy_qualification_packet(
    const ResearchStrategyPlan& strategy,
    const ResearchStrategyExperience& experience,
    const eval::AblationResult& holdout_ablation,
    std::vector<StrategyStepCredit> step_credits,
    const StrategyQualificationPolicy& policy) {
    validate_strategy_qualification_policy(
        policy);

    if (strategy.strategy_id.empty() ||
        strategy.signature.empty() ||
        strategy.steps.empty()) {
        throw std::invalid_argument(
            "strategy qualification requires a complete strategy identity");
    }

    if (experience.strategy_id !=
        strategy.strategy_id) {
        throw std::invalid_argument(
            "strategy qualification experience belongs to a different strategy");
    }

    std::stable_sort(
        step_credits.begin(),
        step_credits.end(),
        [](const StrategyStepCredit& a,
           const StrategyStepCredit& b) {
            return a.ablation.removed_index <
                   b.ablation.removed_index;
        });

    StrategyQualificationPacket packet;
    packet.strategy_id =
        strategy.strategy_id;
    packet.signature =
        strategy.signature;
    packet.title =
        strategy.title;
    packet.experience =
        experience;
    packet.holdout_ablation =
        holdout_ablation;
    packet.step_credits =
        std::move(step_credits);

    packet.experience_sufficient =
        experience.attempts >=
            policy.minimum_completed_executions &&
        experience.smoothed_verified_rate() >=
            policy.minimum_smoothed_verified_rate &&
        experience.average_resource_cost() <=
            policy.maximum_average_resource_cost;

    packet.holdout_sufficient =
        holdout_ablation.enough_cases &&
        holdout_ablation.verification_ok &&
        (!policy.require_holdout_keep ||
         holdout_ablation.recommend_keep);

    if (strategy.steps.size() <= 1U) {
        packet.step_evidence_sufficient = true;
    } else {
        const bool complete =
            packet.step_credits.size() ==
            strategy.steps.size();

        const bool all_match =
            complete &&
            std::all_of(
                packet.step_credits.begin(),
                packet.step_credits.end(),
                [&](const StrategyStepCredit& credit) {
                    return
                        credit.ablation.parent_strategy_id ==
                            strategy.strategy_id &&
                        credit.ablation.removed_index <
                            strategy.steps.size() &&
                        credit.ablation.removed_kind ==
                            strategy.steps[
                                credit.ablation.removed_index] &&
                        credit.enough_cases &&
                        (!policy.
                             require_all_multistep_ablation_credit ||
                         credit.important);
                });

        packet.step_evidence_sufficient =
            all_match;
    }

    packet.ready_for_external_review =
        packet.experience_sufficient &&
        packet.holdout_sufficient &&
        packet.step_evidence_sufficient;

    packet.requires_explicit_promotion = true;

    if (!packet.experience_sufficient) {
        packet.rationale =
            "completed strategy history has not reached reliability/cost thresholds";
    } else if (!packet.holdout_sufficient) {
        packet.rationale =
            "holdout ablation does not support qualification";
    } else if (!packet.step_evidence_sufficient) {
        packet.rationale =
            "step ablation evidence is incomplete or indicates removable strategy steps";
    } else {
        packet.rationale =
            "strategy evidence is review-ready; explicit external promotion remains required";
    }

    packet.experience_hash =
        experience_hash(
            strategy,
            experience);
    packet.holdout_hash =
        growth::ablation_evidence_hash(
            holdout_ablation);
    packet.step_credit_hash =
        step_credit_hash(
            packet.step_credits);
    packet.packet_hash =
        packet_hash(packet);

    return packet;
}

} // namespace expert_robot::research
