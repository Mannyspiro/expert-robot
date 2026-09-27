#include "expert_robot/cognition/interoception.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>

namespace expert_robot::cognition {
namespace {

double clamp01(double value) {
    return std::clamp(value, 0.0, 1.0);
}

double clamp11(double value) {
    return std::clamp(value, -1.0, 1.0);
}

void require_unit(double value, const char* name) {
    if (!std::isfinite(value) || value < 0.0 || value > 1.0) {
        throw std::invalid_argument(std::string(name) + " must be finite and within [0,1]");
    }
}

void require_nonnegative(double value, const char* name) {
    if (!std::isfinite(value) || value < 0.0) {
        throw std::invalid_argument(std::string(name) + " must be finite and nonnegative");
    }
}

double ema(double current, double target, double smoothing) {
    return clamp01(current + smoothing * (target - current));
}

double excess_pressure(double value, double setpoint) {
    if (value <= setpoint) return 0.0;
    const double remaining = 1.0 - setpoint;
    if (remaining <= 0.0) return value >= 1.0 ? 1.0 : 0.0;
    return clamp01((value - setpoint) / remaining);
}

double normalized_count(std::size_t count, std::size_t horizon) {
    if (horizon == 0U) return count > 0U ? 1.0 : 0.0;
    return clamp01(
        static_cast<double>(count) / static_cast<double>(horizon));
}

double normalized_time(double seconds, double horizon) {
    if (horizon <= 0.0) return seconds > 0.0 ? 1.0 : 0.0;
    return clamp01(seconds / horizon);
}

} // namespace

void validate_interoceptive_sensors(const InteroceptiveSensors& s) {
    require_unit(s.cpu_load, "cpu_load");
    require_unit(s.gpu_load, "gpu_load");
    require_unit(s.ram_pressure, "ram_pressure");
    require_unit(s.vram_pressure, "vram_pressure");
    require_unit(s.context_utilization, "context_utilization");
    require_unit(s.work_queue_pressure, "work_queue_pressure");

    require_unit(s.recent_proof_success_rate, "recent_proof_success_rate");
    require_unit(s.verified_progress, "verified_progress");
    require_unit(s.expected_verified_progress, "expected_verified_progress");
    require_unit(s.theorem_novelty, "theorem_novelty");
    require_unit(s.theorem_graph_coverage, "theorem_graph_coverage");
    require_unit(s.route_repetition, "route_repetition");
    require_unit(s.uncertainty, "uncertainty");
    require_unit(s.contradiction_rate, "contradiction_rate");
    require_nonnegative(s.seconds_since_verified_progress, "seconds_since_verified_progress");
    require_unit(s.goal_persistence, "goal_persistence");
}

void validate_interoception_config(const InteroceptionConfig& c) {
    if (!std::isfinite(c.smoothing) || c.smoothing <= 0.0 || c.smoothing > 1.0) {
        throw std::invalid_argument("smoothing must be finite and within (0,1]");
    }

    require_unit(c.cpu_setpoint, "cpu_setpoint");
    require_unit(c.gpu_setpoint, "gpu_setpoint");
    require_unit(c.ram_setpoint, "ram_setpoint");
    require_unit(c.vram_setpoint, "vram_setpoint");
    require_unit(c.context_setpoint, "context_setpoint");
    require_unit(c.queue_setpoint, "queue_setpoint");

    require_nonnegative(c.time_horizon_seconds, "time_horizon_seconds");

    const double weights =
        c.cpu_weight + c.gpu_weight + c.ram_weight +
        c.vram_weight + c.context_weight + c.queue_weight;
    if (!std::isfinite(weights) || weights <= 0.0) {
        throw std::invalid_argument("resource weights must have positive finite sum");
    }
    for (const auto value : {
             c.cpu_weight, c.gpu_weight, c.ram_weight,
             c.vram_weight, c.context_weight, c.queue_weight}) {
        if (!std::isfinite(value) || value < 0.0) {
            throw std::invalid_argument(
                "resource weights must be finite and nonnegative");
        }
    }
}

ArtificialInteroception::ArtificialInteroception(
    InteroceptionConfig config,
    InteroceptiveState initial)
    : config_(config), state_(initial) {
    validate_interoception_config(config_);
    reset(initial);
}

const InteroceptiveState& ArtificialInteroception::state() const noexcept {
    return state_;
}

const InteroceptionConfig& ArtificialInteroception::config() const noexcept {
    return config_;
}

InteroceptiveReading ArtificialInteroception::observe(
    const InteroceptiveSensors& s) {
    validate_interoceptive_sensors(s);

    const double resource_weight_sum =
        config_.cpu_weight + config_.gpu_weight + config_.ram_weight +
        config_.vram_weight + config_.context_weight + config_.queue_weight;

    const double raw_resource_pressure = clamp01(
        (
            config_.cpu_weight *
                excess_pressure(s.cpu_load, config_.cpu_setpoint) +
            config_.gpu_weight *
                excess_pressure(s.gpu_load, config_.gpu_setpoint) +
            config_.ram_weight *
                excess_pressure(s.ram_pressure, config_.ram_setpoint) +
            config_.vram_weight *
                excess_pressure(s.vram_pressure, config_.vram_setpoint) +
            config_.context_weight *
                excess_pressure(s.context_utilization, config_.context_setpoint) +
            config_.queue_weight *
                excess_pressure(s.work_queue_pressure, config_.queue_setpoint)
        ) / resource_weight_sum);

    const double failure_stagnation =
        normalized_count(s.consecutive_failures, config_.failure_horizon);
    const double attempt_stagnation =
        normalized_count(
            s.attempts_since_verified_progress,
            config_.attempt_horizon);
    const double time_stagnation =
        normalized_time(
            s.seconds_since_verified_progress,
            config_.time_horizon_seconds);

    const double raw_stagnation = clamp01(
        0.40 * failure_stagnation +
        0.35 * attempt_stagnation +
        0.25 * time_stagnation);

    const double rpe = clamp11(
        s.verified_progress - s.expected_verified_progress);

    // Surprise combines explicit prediction error with deviations from running
    // success/progress baselines and contradictions detected by the system.
    const double progress_deviation =
        std::abs(s.verified_progress - state_.progress_baseline);
    const double success_deviation =
        std::abs(s.recent_proof_success_rate - state_.success_rate_baseline);

    const double raw_surprise = clamp01(
        0.40 * std::abs(rpe) +
        0.20 * progress_deviation +
        0.15 * success_deviation +
        0.25 * s.contradiction_rate);

    const double unexplored_fraction = 1.0 - s.theorem_graph_coverage;
    const double raw_novelty = clamp01(
        0.70 * s.theorem_novelty +
        0.30 * unexplored_fraction);

    const double raw_cognitive_strain = clamp01(
        0.30 * s.uncertainty +
        0.25 * raw_stagnation +
        0.20 * s.route_repetition +
        0.15 * s.contradiction_rate +
        0.10 * raw_resource_pressure);

    const double raw_attention_demand = clamp01(
        0.30 * s.uncertainty +
        0.25 * raw_surprise +
        0.20 * s.contradiction_rate +
        0.15 * raw_novelty +
        0.10 * raw_stagnation);

    state_.resource_pressure =
        ema(state_.resource_pressure, raw_resource_pressure, config_.smoothing);
    state_.cognitive_strain =
        ema(state_.cognitive_strain, raw_cognitive_strain, config_.smoothing);
    state_.stagnation =
        ema(state_.stagnation, raw_stagnation, config_.smoothing);
    state_.novelty =
        ema(state_.novelty, raw_novelty, config_.smoothing);
    state_.surprise =
        ema(state_.surprise, raw_surprise, config_.smoothing);
    state_.uncertainty =
        ema(state_.uncertainty, s.uncertainty, config_.smoothing);
    state_.attention_demand =
        ema(state_.attention_demand, raw_attention_demand, config_.smoothing);
    state_.route_repetition =
        ema(state_.route_repetition, s.route_repetition, config_.smoothing);
    state_.verified_progress =
        ema(state_.verified_progress, s.verified_progress, config_.smoothing);
    state_.goal_persistence =
        ema(state_.goal_persistence, s.goal_persistence, config_.smoothing);

    // RPE is signed, so use a standard EMA without [0,1] clamping.
    state_.reward_prediction_error =
        std::clamp(
            state_.reward_prediction_error +
                config_.smoothing *
                    (rpe - state_.reward_prediction_error),
            -1.0,
            1.0);

    state_.progress_baseline =
        ema(
            state_.progress_baseline,
            s.verified_progress,
            config_.smoothing);
    state_.success_rate_baseline =
        ema(
            state_.success_rate_baseline,
            s.recent_proof_success_rate,
            config_.smoothing);
    state_.resource_baseline =
        ema(
            state_.resource_baseline,
            raw_resource_pressure,
            config_.smoothing);

    ++state_.step;

    CognitiveSignals signals;
    signals.verified_progress = state_.verified_progress;
    signals.reward_prediction_error = state_.reward_prediction_error;
    signals.surprise = state_.surprise;
    signals.uncertainty = state_.uncertainty;
    signals.novelty = state_.novelty;
    signals.attention_demand = state_.attention_demand;
    signals.stagnation = state_.stagnation;
    signals.route_repetition = state_.route_repetition;
    signals.resource_pressure = state_.resource_pressure;
    signals.goal_persistence = state_.goal_persistence;

    return InteroceptiveReading{
        .state = state_,
        .cognitive_signals = signals,
    };
}

void ArtificialInteroception::reset(InteroceptiveState state) {
    for (const auto value : {
             state.resource_pressure,
             state.cognitive_strain,
             state.stagnation,
             state.novelty,
             state.surprise,
             state.uncertainty,
             state.attention_demand,
             state.route_repetition,
             state.verified_progress,
             state.goal_persistence,
             state.progress_baseline,
             state.success_rate_baseline,
             state.resource_baseline}) {
        require_unit(value, "interoceptive state field");
    }
    if (!std::isfinite(state.reward_prediction_error) ||
        state.reward_prediction_error < -1.0 ||
        state.reward_prediction_error > 1.0) {
        throw std::invalid_argument(
            "interoceptive reward_prediction_error must be within [-1,1]");
    }
    state_ = state;
}

} // namespace expert_robot::cognition
