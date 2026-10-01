#include "expert_robot/cognition/neuromodulation.hpp"

#include <algorithm>
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

double ema(double current, double target, double smoothing) {
    return clamp01(current + smoothing * (target - current));
}

} // namespace

void validate_signals(const CognitiveSignals& s) {
    require_unit(s.verified_progress, "verified_progress");
    if (!std::isfinite(s.reward_prediction_error) ||
        s.reward_prediction_error < -1.0 ||
        s.reward_prediction_error > 1.0) {
        throw std::invalid_argument(
            "reward_prediction_error must be finite and within [-1,1]");
    }
    require_unit(s.surprise, "surprise");
    require_unit(s.uncertainty, "uncertainty");
    require_unit(s.novelty, "novelty");
    require_unit(s.attention_demand, "attention_demand");
    require_unit(s.stagnation, "stagnation");
    require_unit(s.route_repetition, "route_repetition");
    require_unit(s.resource_pressure, "resource_pressure");
    require_unit(s.goal_persistence, "goal_persistence");
}

void validate_config(const NeuromodulationConfig& c) {
    if (!std::isfinite(c.smoothing) || c.smoothing <= 0.0 || c.smoothing > 1.0) {
        throw std::invalid_argument("smoothing must be finite and within (0,1]");
    }
    require_unit(c.dopamine_baseline, "dopamine_baseline");
    require_unit(c.norepinephrine_baseline, "norepinephrine_baseline");
    require_unit(c.acetylcholine_baseline, "acetylcholine_baseline");
    require_unit(c.serotonin_baseline, "serotonin_baseline");
    require_unit(c.breakthrough_stagnation_threshold, "breakthrough_stagnation_threshold");
    require_unit(c.breakthrough_switch_threshold, "breakthrough_switch_threshold");
}

SoftwareNeuromodulators::SoftwareNeuromodulators(
    NeuromodulationConfig config,
    NeuromodulatorState initial)
    : config_(config), state_(initial) {
    validate_config(config_);
    require_unit(state_.dopamine_like, "initial dopamine_like");
    require_unit(state_.norepinephrine_like, "initial norepinephrine_like");
    require_unit(state_.acetylcholine_like, "initial acetylcholine_like");
    require_unit(state_.serotonin_like, "initial serotonin_like");
}

const NeuromodulatorState& SoftwareNeuromodulators::state() const noexcept {
    return state_;
}

const NeuromodulationConfig& SoftwareNeuromodulators::config() const noexcept {
    return config_;
}

ExecutiveBias SoftwareNeuromodulators::update(const CognitiveSignals& s) {
    validate_signals(s);

    const double positive_rpe = std::max(0.0, s.reward_prediction_error);
    const double negative_rpe = std::max(0.0, -s.reward_prediction_error);

    const double dopamine_target = clamp01(
        config_.dopamine_baseline
        + 0.45 * s.verified_progress
        + 0.30 * positive_rpe
        + 0.15 * s.novelty
        - 0.25 * negative_rpe
        - 0.15 * s.stagnation);

    const double norepinephrine_target = clamp01(
        config_.norepinephrine_baseline
        + 0.40 * s.surprise
        + 0.25 * s.uncertainty
        + 0.20 * s.stagnation
        + 0.15 * s.route_repetition);

    const double acetylcholine_target = clamp01(
        config_.acetylcholine_baseline
        + 0.45 * s.attention_demand
        + 0.30 * s.uncertainty
        + 0.15 * s.novelty
        - 0.20 * s.resource_pressure);

    const double serotonin_target = clamp01(
        config_.serotonin_baseline
        + 0.45 * s.goal_persistence
        + 0.20 * s.stagnation
        + 0.10 * (1.0 - s.surprise)
        - 0.35 * s.resource_pressure);

    state_.dopamine_like = ema(
        state_.dopamine_like, dopamine_target, config_.smoothing);
    state_.norepinephrine_like = ema(
        state_.norepinephrine_like, norepinephrine_target, config_.smoothing);
    state_.acetylcholine_like = ema(
        state_.acetylcholine_like, acetylcholine_target, config_.smoothing);
    state_.serotonin_like = ema(
        state_.serotonin_like, serotonin_target, config_.smoothing);
    ++state_.step;

    ExecutiveBias bias;

    bias.exploration_drive = clamp01(
        0.35 * state_.norepinephrine_like
        + 0.25 * state_.dopamine_like
        + 0.25 * s.novelty
        + 0.15 * s.stagnation);

    bias.persistence_drive = clamp01(
        0.55 * state_.serotonin_like
        + 0.25 * state_.dopamine_like
        + 0.20 * s.goal_persistence
        - 0.30 * s.resource_pressure);

    bias.attention_allocation = clamp01(
        0.70 * state_.acetylcholine_like
        + 0.20 * s.attention_demand
        + 0.10 * s.uncertainty);

    bias.strategy_switch_pressure = clamp01(
        0.50 * state_.norepinephrine_like
        + 0.25 * s.route_repetition
        + 0.25 * s.stagnation
        - 0.20 * state_.dopamine_like);

    bias.compute_conservation = clamp01(
        0.70 * s.resource_pressure
        + 0.20 * (1.0 - bias.persistence_drive)
        + 0.10 * s.route_repetition);

    bias.breakthrough_mode =
        s.stagnation >= config_.breakthrough_stagnation_threshold &&
        bias.strategy_switch_pressure >= config_.breakthrough_switch_threshold;

    bias.verification_rigor_multiplier = 1.0;
    bias.authority_delta = 0.0;

    return bias;
}

void SoftwareNeuromodulators::reset(NeuromodulatorState state) {
    require_unit(state.dopamine_like, "reset dopamine_like");
    require_unit(state.norepinephrine_like, "reset norepinephrine_like");
    require_unit(state.acetylcholine_like, "reset acetylcholine_like");
    require_unit(state.serotonin_like, "reset serotonin_like");
    state_ = state;
}

} // namespace expert_robot::cognition
