#include "expert_robot/cognition/controller.hpp"

#include <cassert>

int main() {
    using namespace expert_robot::cognition;

    InteroceptionConfig i_cfg;
    i_cfg.smoothing = 1.0;

    NeuromodulationConfig n_cfg;
    n_cfg.smoothing = 1.0;

    CognitionController cognition(
        math_researcher_personality(),
        i_cfg,
        n_cfg);

    InteroceptiveSensors sensors;
    sensors.cpu_load = 0.50;
    sensors.gpu_load = 0.50;
    sensors.ram_pressure = 0.40;
    sensors.vram_pressure = 0.40;
    sensors.context_utilization = 0.40;
    sensors.work_queue_pressure = 0.30;
    sensors.recent_proof_success_rate = 0.00;
    sensors.verified_progress = 0.00;
    sensors.expected_verified_progress = 0.65;
    sensors.theorem_novelty = 0.90;
    sensors.theorem_graph_coverage = 0.20;
    sensors.route_repetition = 1.00;
    sensors.uncertainty = 0.85;
    sensors.contradiction_rate = 0.15;
    sensors.consecutive_failures = 12;
    sensors.attempts_since_verified_progress = 20;
    sensors.seconds_since_verified_progress = 300.0;
    sensors.goal_persistence = 0.90;

    LogicalAssessment logic;
    logic.evidence_strength = 0.15;
    logic.expected_success = 0.15;
    logic.expected_information_gain = 0.85;
    logic.contradiction_risk = 0.20;
    logic.decomposition_value = 0.70;
    logic.counterexample_value = 0.35;
    logic.abstraction_value = 0.65;
    logic.compression_value = 0.15;
    logic.representation_switch_value = 1.00;
    logic.current_route_progress = 0.05;
    logic.branch_cost = 0.30;

    const auto cycle = cognition.step(sensors, logic);

    assert(cycle.interoception.state.stagnation > 0.9);
    assert(cycle.affect.breakthrough_mode);
    assert(
        cycle.decision.action ==
        CognitiveAction::SwitchRepresentation);
    assert(cycle.decision.verification_rigor_multiplier == 1.0);
    assert(cycle.decision.authority_delta == 0.0);
    assert(cognition.personality().skepticism == 0.98);

    const auto personality_before = cognition.personality();
    cognition.reset_transient_state();

    assert(cognition.interoceptive_state().step == 0);
    assert(cognition.neuromodulator_state().step == 0);
    assert(cognition.personality().openness == personality_before.openness);
    assert(cognition.personality().skepticism == personality_before.skepticism);

    return 0;
}
