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

    NeuromodulationConfig config;
    config.smoothing = 1.0;
    SoftwareNeuromodulators system(config);

    CognitiveSignals progress;
    progress.verified_progress = 1.0;
    progress.reward_prediction_error = 0.8;
    progress.novelty = 0.5;
    progress.goal_persistence = 0.8;

    const auto progress_bias = system.update(progress);
    const auto after_progress = system.state();
    assert(after_progress.dopamine_like > config.dopamine_baseline);
    assert(progress_bias.verification_rigor_multiplier == 1.0);
    assert(progress_bias.authority_delta == 0.0);

    system.reset();

    CognitiveSignals surprise;
    surprise.surprise = 1.0;
    surprise.uncertainty = 0.8;
    surprise.attention_demand = 0.9;
    surprise.goal_persistence = 0.5;

    const auto surprise_bias = system.update(surprise);
    const auto after_surprise = system.state();
    assert(after_surprise.norepinephrine_like > config.norepinephrine_baseline);
    assert(after_surprise.acetylcholine_like > config.acetylcholine_baseline);
    assert(surprise_bias.attention_allocation > 0.5);

    system.reset();

    CognitiveSignals stalled;
    stalled.surprise = 0.8;
    stalled.uncertainty = 0.8;
    stalled.novelty = 0.6;
    stalled.attention_demand = 0.8;
    stalled.stagnation = 1.0;
    stalled.route_repetition = 1.0;
    stalled.goal_persistence = 0.9;

    const auto stalled_bias = system.update(stalled);
    assert(stalled_bias.strategy_switch_pressure >=
           config.breakthrough_switch_threshold);
    assert(stalled_bias.breakthrough_mode);

    system.reset();

    CognitiveSignals exhausted = stalled;
    exhausted.resource_pressure = 1.0;
    exhausted.goal_persistence = 0.2;
    const auto exhausted_bias = system.update(exhausted);
    assert(exhausted_bias.compute_conservation > 0.6);
    assert(exhausted_bias.persistence_drive < stalled_bias.persistence_drive);

    for (const double x : {
             system.state().dopamine_like,
             system.state().norepinephrine_like,
             system.state().acetylcholine_like,
             system.state().serotonin_like,
             exhausted_bias.exploration_drive,
             exhausted_bias.persistence_drive,
             exhausted_bias.attention_allocation,
             exhausted_bias.strategy_switch_pressure,
             exhausted_bias.compute_conservation}) {
        assert(unit(x));
    }

    bool rejected = false;
    try {
        CognitiveSignals invalid;
        invalid.uncertainty = 1.5;
        (void)system.update(invalid);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    return 0;
}
