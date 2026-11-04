"""Composed reference models built on Merlin's shared simulation interface."""
from __future__ import annotations

from typing import Callable, Sequence
import numpy as np

from .simulation import (
    SimulationConfig,
    SimulationResult,
    explicit_euler,
    periodic_diffusion_rhs,
)


def simulate_reaction_diffusion_1d(
    initial_field: Sequence[float],
    reaction_rhs: Callable[[np.ndarray, float], np.ndarray],
    diffusivity: float,
    dx: float,
    config: SimulationConfig,
    *,
    parameters: dict,
    code_revision: str = "untracked",
) -> SimulationResult:
    """Compose a user-supplied local reaction term with periodic diffusion.

    The explicit 1-D diffusion stability restriction dt*D/dx**2 <= 1/2 is
    enforced. This does not bound stiffness in the reaction term.
    """
    if diffusivity < 0 or dx <= 0:
        raise ValueError("diffusivity must be nonnegative and dx positive")
    if config.dt * diffusivity / dx**2 > 0.5 + 1e-12:
        raise ValueError("explicit diffusion stability bound violated: dt*D/dx^2 must be <= 0.5")
    diffusion = periodic_diffusion_rhs(diffusivity, dx)

    def combined(state, time):
        reaction = np.asarray(reaction_rhs(state.copy(), time), dtype=float)
        transport = diffusion(state, time)
        if reaction.shape != state.shape:
            raise ValueError("reaction RHS shape must match the field")
        return reaction + transport

    result = explicit_euler(
        initial_field,
        combined,
        config,
        model_id="reaction-diffusion-1d-periodic",
        parameters={"diffusivity": diffusivity, "dx": dx, **parameters},
        boundary_conditions="periodic",
        code_revision=code_revision,
    )
    result.metadata["composition"] = ["local_reaction", "periodic_diffusion"]
    result.metadata["diffusion_cfl_number"] = config.dt * diffusivity / dx**2
    return result


def simulate_sir(
    initial_state: Sequence[float],
    transmission: float,
    recovery: float,
    population: float,
    config: SimulationConfig,
    *,
    code_revision: str = "untracked",
) -> SimulationResult:
    """Integrate a closed-population frequency-dependent SIR system."""
    if transmission < 0 or recovery < 0 or population <= 0:
        raise ValueError("rates must be nonnegative and population positive")
    initial = np.asarray(initial_state, dtype=float)
    if initial.shape != (3,) or np.any(initial < 0):
        raise ValueError("initial_state must be [S, I, R] with nonnegative values")
    if not np.isclose(initial.sum(), population, rtol=1e-10, atol=1e-10):
        raise ValueError("initial S+I+R must equal declared population")

    def rhs(state, _time):
        susceptible, infectious, _recovered = state
        incidence = transmission * susceptible * infectious / population
        return np.array([-incidence, incidence - recovery * infectious, recovery * infectious])

    result = explicit_euler(
        initial, rhs, config, model_id="sir-closed-frequency-dependent",
        parameters={"transmission": transmission, "recovery": recovery, "population": population},
        boundary_conditions="closed-population-no-imports",
        code_revision=code_revision,
    )
    states = np.asarray(result.states)
    if np.min(states) < -1e-10:
        raise ValueError("step size produced a negative compartment; reduce dt")
    result.metadata["invariant_max_abs_population_residual"] = float(
        np.max(np.abs(states.sum(axis=1) - population))
    )
    result.metadata["composition"] = ["infection_transfer", "recovery_transfer"]
    return result


def simulate_lotka_volterra(
    initial_state: Sequence[float],
    alpha: float,
    beta: float,
    delta: float,
    gamma: float,
    config: SimulationConfig,
    *,
    code_revision: str = "untracked",
) -> SimulationResult:
    """Integrate the classical two-species predator-prey equations."""
    if min(alpha, beta, delta, gamma) < 0:
        raise ValueError("Lotka-Volterra parameters must be nonnegative")
    initial = np.asarray(initial_state, dtype=float)
    if initial.shape != (2,) or np.any(initial < 0):
        raise ValueError("initial_state must be [prey, predator] and nonnegative")

    def rhs(state, _time):
        prey, predator = state
        interaction = prey * predator
        return np.array([alpha * prey - beta * interaction,
                         delta * interaction - gamma * predator])

    result = explicit_euler(
        initial, rhs, config, model_id="lotka-volterra-classical",
        parameters={"alpha": alpha, "beta": beta, "delta": delta, "gamma": gamma},
        boundary_conditions="well-mixed-nonnegative-populations",
        code_revision=code_revision,
    )
    states = np.asarray(result.states)
    if np.min(states) < -1e-10:
        raise ValueError("step size produced a negative population; reduce dt")
    result.metadata["composition"] = ["prey_growth_and_predation", "predator_conversion_and_mortality"]
    return result
