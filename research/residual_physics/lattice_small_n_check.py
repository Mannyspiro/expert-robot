#!/usr/bin/env python3
"""Small-N Ising-limit lattice Hamiltonian sanity checks.

Implements the Eq. (2) spin-chain Hamiltonian transcribed in
formal/RESIDUAL_PHYSICS_LITERATURE_TRIAGE.md. This is an implementation check,
not a reproduction of the paper's gauge-invariant link-cut entropy or N=17 result.
Requires NumPy.
"""
from __future__ import annotations
import json, math
import numpy as np


def build_hamiltonian(n_sites: int, g2a: float = 1.6, a: float = 1.0) -> np.ndarray:
    if n_sites < 3:
        raise ValueError("Use n_sites >= 3 to avoid degenerate periodic-neighbor conventions")
    if g2a <= 0 or a <= 0:
        raise ValueError("g2a and a must be positive")
    g2 = g2a / a
    J = -3.0 * g2 / 16.0
    hx = 1.0 / (a * math.sqrt(g2))**2
    dim = 1 << n_sites
    H = np.zeros((dim, dim), dtype=np.float64)
    # Computational basis bit 0 -> z=+1; bit 1 -> z=-1.
    for state in range(dim):
        z = [1 - 2 * ((state >> i) & 1) for i in range(n_sites)]
        diagonal = 0.0
        for i in range(n_sites):
            diagonal += J * z[i] * z[(i + 1) % n_sites] - 2.0 * J * z[i]
            nu = (1.0 / math.sqrt(2.0)) ** (z[(i - 1) % n_sites] + z[(i + 1) % n_sites])
            H[state, state ^ (1 << i)] += hx * nu
        H[state, state] += diagonal
    return H


def entropy_of_pure_state(psi: np.ndarray, n_sites: int, a_sites: list[int]) -> tuple[float, float, float]:
    b_sites = [i for i in range(n_sites) if i not in set(a_sites)]
    dim_a, dim_b = 1 << len(a_sites), 1 << len(b_sites)
    amplitudes = np.empty((dim_a, dim_b), dtype=np.complex128)
    for state, amp in enumerate(psi):
        a_idx = sum(((state >> site) & 1) << j for j, site in enumerate(a_sites))
        b_idx = sum(((state >> site) & 1) << j for j, site in enumerate(b_sites))
        amplitudes[a_idx, b_idx] = amp
    rho_a = amplitudes @ amplitudes.conj().T
    rho_a = (rho_a + rho_a.conj().T) / 2
    vals = np.linalg.eigvalsh(rho_a)
    trace_err = abs(float(np.trace(rho_a).real) - 1.0)
    min_eig = float(vals.min())
    positive = np.clip(vals, 0.0, None)
    entropy = -float(sum(p * math.log(p) for p in positive if p > 0))
    return entropy, trace_err, min_eig


def run(n_sites: int = 4) -> dict:
    H = build_hamiltonian(n_sites)
    herm_err = float(np.max(np.abs(H - H.T)))
    eigvals, eigvecs = np.linalg.eigh(H)
    residuals = [float(np.linalg.norm(H @ eigvecs[:, k] - eigvals[k] * eigvecs[:, k])) for k in range(len(eigvals))]
    norm_errors = [abs(float(np.vdot(eigvecs[:, k], eigvecs[:, k]).real) - 1.0) for k in range(len(eigvals))]
    entropies, rho_trace_errors, rho_min_eigs = [], [], []
    cut = n_sites // 2
    a_sites, b_sites = list(range(cut)), list(range(cut, n_sites))
    for idx in (0, len(eigvals)//2, len(eigvals)-1):
        s_a, tr_a, min_a = entropy_of_pure_state(eigvecs[:, idx], n_sites, a_sites)
        s_b, tr_b, min_b = entropy_of_pure_state(eigvecs[:, idx], n_sites, b_sites)
        entropies.append({"eigenstate_index": idx, "energy": float(eigvals[idx]), "entropy_A_nats": s_a, "entropy_B_nats": s_b, "entropy_difference": abs(s_a-s_b)})
        rho_trace_errors.extend([tr_a, tr_b])
        rho_min_eigs.extend([min_a, min_b])
    checks = {
        "hermitian": herm_err < 1e-12,
        "eigenpair_residuals_small": max(residuals) < 1e-10,
        "eigenvectors_normalized": max(norm_errors) < 1e-12,
        "reduced_density_trace_one": max(rho_trace_errors) < 1e-10,
        "reduced_density_psd_with_roundoff": min(rho_min_eigs) > -1e-10,
        "pure_state_entropy_partition_symmetry": max(x["entropy_difference"] for x in entropies) < 1e-10,
    }
    return {
        "schema_version": 1,
        "status": "pass" if all(checks.values()) else "fail",
        "scope": "small-N Ising-limit Hamiltonian implementation checks only; not a reproduction of published SU(2) gauge-link Page curve",
        "source_equation": "Ebner et al., PRD 110, 014505 (2024), Eq. (2)",
        "parameters": {"n_sites": n_sites, "g2a": 1.6, "lattice_spacing_a": 1.0, "J": -3.0*1.6/16.0, "h_x": 1.0/1.6, "basis_order": "bit 0 => sigma_z=+1; bit 1 => sigma_z=-1", "periodic_boundary": True},
        "hilbert_dimension": int(H.shape[0]),
        "checks": checks,
        "diagnostics": {"max_abs_hermiticity_error": herm_err, "max_eigenpair_residual": max(residuals), "max_eigenvector_norm_error": max(norm_errors), "max_rho_trace_error": max(rho_trace_errors), "minimum_rho_eigenvalue": min(rho_min_eigs)},
        "sample_eigenstates": entropies,
        "promotion": False,
        "limitations": ["Spin-site bipartition is not automatically the paper's gauge-invariant link-cut partition.", "Only small-N implementation sanity is checked; no N=17 benchmark or physical interpretation is claimed.", "Floating-point eigensolver output is numerical evidence, not a Lean proof."]
    }


if __name__ == "__main__":
    result = run(4)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "pass":
        raise SystemExit(1)
