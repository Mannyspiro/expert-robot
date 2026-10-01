#include "expert_robot/cognition/personality.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>
#include <string>

namespace expert_robot::cognition {
namespace {

double clamp01(double value) {
    return std::clamp(value, 0.0, 1.0);
}

void require_unit(double value, const char* name) {
    if (!std::isfinite(value) || value < 0.0 || value > 1.0) {
        throw std::invalid_argument(std::string(name) + " must be finite and within [0,1]");
    }
}

} // namespace

void validate_personality(const PersonalityProfile& p) {
    require_unit(p.openness, "openness");
    require_unit(p.conscientiousness, "conscientiousness");
    require_unit(p.persistence, "persistence");
    require_unit(p.skepticism, "skepticism");
    require_unit(p.novelty_seeking, "novelty_seeking");
    require_unit(p.risk_tolerance, "risk_tolerance");
    require_unit(p.abstraction_bias, "abstraction_bias");
    require_unit(p.compression_drive, "compression_drive");
}

void validate_logical_assessment(const LogicalAssessment& x) {
    require_unit(x.evidence_strength, "evidence_strength");
    require_unit(x.expected_success, "expected_success");
    require_unit(x.expected_information_gain, "expected_information_gain");
    require_unit(x.contradiction_risk, "contradiction_risk");
    require_unit(x.decomposition_value, "decomposition_value");
    require_unit(x.counterexample_value, "counterexample_value");
    require_unit(x.abstraction_value, "abstraction_value");
    require_unit(x.compression_value, "compression_value");
    require_unit(x.representation_switch_value, "representation_switch_value");
    require_unit(x.current_route_progress, "current_route_progress");
    require_unit(x.branch_cost, "branch_cost");
}

PersonalityProfile math_researcher_personality() {
    return PersonalityProfile{
        .openness = 0.90,
        .conscientiousness = 0.98,
        .persistence = 0.90,
        .skepticism = 0.98,
        .novelty_seeking = 0.80,
        .risk_tolerance = 0.55,
        .abstraction_bias = 0.70,
        .compression_drive = 0.85,
    };
}

std::string_view cognitive_action_name(CognitiveAction action) {
    switch (action) {
        case CognitiveAction::ContinueCurrentRoute: return "continue_current_route";
        case CognitiveAction::ExploreNovelRoute: return "explore_novel_route";
        case CognitiveAction::DecomposeProblem: return "decompose_problem";
        case CognitiveAction::SeekCounterexample: return "seek_counterexample";
        case CognitiveAction::AbstractGeneralize: return "abstract_generalize";
        case CognitiveAction::CompressSimplify: return "compress_simplify";
        case CognitiveAction::SwitchRepresentation: return "switch_representation";
        case CognitiveAction::IntensifyVerification: return "intensify_verification";
        case CognitiveAction::ConserveCompute: return "conserve_compute";
        case CognitiveAction::Count: break;
    }
    return "unknown";
}

PersonalityExecutive::PersonalityExecutive(PersonalityProfile profile)
    : profile_(profile) {
    validate_personality(profile_);
}

const PersonalityProfile& PersonalityExecutive::profile() const noexcept {
    return profile_;
}

ExecutiveDecision PersonalityExecutive::decide(
    const LogicalAssessment& logic,
    const InteroceptiveState& interoception,
    const ExecutiveBias& affect) const {
    validate_logical_assessment(logic);

    // Validate the transient state this module consumes.
    for (const auto value : {
             interoception.resource_pressure,
             interoception.cognitive_strain,
             interoception.stagnation,
             interoception.novelty,
             interoception.surprise,
             interoception.uncertainty,
             interoception.attention_demand,
             interoception.route_repetition,
             interoception.verified_progress,
             interoception.goal_persistence,
             affect.exploration_drive,
             affect.persistence_drive,
             affect.attention_allocation,
             affect.strategy_switch_pressure,
             affect.compute_conservation}) {
        require_unit(value, "executive transient input");
    }

    ExecutiveDecision d;

    d.continue_score = clamp01(
        0.24 * profile_.persistence
        + 0.16 * profile_.conscientiousness
        + 0.18 * affect.persistence_drive
        + 0.18 * logic.expected_success
        + 0.16 * logic.current_route_progress
        + 0.08 * logic.evidence_strength
        - 0.18 * affect.strategy_switch_pressure
        - 0.14 * logic.branch_cost
        - 0.12 * interoception.stagnation);

    d.explore_score = clamp01(
        0.20 * profile_.openness
        + 0.18 * profile_.novelty_seeking
        + 0.16 * profile_.risk_tolerance
        + 0.16 * affect.exploration_drive
        + 0.14 * logic.expected_information_gain
        + 0.10 * interoception.novelty
        + 0.06 * interoception.surprise);

    d.decompose_score = clamp01(
        0.20 * profile_.conscientiousness
        + 0.18 * profile_.persistence
        + 0.24 * logic.decomposition_value
        + 0.16 * interoception.stagnation
        + 0.12 * interoception.cognitive_strain
        + 0.10 * affect.attention_allocation);

    d.counterexample_score = clamp01(
        0.25 * profile_.skepticism
        + 0.22 * logic.counterexample_value
        + 0.18 * logic.contradiction_risk
        + 0.12 * interoception.uncertainty
        + 0.10 * interoception.surprise
        + 0.08 * profile_.openness
        + 0.05 * affect.attention_allocation);

    d.abstract_score = clamp01(
        0.24 * profile_.abstraction_bias
        + 0.18 * profile_.openness
        + 0.22 * logic.abstraction_value
        + 0.14 * logic.expected_information_gain
        + 0.12 * interoception.novelty
        + 0.10 * affect.exploration_drive);

    d.compress_score = clamp01(
        0.26 * profile_.compression_drive
        + 0.18 * profile_.conscientiousness
        + 0.24 * logic.compression_value
        + 0.12 * logic.evidence_strength
        + 0.10 * interoception.verified_progress
        + 0.10 * affect.attention_allocation);

    d.switch_score = clamp01(
        0.18 * profile_.openness
        + 0.14 * profile_.novelty_seeking
        + 0.22 * logic.representation_switch_value
        + 0.20 * affect.strategy_switch_pressure
        + 0.14 * interoception.stagnation
        + 0.12 * interoception.route_repetition);

    d.verification_score = clamp01(
        0.28 * profile_.skepticism
        + 0.22 * profile_.conscientiousness
        + 0.16 * logic.contradiction_risk
        + 0.12 * interoception.uncertainty
        + 0.10 * interoception.surprise
        + 0.07 * (1.0 - logic.evidence_strength)
        + 0.05 * affect.attention_allocation);

    d.conserve_score = clamp01(
        0.55 * affect.compute_conservation
        + 0.25 * interoception.resource_pressure
        + 0.12 * logic.branch_cost
        + 0.08 * interoception.route_repetition);

    d.abandon_pressure = clamp01(
        0.22 * logic.branch_cost
        + 0.20 * affect.strategy_switch_pressure
        + 0.18 * interoception.route_repetition
        + 0.16 * interoception.stagnation
        + 0.14 * interoception.resource_pressure
        + 0.10 * (1.0 - logic.expected_success)
        - 0.14 * profile_.persistence
        - 0.08 * logic.current_route_progress);

    // Breakthrough mode does not create a new action. It increases the scores
    // of actions that escape a local basin while preserving verification.
    d.breakthrough_mode = affect.breakthrough_mode;
    if (d.breakthrough_mode) {
        d.explore_score = clamp01(d.explore_score + 0.10 * profile_.openness);
        d.decompose_score = clamp01(d.decompose_score + 0.10 * profile_.persistence);
        d.counterexample_score = clamp01(d.counterexample_score + 0.08 * profile_.skepticism);
        d.switch_score = clamp01(d.switch_score + 0.12 * profile_.novelty_seeking);
        d.abstract_score = clamp01(d.abstract_score + 0.08 * profile_.abstraction_bias);
    }

    const std::array<double, static_cast<std::size_t>(CognitiveAction::Count)> scores = {
        d.continue_score,
        d.explore_score,
        d.decompose_score,
        d.counterexample_score,
        d.abstract_score,
        d.compress_score,
        d.switch_score,
        d.verification_score,
        d.conserve_score,
    };

    std::size_t best = 0;
    for (std::size_t i = 1; i < scores.size(); ++i) {
        // Stable deterministic tie-break: lower enum value wins.
        if (scores[i] > scores[best]) best = i;
    }
    d.action = static_cast<CognitiveAction>(best);

    // Search-policy modules can never lower these invariants.
    d.verification_rigor_multiplier = 1.0;
    d.authority_delta = 0.0;

    return d;
}

} // namespace expert_robot::cognition
