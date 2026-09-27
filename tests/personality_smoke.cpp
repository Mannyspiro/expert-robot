#include "expert_robot/cognition/personality.hpp"

#include <cassert>
#include <cmath>
#include <stdexcept>
#include <string_view>

namespace {

bool unit(double x) {
    return std::isfinite(x) && x >= 0.0 && x <= 1.0;
}

expert_robot::cognition::InteroceptiveState quiet_state() {
    using namespace expert_robot::cognition;
    InteroceptiveState s;
    s.resource_pressure = 0.10;
    s.cognitive_strain = 0.15;
    s.stagnation = 0.05;
    s.novelty = 0.20;
    s.surprise = 0.10;
    s.uncertainty = 0.20;
    s.attention_demand = 0.40;
    s.route_repetition = 0.05;
    s.verified_progress = 0.80;
    s.goal_persistence = 0.90;
    return s;
}

expert_robot::cognition::ExecutiveBias calm_affect() {
    using namespace expert_robot::cognition;
    ExecutiveBias a;
    a.exploration_drive = 0.35;
    a.persistence_drive = 0.90;
    a.attention_allocation = 0.50;
    a.strategy_switch_pressure = 0.10;
    a.compute_conservation = 0.10;
    a.breakthrough_mode = false;
    return a;
}

} // namespace

int main() {
    using namespace expert_robot::cognition;

    const auto profile = math_researcher_personality();
    PersonalityExecutive executive(profile);

    assert(profile.openness == 0.90);
    assert(profile.skepticism == 0.98);
    assert(profile.conscientiousness == 0.98);

    // A productive route with strong evidence should keep going.
    LogicalAssessment productive;
    productive.evidence_strength = 0.90;
    productive.expected_success = 0.95;
    productive.expected_information_gain = 0.40;
    productive.current_route_progress = 0.90;
    productive.branch_cost = 0.10;
    productive.decomposition_value = 0.10;
    productive.counterexample_value = 0.10;
    productive.abstraction_value = 0.20;
    productive.compression_value = 0.30;
    productive.representation_switch_value = 0.10;

    const auto productive_decision =
        executive.decide(productive, quiet_state(), calm_affect());
    assert(productive_decision.action == CognitiveAction::ContinueCurrentRoute);
    assert(productive_decision.continue_score > productive_decision.switch_score);

    // Strong contradiction should activate the skeptical/counterexample path.
    LogicalAssessment contradictory;
    contradictory.evidence_strength = 0.20;
    contradictory.expected_success = 0.20;
    contradictory.expected_information_gain = 0.70;
    contradictory.contradiction_risk = 1.00;
    contradictory.counterexample_value = 1.00;
    contradictory.decomposition_value = 0.40;
    contradictory.abstraction_value = 0.30;
    contradictory.compression_value = 0.10;
    contradictory.representation_switch_value = 0.30;
    contradictory.current_route_progress = 0.10;
    contradictory.branch_cost = 0.25;

    auto contradiction_state = quiet_state();
    contradiction_state.uncertainty = 0.90;
    contradiction_state.surprise = 0.90;
    contradiction_state.cognitive_strain = 0.70;
    contradiction_state.verified_progress = 0.10;

    auto skeptical_affect = calm_affect();
    skeptical_affect.attention_allocation = 1.00;
    skeptical_affect.strategy_switch_pressure = 0.55;
    skeptical_affect.exploration_drive = 0.65;

    const auto contradiction_decision =
        executive.decide(contradictory, contradiction_state, skeptical_affect);
    assert(contradiction_decision.action == CognitiveAction::SeekCounterexample);
    assert(
        contradiction_decision.counterexample_score >
        contradiction_decision.continue_score);

    // Stagnation plus a valuable representation change should switch domains.
    LogicalAssessment stuck;
    stuck.evidence_strength = 0.20;
    stuck.expected_success = 0.15;
    stuck.expected_information_gain = 0.80;
    stuck.contradiction_risk = 0.25;
    stuck.decomposition_value = 0.60;
    stuck.counterexample_value = 0.40;
    stuck.abstraction_value = 0.60;
    stuck.compression_value = 0.20;
    stuck.representation_switch_value = 1.00;
    stuck.current_route_progress = 0.05;
    stuck.branch_cost = 0.40;

    auto stalled_state = quiet_state();
    stalled_state.stagnation = 1.00;
    stalled_state.route_repetition = 1.00;
    stalled_state.novelty = 0.90;
    stalled_state.surprise = 0.80;
    stalled_state.uncertainty = 0.80;
    stalled_state.cognitive_strain = 0.85;
    stalled_state.verified_progress = 0.00;

    auto breakthrough_affect = calm_affect();
    breakthrough_affect.exploration_drive = 0.80;
    breakthrough_affect.persistence_drive = 0.65;
    breakthrough_affect.attention_allocation = 0.80;
    breakthrough_affect.strategy_switch_pressure = 0.90;
    breakthrough_affect.compute_conservation = 0.20;
    breakthrough_affect.breakthrough_mode = true;

    const auto stuck_decision =
        executive.decide(stuck, stalled_state, breakthrough_affect);
    assert(stuck_decision.breakthrough_mode);
    assert(stuck_decision.action == CognitiveAction::SwitchRepresentation);
    assert(stuck_decision.switch_score > stuck_decision.continue_score);

    // A mature result with strong compression opportunity should seek a simpler
    // representation/generalization instead of gratuitous exploration.
    LogicalAssessment compression;
    compression.evidence_strength = 0.90;
    compression.expected_success = 0.70;
    compression.expected_information_gain = 0.40;
    compression.decomposition_value = 0.15;
    compression.counterexample_value = 0.15;
    compression.abstraction_value = 0.30;
    compression.compression_value = 1.00;
    compression.representation_switch_value = 0.10;
    compression.current_route_progress = 0.50;
    compression.branch_cost = 0.10;

    auto compression_state = quiet_state();
    compression_state.verified_progress = 0.90;
    auto focused_affect = calm_affect();
    focused_affect.attention_allocation = 0.80;
    focused_affect.persistence_drive = 0.55;

    const auto compression_decision =
        executive.decide(compression, compression_state, focused_affect);
    assert(compression_decision.action == CognitiveAction::CompressSimplify);

    for (const auto* decision : {
             &productive_decision,
             &contradiction_decision,
             &stuck_decision,
             &compression_decision}) {
        for (const double value : {
                 decision->continue_score,
                 decision->explore_score,
                 decision->decompose_score,
                 decision->counterexample_score,
                 decision->abstract_score,
                 decision->compress_score,
                 decision->switch_score,
                 decision->verification_score,
                 decision->conserve_score,
                 decision->abandon_pressure}) {
            assert(unit(value));
        }
        assert(decision->verification_rigor_multiplier == 1.0);
        assert(decision->authority_delta == 0.0);
        assert(cognitive_action_name(decision->action) != std::string_view("unknown"));
    }

    bool rejected = false;
    try {
        PersonalityProfile invalid = profile;
        invalid.openness = 1.1;
        PersonalityExecutive bad(invalid);
        (void)bad;
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    return 0;
}
