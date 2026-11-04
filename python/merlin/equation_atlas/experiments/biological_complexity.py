"""Deterministic synthetic checks for RWEA-061–070.

These tests exercise toy mathematical identities and numerical invariants;
they are not empirical validation of biological or physical models.
"""
import numpy as np


def _rule30(state):
    n = len(state)
    out = np.zeros_like(state)
    for i in range(n):
        left, center, right = state[(i-1) % n], state[i], state[(i+1) % n]
        out[i] = left ^ (center | right)
    return out


def _giant_component_size(adjacency):
    seen = set()
    best = 0
    for start in range(len(adjacency)):
        if start in seen:
            continue
        stack, size = [start], 0
        seen.add(start)
        while stack:
            node = stack.pop()
            size += 1
            for neighbor, connected in enumerate(adjacency[node]):
                if connected and neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        best = max(best, size)
    return best


def run_biological_complexity_checks():
    # Periodic finite-difference Laplacian: diffusion-only mass conservation.
    rng = np.random.default_rng(61070)
    field = rng.random(32)
    lap = np.roll(field, 1) - 2.0 * field + np.roll(field, -1)
    diffusion_mass_residual = float(abs(np.sum(lap)))

    # Logistic model: positive initial population remains in (0, K).
    r, capacity, n0, dt, steps = 0.8, 100.0, 12.0, 0.01, 1000
    population = n0
    for _ in range(steps):
        population += dt * r * population * (1.0 - population / capacity)

    # Replicator equation with constant fitness; Euler step preserves sum
    # algebraically for this update, and positive frequencies remain positive
    # for the selected small step.
    x = np.array([0.2, 0.3, 0.5], dtype=float)
    fitness = np.array([1.0, 1.5, 0.5])
    mean_fitness = float(x @ fitness)
    x_next = x + 0.01 * x * (fitness - mean_fitness)

    # Rule 30 has a deterministic, inspectable next row.
    ca = np.zeros( nine := 9, dtype=np.int8)
    ca[nine // 2] = 1
    ca_next = _rule30(ca)

    # Identical-frequency Kuramoto network: coupling reduces phase spread.
    theta = np.array([-1.0, -0.3, 0.4, 1.1], dtype=float)
    initial_spread = float(np.std(theta))
    adjacency = np.ones((4, 4), dtype=float) - np.eye(4)
    coupling, step = 1.0, 0.005
    for _ in range(800):
        delta = theta[None, :] - theta[:, None]
        theta += step * coupling * np.sum(adjacency * np.sin(delta), axis=1)
    final_spread = float(np.std(theta))
    order_parameter = float(abs(np.mean(np.exp(1j * theta))))

    # Mutual information: independent variables -> 0; perfectly paired -> 1 bit.
    independent = np.full((2, 2), 0.25)
    paired = np.array([[0.5, 0.0], [0.0, 0.5]])
    def mutual_information(joint):
        px, py = joint.sum(axis=1), joint.sum(axis=0)
        total = 0.0
        for i in range(2):
            for j in range(2):
                if joint[i, j] > 0:
                    total += joint[i, j] * np.log2(joint[i, j] / (px[i] * py[j]))
        return float(total)

    # A simple finite graph has a component of size three.
    graph = np.array([
        [0, 1, 0, 0, 0],
        [1, 0, 1, 0, 0],
        [0, 1, 0, 0, 0],
        [0, 0, 0, 0, 1],
        [0, 0, 0, 1, 0],
    ], dtype=int)

    return {
        "experiment_set": "merlin-rwea-061-070-biological-complexity-v0.1",
        "seed": 61070,
        "reaction_diffusion": {"periodic_laplacian_mass_residual": diffusion_mass_residual},
        "logistic": {"population_after_steps": float(population), "carrying_capacity": capacity},
        "replicator": {"frequency_sum": float(x_next.sum()), "minimum_frequency": float(x_next.min())},
        "cellular_automaton": {"rule": 30, "initial": ca.tolist(), "next": ca_next.tolist()},
        "kuramoto": {"initial_phase_spread": initial_spread, "final_phase_spread": final_spread, "order_parameter": order_parameter},
        "mutual_information": {"independent_bits": mutual_information(independent), "paired_bits": mutual_information(paired)},
        "percolation_graph": {"largest_component_size": _giant_component_size(graph)},
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_biological_complexity_checks(), indent=2, sort_keys=True))
