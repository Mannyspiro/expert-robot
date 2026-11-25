#!/usr/bin/env python3
"""Plot a complete synthetic calibration receipt without executing the experiment.

Receipts with rejected executions lacking numerical metrics or a bare FP64
fallback are deliberately rejected; inspect their JSON rather than inventing a
plot. Conclusions are derived from the supplied interval, not fixed wording.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

FLOOR = 1e-16
COLORS = {"pass": "#265da8", "selected": "#087f83", "reject": "#b43f36", "control": "#747f8e"}


def load_data(receipt_path, protocol_path):
    receipt_bytes, protocol_bytes = receipt_path.read_bytes(), protocol_path.read_bytes()
    receipt, protocol = json.loads(receipt_bytes), json.loads(protocol_bytes)
    digest = hashlib.sha256(json.dumps(protocol, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != receipt["protocol_sha256"]:
        raise ValueError("Protocol identity disagrees with receipt")
    if receipt["trained_language_model_evaluated"] or protocol["trained_language_model_evaluated"]:
        raise ValueError("This renderer labels only the synthetic fixture")
    rows, selected = receipt["validation"], receipt["selection"]["selected_candidate"]
    if len(rows) != 8 or len({r["candidate"]["name"] for r in rows}) != 8:
        raise ValueError("Expected the eight unique frozen validation records")
    threshold = float(re.search(r"max absolute output error <= ([0-9.eE+-]+)", protocol["selection"])[1])
    for row in rows:
        if any(k not in row for k in ("max_abs_output_error", "max_abs_arithmetic_error_vs_rounded_inputs", "max_abs_input_quantization_error")):
            raise ValueError("Incomplete candidate metrics; inspect the receipt directly")
        if bool(row["equivalence_gate_passed"]) != (row["max_abs_output_error"] <= threshold):
            raise ValueError("Recorded accuracy gate disagrees with its declared threshold")
        for field in ("max_abs_output_error", "max_abs_arithmetic_error_vs_rounded_inputs", "max_abs_input_quantization_error"):
            if not math.isfinite(row[field]) or row[field] < 0:
                raise ValueError("Invalid error value in receipt")
    test = receipt["test"]
    baseline, chosen = test["baseline"], test["selected"]
    if chosen["candidate"]["name"] != selected:
        raise ValueError("Held-out candidate does not match frozen selection")
    delta = test["paired_nll_delta_selected_minus_baseline"]
    interval = test["approximate_95pct_paired_normal_interval"]
    if any(k not in chosen for k in ("max_abs_output_error", "mean_teacher_kl")) or "method" not in chosen["candidate"]:
        raise ValueError("Bare reference fallback has no comparable error plot; inspect the receipt directly")
    if not (len(interval) == 2 and all(math.isfinite(x) for x in [delta, *interval]) and interval[0] <= delta <= interval[1]):
        raise ValueError("Invalid paired interval")
    if chosen["max_abs_output_error"] <= 0 or min(baseline["mean_teacher_kl"], chosen["mean_teacher_kl"]) <= 0:
        raise ValueError("Ratio/log plots require positive errors and KL; inspect zero or rounded-negative values directly")
    conclusion = ("lower synthetic sample perplexity" if interval[1] < 0 else
                  "higher synthetic sample perplexity" if interval[0] > 0 else "no established perplexity gain")
    derived = {
        "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "protocol_sha256": digest, "accuracy_gate": threshold,
        "test_max_output_error_reduction_factor": baseline["max_abs_output_error"] / chosen["max_abs_output_error"],
        "test_teacher_kl_reduction_factor": baseline["mean_teacher_kl"] / chosen["mean_teacher_kl"],
        "test_relative_ppl_change_ppm": 1e6 * math.expm1(delta),
        "test_relative_ppl_change_95pct_interval_ppm": [1e6 * math.expm1(x) for x in interval],
        "interval_method": "Monotone transform 1e6*expm1(x) of the receipt's approximate paired normal NLL interval; relative PPL, not absolute PPL difference.",
        "plotting_floor": {"value": FLOOR, "scope": "Zero input-quantization error in panel B only; shown with a left-pointing triangle and labeled zero."},
        "scope": "synthetic conditional-token fixture; no trained language model; no experiment rerun",
        "perplexity_conclusion": conclusion,
        "interval_includes_zero": interval[0] <= 0 <= interval[1],
    }
    return receipt, protocol, derived


def label(candidate):
    method = {"raw": "Raw", "centered": "Centered", "block": f"Block {candidate['block_rows']}"}[candidate["method"]]
    return f"{method} · {candidate['dtype'].replace('float', 'FP')}" + (" (control)" if candidate["role"] == "control" else "")


def render(receipt, protocol, derived, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "text.color": "#1b2a3c", "axes.labelcolor": "#354457",
                         "xtick.color": "#354457", "ytick.color": "#354457"})
    rows, selected = receipt["validation"], receipt["selection"]["selected_candidate"]
    test, threshold = receipt["test"], derived["accuracy_gate"]
    fig = plt.figure(figsize=(17, 12), facecolor="white")
    fig.suptitle("PARALLAX NUMERICAL CALIBRATION", fontsize=23, fontweight="bold", y=.974)
    fig.text(.5, .935, "Synthetic conditional-token fixture · no trained language model · no weight training", ha="center", fontsize=14)
    ratio = derived['test_max_output_error_reduction_factor']
    error_claim = f"{ratio:.2f}× smaller held-out maximum output error" if ratio >= 1 else f"Held-out error ratio baseline/selected: {ratio:.2f}"
    fig.text(.5, .890, error_claim + "; " + derived["perplexity_conclusion"], ha="center", fontsize=16, weight="bold")
    fig.text(.5, .858, f"8 frozen variants · {rows[0]['tokens']} validation traces · {test['selected']['tokens']} held-out traces · selected on validation only", ha="center", fontsize=11)
    axa = fig.add_axes([.17, .51, .33, .28])
    axb = fig.add_axes([.59, .51, .35, .28])
    axc = fig.add_axes([.17, .20, .33, .17])
    axd = fig.add_axes([.59, .20, .35, .17])
    for ax in (axa, axb, axc, axd):
        ax.spines[["right", "top"]].set_visible(False)
        ax.grid(axis="x", color="#e7ecf1", linewidth=.7)
        ax.set_axisbelow(True)
    for ax in (axa, axb):
        ax.set_xscale("log")
        maximum_error = max(r[k] for r in rows for k in ("max_abs_output_error", "max_abs_arithmetic_error_vs_rounded_inputs", "max_abs_input_quantization_error"))
        ax.set_xlim(FLOOR / 2, max(2, maximum_error * 4))
        ax.set_xticks([1e-16, 1e-12, 1e-8, 1e-4, 1])
        ax.set_ylim(7.6, -.6)
        ax.set_yticks(range(8))
    axa.set_yticklabels([label(r["candidate"]) for r in rows])
    axb.set_yticklabels([])
    axa.set_title("A  Validation output accuracy", loc="left", fontsize=14, weight="bold", pad=28)
    axa.text(0, 1.02, f"Accuracy gate ≤ {threshold:.0e}; × marks rejection", transform=axa.transAxes, fontsize=10)
    axa.axvspan(threshold, axa.get_xlim()[1], color=COLORS["reject"], alpha=.05)
    axa.axvline(threshold, color=COLORS["reject"], linestyle="--", linewidth=1)
    for i, row in enumerate(rows):
        status = "control" if row["candidate"]["role"] == "control" else "pass" if row["equivalence_gate_passed"] else "reject"
        if row["candidate"]["name"] == selected:
            status = "selected"
            for ax in (axa, axb):
                ax.axhspan(i - .36, i + .36, color=COLORS["selected"], alpha=.06)
            axa.get_yticklabels()[i].set_weight("bold")
        value = row["max_abs_output_error"]
        axa.scatter(value, i, marker={"reject": "x", "selected": "*", "control": "D"}.get(status, "o"),
                    s=105 if status == "selected" else 48, color=COLORS[status], zorder=3)
        axa.annotate(f"{value:.2e}", (value, i), xytext=(7, 0), textcoords="offset points", va="center", fontsize=9, color=COLORS[status])
        arithmetic, quantization = row["max_abs_arithmetic_error_vs_rounded_inputs"], row["max_abs_input_quantization_error"]
        axb.plot([arithmetic, max(quantization, FLOOR)], [i, i], color="#c6cdd7", linewidth=1)
        axb.scatter(arithmetic, i, color="#77549a", s=44, zorder=3)
        axb.scatter(max(quantization, FLOOR), i, color="#c78920", s=48, marker="<" if quantization == 0 else "s", zorder=3)
        if quantization == 0:
            axb.annotate("zero", (FLOOR, i), xytext=(7, 10), textcoords="offset points", fontsize=9, color="#89611d")
    axa.set_xlabel("Max |output − FP64 reference| (log scale)", labelpad=8)
    axb.set_title("B  Arithmetic and input rounding", loc="left", fontsize=14, weight="bold", pad=28)
    axb.legend(handles=[Line2D([], [], marker="o", color="#77549a", linestyle="", label="Arithmetic"),
                        Line2D([], [], marker="s", color="#c78920", linestyle="", label="Input quantization")],
               frameon=False, fontsize=10, ncol=2, loc="lower left", bbox_to_anchor=(-.02, 1.0))
    axb.set_xlabel("Maximum absolute error (log scale)", labelpad=8)
    rejected = sum(r["candidate"]["dtype"] == "float16" and not r["equivalence_gate_passed"] for r in rows)
    total_fp16 = sum(r["candidate"]["dtype"] == "float16" for r in rows)
    fig.text(.17, .452, f"{rejected}/{total_fp16} FP16 variants rejected. FP64 control excluded from selection.", fontsize=10)
    fig.text(.17, .433, "Star: selected by validation NLL after passing the accuracy gate.", fontsize=10, color=COLORS["selected"])
    fig.text(.59, .452, "Rows match A. Zero is placed at 10⁻¹⁶; positive values are unchanged.", fontsize=10)
    fig.text(.59, .433, "Arithmetic uses a rounded-input reference; maxima are not additive.", fontsize=10)
    axc.set_title("C  Held-out divergence from the teacher", loc="left", fontsize=14, weight="bold", pad=20)
    axc.set_xscale("log")
    kls = [test[key]["mean_teacher_kl"] for key in ("baseline", "selected")]
    axc.set_xlim(min(kls) / 10, max(kls) * 10)
    axc.set_ylim(-.65, 1.65)
    axc.set_yticks([0, 1], [label(test["selected"]["candidate"]), label(test["baseline"]["candidate"])])
    for y, key, color in ((1, "baseline", COLORS["pass"]), (0, "selected", COLORS["selected"])):
        kl = test[key]["mean_teacher_kl"]
        axc.scatter(kl, y, s=85, color=color, zorder=3)
        axc.annotate(f"{kl:.3e}", (kl, y), xytext=(9, 0), textcoords="offset points", va="center", fontsize=11)
    axc.set_xlabel("Mean KL(teacher ∥ candidate), nats (log scale)", labelpad=8)
    axd.set_title("D  Held-out relative perplexity change", loc="left", fontsize=14, weight="bold", pad=20)
    point = derived["test_relative_ppl_change_ppm"]
    lo, hi = derived["test_relative_ppl_change_95pct_interval_ppm"]
    extent = max(2.0, 1.25 * max(abs(lo), abs(hi)))
    axd.set(xlim=(-extent, extent), ylim=(-1, 1), yticks=[])
    axd.axvline(0, color="#526174", linestyle="--", linewidth=1.2)
    axd.errorbar(point, 0, xerr=[[point - lo], [hi - point]], fmt="o", color="#425c7f", capsize=7, markersize=8, linewidth=2)
    interval_label = "95% interval includes zero" if derived["interval_includes_zero"] else "95% interval excludes zero"
    axd.text(.5, .80, interval_label, ha="center", transform=axd.transAxes, fontsize=12, weight="bold")
    axd.text(.5, .14, f"{point:+.3f} ppm  [{lo:+.3f}, {hi:+.3f}]", ha="center", transform=axd.transAxes, fontsize=11)
    axd.set_xlabel("(Selected PPL / baseline PPL − 1) × 10⁶\nPositive values mean higher perplexity", labelpad=8)
    a, b = test["baseline"], test["selected"]
    fig.text(.17, .127, f"Held-out max output error: {a['max_abs_output_error']:.3e} → {b['max_abs_output_error']:.3e}.", fontsize=10)
    fig.text(.17, .107, f"Teacher KL ratio baseline/selected: {derived['test_teacher_kl_reduction_factor']:.1f}; numerical fidelity only.", fontsize=10)
    fig.text(.59, .116, "PPL interval: exp-transform of the recorded paired normal NLL interval.", fontsize=10)
    fig.text(.59, .096, f"PPL {a['perplexity']:.8f} → {b['perplexity']:.8f}; " + derived["perplexity_conclusion"], fontsize=10)
    fig.text(.05, .057, "Fixed random inputs/readout; synthetic teacher-sampled tokens. Intervals concern independent synthetic traces, not natural-language generalization.", fontsize=10)
    fig.text(.05, .034, f"Existing receipt only; no experiment rerun. Receipt SHA-256: {derived['receipt_sha256'][:16]}…  |  Run: {receipt['run_id']}", fontsize=9, color="#586779")
    for suffix in ("png", "svg"):
        fig.savefig(output / f"parallax_calibration.{suffix}", dpi=200, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    receipt, protocol, derived = load_data(args.receipt, args.protocol or args.receipt.with_name("protocol.json"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    render(receipt, protocol, derived, args.output_dir)
    derived["renderer_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (args.output_dir / "calibration_figure_provenance.json").write_text(json.dumps(derived, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output_dir": str(args.output_dir), **derived}, indent=2))


if __name__ == "__main__":
    main()
