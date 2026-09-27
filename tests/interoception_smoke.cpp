#include "expert_robot/cognition/interoception.hpp"
#include "expert_robot/cognition/neuromodulation.hpp"

#include <cassert>
#include <cmath>
#include <stdexcept>

namespace {

bool unit(double x) {
    return std::isfinite(x) && x >= 0.0 && x <= 1.0;
}

} // namespace

int main() {
    using namespace expert_robot::cognition;

    InteroceptionConfig config;
    config.smoothing = 1.0; // inspect raw deterministic targets in this test
    ArtificialInteroception interoception(config);

    InteroceptiveSensors healthy;
    healthy.cpu_load = 0.40;
    healthy.gpu_load = 0.50;
    healthy.ram_pressure = 0.40;
    healthy.vram_pressure = 0.40;
    healthy.context_utilization = 0.30;
    healthy.work_queue_pressure = 0.20;
    healthy.recent_proof_success_rate = 0.80;
    healthy.verified_progress = 0.70;
    healthy.expected_verified_progress = 0.60;
    healthy.theorem_novelty = 0.50;
    healthy.theorem_graph_coverage = 0.40;
    healthy.route_repetition = 0.10;
    healthy.uncertainty = 0.20;
    healthy.contradiction_rate = 0.00;
    healthy.goal_persistence = 0.80;

    const auto first = interoception.observe(healthy);
    assert(first.state.resource_pressure == 0.0);
    assert(first.state.stagnation == 0.0);
    assert(first.state.reward_prediction_error > 0.0);
    assert(first.cognitive_signals.verified_progress == 0.70);

    InteroceptiveSensors stalled = healthy;
    stalled.cpu_load = 0.95;
    stalled.gpu_load = 0.95;
    stalled.ram_pressure = 0.95;
    stalled.vram_pressure = 0.95;
    stalled.context_utilization = 0.98;
    stalled.work_queue_pressure = 0.95;
    stalled.recent_proof_success_rate = 0.00;
    stalled.verified_progress = 0.00;
    stalled.expected_verified_progress = 0.70;
    stalled.theorem_novelty = 0.85;
    stalled.theorem_graph_coverage = 0.25;
    stalled.route_repetition = 1.00;
    stalled.uncertainty = 0.90;
    stalled.contradiction_rate = 0.60;
    stalled.consecutive_failures = 12;
    stalled.attempts_since_verified_progress = 20;
    stalled.seconds_since_verified_progress = 300.0;
    stalled.goal_persistence = 0.90;

    const auto second = interoception.observe(stalled);
    assert(second.state.resource_pressure > 0.5);
    assert(second.state.stagnation > 0.9);
    assert(second.state.cognitive_strain > 0.7);
    assert(second.state.surprise > 0.5);
    assert(second.state.novelty > 0.8);
    assert(second.state.reward_prediction_error < 0.0);

    SoftwareNeuromodulators neuromodulators(
        NeuromodulationConfig{
            .smoothing = 1.0,
            .dopamine_baseline = 0.20,
            .norepinephrine_baseline = 0.20,
            .acetylcholine_baseline = 0.20,
            .serotonin_baseline = 0.20,
            .breakthrough_stagnation_threshold = 0.65,
            .breakthrough_switch_threshold = 0.60,
        });

    const auto bias = neuromodulators.update(second.cognitive_signals);
    assert(bias.breakthrough_mode);
    assert(bias.strategy_switch_pressure >= 0.60);
    assert(bias.compute_conservation > 0.4);
    assert(bias.verification_rigor_multiplier == 1.0);
    assert(bias.authority_delta == 0.0);

    for (const double x : {
             second.state.resource_pressure,
             second.state.cognitive_strain,
             second.state.stagnation,
             second.state.novelty,
             second.state.surprise,
             second.state.uncertainty,
             second.state.attention_demand,
             bias.exploration_drive,
             bias.persistence_drive,
             bias.attention_allocation,
             bias.strategy_switch_pressure,
             bias.compute_conservation}) {
        assert(unit(x));
    }

    bool rejected = false;
    try {
        InteroceptiveSensors invalid;
        invalid.context_utilization = 1.2;
        (void)interoception.observe(invalid);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    return 0;
}
