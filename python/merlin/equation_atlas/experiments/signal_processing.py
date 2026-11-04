"""Deterministic signal-processing checks for RWEA-041–050.

These are synthetic numerical consistency checks, not empirical validation.
"""
from __future__ import annotations

import numpy as np


def run_signal_checks() -> dict:
    # DFT round trip and Parseval under NumPy's forward-unscaled convention.
    x = np.array([0.25, -1.0, 0.5, 2.0, -0.75, 0.125, 1.25, -0.5], dtype=float)
    spectrum = np.fft.fft(x)
    reconstructed = np.fft.ifft(spectrum)
    parseval_lhs = float(np.sum(np.abs(x) ** 2))
    parseval_rhs = float(np.sum(np.abs(spectrum) ** 2) / x.size)

    # Linear convolution theorem with zero-padding to the exact linear length.
    a = np.array([1.0, -2.0, 0.5, 3.0])
    b = np.array([0.25, 1.5, -1.0])
    n_linear = a.size + b.size - 1
    spectral_convolution = np.fft.ifft(
        np.fft.fft(a, n_linear) * np.fft.fft(b, n_linear)
    ).real
    direct_convolution = np.convolve(a, b)

    # A 17 Hz sinusoid sampled at 20 Hz aliases to a 3 Hz magnitude peak.
    fs, f_input, count = 20.0, 17.0, 100
    t = np.arange(count, dtype=float) / fs
    samples = np.sin(2.0 * np.pi * f_input * t)
    frequencies = np.fft.rfftfreq(count, d=1.0 / fs)
    magnitudes = np.abs(np.fft.rfft(samples))
    alias_peak_hz = float(frequencies[1 + np.argmax(magnitudes[1:])])

    # Entropy and mutual-information identities on exact finite distributions.
    def entropy(probabilities):
        p = np.asarray(probabilities, dtype=float)
        p = p[p > 0.0]
        return float(-np.sum(p * np.log2(p)))

    p_joint_independent = np.array([[0.25, 0.25], [0.25, 0.25]])
    p_joint_equal = np.array([[0.5, 0.0], [0.0, 0.5]])

    def mutual_information(joint):
        px = joint.sum(axis=1)
        py = joint.sum(axis=0)
        total = 0.0
        for i in range(joint.shape[0]):
            for j in range(joint.shape[1]):
                if joint[i, j] > 0.0:
                    total += joint[i, j] * np.log2(
                        joint[i, j] / (px[i] * py[j])
                    )
        return float(total)

    # Uniform quantization error for deterministic midpoint-offset samples.
    delta = 1.0 / 64.0
    phase = (np.arange(4096, dtype=float) + 0.5) / 4096.0
    quantizer_input = delta * (np.floor(np.arange(4096) / 16.0) + phase - 128.0)
    quantized = delta * np.round(quantizer_input / delta)
    quantization_error_variance = float(np.var(quantized - quantizer_input))
    ideal_quantization_variance = delta * delta / 12.0

    return {
        "experiment_set": "merlin-rwea-041-050-signal-checks-v0.1",
        "seed": "not_applicable_deterministic_constructed_inputs",
        "dft": {
            "round_trip_max_abs_error": float(np.max(np.abs(reconstructed - x))),
            "parseval_absolute_error": abs(parseval_lhs - parseval_rhs),
            "parseval_time_energy": parseval_lhs,
            "parseval_frequency_energy": parseval_rhs,
        },
        "convolution": {
            "linear_convolution_max_abs_error": float(
                np.max(np.abs(spectral_convolution - direct_convolution))
            ),
            "output_length": int(n_linear),
        },
        "sampling_aliasing": {
            "sample_rate_hz": fs,
            "input_frequency_hz": f_input,
            "expected_alias_frequency_hz": abs(f_input - fs),
            "observed_fft_peak_hz": alias_peak_hz,
        },
        "information_theory": {
            "fair_binary_entropy_bits": entropy([0.5, 0.5]),
            "deterministic_entropy_bits": entropy([1.0, 0.0]),
            "independent_mutual_information_bits": mutual_information(
                p_joint_independent
            ),
            "perfectly_correlated_mutual_information_bits": mutual_information(
                p_joint_equal
            ),
        },
        "quantization": {
            "step": delta,
            "measured_error_variance": quantization_error_variance,
            "ideal_uniform_error_variance": ideal_quantization_variance,
            "relative_variance_error": abs(
                quantization_error_variance - ideal_quantization_variance
            ) / ideal_quantization_variance,
            "model_assumption": "deterministic uniform quantization error coverage; not a universal ADC noise model",
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_signal_checks(), indent=2, sort_keys=True))
