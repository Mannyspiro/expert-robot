"""Deterministic stochastic-model sanity checks for RWEA-051–060.

Synthetic checks only; these do not establish empirical model validity.
"""
import numpy as np


def run_stochastic_checks():
    # Markov chain with a known stationary distribution.
    transition = np.array([
        [0.8, 0.2, 0.0],
        [0.1, 0.7, 0.2],
        [0.0, 0.3, 0.7],
    ])
    stationary = np.array([0.2, 0.4, 0.4])
    stationarity_residual = float(np.max(np.abs(stationary @ transition - stationary)))

    # Continuous-time three-state ring: driven clockwise/reverse rates.
    clockwise, counterclockwise = 2.0, 1.0
    pi = np.full(3, 1.0 / 3.0)
    q = np.zeros((3, 3))
    for i in range(3):
        q[i, (i + 1) % 3] = clockwise
        q[i, (i - 1) % 3] = counterclockwise
    entropy_rate_over_kb = 0.0
    for i in range(3):
        for j in range(3):
            if i != j and q[i, j] > 0 and q[j, i] > 0:
                flux = pi[i] * q[i, j] - pi[j] * q[j, i]
                entropy_rate_over_kb += 0.5 * flux * np.log(
                    (pi[i] * q[i, j]) / (pi[j] * q[j, i])
                )

    # Detailed-balance ring must have zero entropy production.
    q_eq = np.zeros((3, 3))
    for i in range(3):
        q_eq[i, (i + 1) % 3] = 1.5
        q_eq[i, (i - 1) % 3] = 1.5
    entropy_equilibrium_over_kb = 0.0
    for i in range(3):
        for j in range(3):
            if i != j and q_eq[i, j] > 0:
                flux = pi[i] * q_eq[i, j] - pi[j] * q_eq[j, i]
                entropy_equilibrium_over_kb += 0.5 * flux * np.log(
                    (pi[i] * q_eq[i, j]) / (pi[j] * q_eq[j, i])
                )

    # Brownian increment variance: deterministic seed, finite-sample diagnostic.
    rng = np.random.default_rng(20261104)
    dt, paths, steps = 0.01, 12000, 100
    increments = rng.normal(0.0, np.sqrt(dt), size=(paths, steps))
    brownian_terminal = increments.sum(axis=1)
    brownian_variance = float(np.var(brownian_terminal, ddof=1))

    # Beta-Binomial conjugate posterior.
    alpha_prior, beta_prior, successes, failures = 2.0, 2.0, 7.0, 3.0
    alpha_post = alpha_prior + successes
    beta_post = beta_prior + failures
    posterior_mean = alpha_post / (alpha_post + beta_post)

    # Scalar Kalman measurement update.
    prior_variance, measurement_variance = 2.0, 1.0
    gain = prior_variance / (prior_variance + measurement_variance)
    posterior_variance = (1.0 - gain) * prior_variance

    # Ornstein-Uhlenbeck stationary variance: dX=-kXdt+sqrt(2D)dW.
    kappa, diffusion = 2.0, 3.0
    ou_stationary_variance = diffusion / kappa

    return {
        "experiment_set": "merlin-rwea-051-060-stochastic-checks-v0.1",
        "seed": 20261104,
        "markov": {
            "stationarity_residual": stationarity_residual,
            "transition_row_sum_error": float(np.max(np.abs(transition.sum(axis=1) - 1.0))),
        },
        "brownian": {
            "time_horizon": dt * steps,
            "observed_terminal_variance": brownian_variance,
            "theoretical_terminal_variance": dt * steps,
        },
        "bayesian_beta_binomial": {
            "posterior_alpha": alpha_post,
            "posterior_beta": beta_post,
            "posterior_mean": posterior_mean,
        },
        "kalman_scalar": {
            "gain": gain,
            "posterior_variance": posterior_variance,
        },
        "ornstein_uhlenbeck": {
            "kappa": kappa,
            "diffusion": diffusion,
            "theoretical_stationary_variance": ou_stationary_variance,
        },
        "entropy_production": {
            "driven_ring_sigma_over_kb": float(entropy_rate_over_kb),
            "equilibrium_ring_sigma_over_kb": float(entropy_equilibrium_over_kb),
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_stochastic_checks(), indent=2, sort_keys=True))
