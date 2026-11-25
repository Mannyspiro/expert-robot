#!/usr/bin/env python3
"""Render a completed CPU language-model pilot from saved records only.

The receipt's adjacent protocol.json is required. This program never imports
the model or opens its logit arrays. It checks recorded loss arithmetic and
selection consistency; it does not independently recompute logits or inference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile


BASELINE = "author_fp32"
CANDIDATE = "centered_mass_fp32"
TOKENS = 128
GATE = 1e-3
COLORS = {
    "navy": "#182c46", "teal": "#087f83", "purple": "#77549a",
    "muted": "#586779", "grid": "#e5ebf1", "red": "#b43f36",
    "pale": "#f4f7fa",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    raw = path.read_bytes()
    require(len(raw) <= 2 * 1024 * 1024, "JSON input exceeds the bounded receipt size")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key: " + key)
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Nonfinite JSON constant: " + value)

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    require(isinstance(value, dict), "Expected a JSON object")
    return value, raw


def number(value, label, *, nonnegative=False):
    require(type(value) in (int, float) and math.isfinite(value), "Invalid numeric field: " + label)
    require(not nonnegative or value >= 0, "Negative field: " + label)
    return float(value)


def same_number(actual, expected, label):
    actual = number(actual, label)
    require(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12),
            "Recorded arithmetic disagrees: " + label)


def digest(value, label):
    require(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value),
            "Invalid SHA-256 field: " + label)
    return value


def score_row(row, split, candidate, vocab_size):
    require(isinstance(row, dict), "Missing completed score row")
    require(row["split"] == split and row["candidate"] == candidate, "Score identity mismatch")
    require(type(row["scored_tokens"]) is int and row["scored_tokens"] == TOKENS,
            "Expected exactly 128 scored targets")
    require(row["finite_logits"] is True, "Score does not report finite logits")
    losses = row["per_token_losses"]
    require(isinstance(losses, list) and len(losses) == TOKENS, "Expected 128 saved token losses")
    losses = [number(x, "per_token_losses", nonnegative=True) for x in losses]
    total = math.fsum(losses)
    same_number(row["sum_nll"], total, "sum_nll")
    same_number(row["mean_nll"], total / TOKENS, "mean_nll")
    same_number(row["perplexity"], math.exp(total / TOKENS), "perplexity")
    number(row["forward_seconds"], "forward_seconds", nonnegative=True)
    logits = row["logits"]
    require(logits["filename"] == f"{split}-{candidate}-logits.npy", "Unexpected logit filename")
    require(logits["shape"] == [TOKENS, vocab_size] and logits["dtype"] == "float32",
            "Unexpected recorded logit shape or dtype")
    require(type(logits["bytes"]) is int and logits["bytes"] > TOKENS * vocab_size * 4,
            "Invalid recorded logit byte count")
    digest(logits["sha256"], "logits.sha256")
    calls = row["attention_invocations"]
    require(isinstance(calls, list) and len(calls) == 28, "Expected 28 observed attention calls")
    require([call["layer"] for call in calls] == list(range(28)), "Layer trace is out of order")
    for call in calls:
        require(call["dtype"] == "torch.float32", "Non-FP32 attention trace")
        for field in ("query_shape", "key_shape"):
            shape = call[field]
            require(isinstance(shape, list) and len(shape) == 4
                    and all(type(x) is int and x > 0 for x in shape)
                    and shape[0] == 1 and shape[2] == TOKENS, "Invalid attention shape")
        if call["mask_shape"] is not None:
            digest(call["mask_sha256"], "attention mask")
        else:
            require(call["mask_sha256"] is None, "Mask hash without a mask")
    return row


def check_drift(row):
    value = number(row["max_abs_logit_difference"], "max_abs_logit_difference", nonnegative=True)
    require(type(row["logit_gate_passed"]) is bool
            and row["logit_gate_passed"] == (value <= GATE), "Logit gate disagrees with 1e-3 threshold")
    return value


def load_data(receipt_path):
    receipt, raw = read_json(receipt_path)
    protocol, protocol_raw = read_json(receipt_path.with_name("protocol.json"))
    require(receipt["schema"] == "merlin-parallax-lm-receipt/1", "Unsupported receipt schema")
    require(protocol["schema"] == "merlin-parallax-lm-protocol/1", "Unsupported protocol schema")
    protocol_hash = sha256(canonical(protocol))
    require(digest(receipt["protocol_sha256"], "protocol_sha256") == protocol_hash,
            "Frozen protocol does not match the receipt")
    require(isinstance(receipt["run_id"], str)
            and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", receipt["run_id"]), "Invalid run identity")
    require(isinstance(receipt["source_commit"], str)
            and re.fullmatch(r"[a-f0-9]{40}", receipt["source_commit"]), "Invalid source commit")
    required_protocol = {
        "model_id": "YifeiZuo/Parallax-0.6B",
        "revision": "0cf73e2d49ea1a09a9ef85178b73ad68e019ae36",
        "model_dtype": "float32", "cpu_threads": 2, "interop_threads": 1,
        "input_positions": TOKENS, "scored_targets": TOKENS, "total_token_ids": TOKENS + 1,
        "candidates": [BASELINE, CANDIDATE], "use_cache": False, "autocast": False,
        "inference_mode": True, "test_episodes": 1, "test_forward_passes_max": 2,
        "candidate_admission": {"finite_logits": True, "max_abs_logit_difference": GATE},
        "interval": None, "production_promotion": False, "model_updates": False,
    }
    require(all(protocol[key] == value for key, value in required_protocol.items()),
            "Unsupported pilot scope or admission gate")
    require(set(protocol["splits"]) == {"validation", "test"}, "Unexpected split set")
    for split in protocol["splits"].values():
        ids = split["token_ids"]
        require(isinstance(ids, list) and len(ids) == TOKENS + 1
                and all(type(x) is int and x >= 0 for x in ids), "Invalid frozen token sequence")
        require(digest(split["token_ids_sha256"], "token sequence") == sha256(canonical(ids)),
                "Frozen token identity changed")
        digest(split["text_sha256"], "text identity")
    require(protocol["splits"]["validation"]["token_ids_sha256"]
            != protocol["splits"]["test"]["token_ids_sha256"], "Validation and test must differ")
    require(receipt["runtime"] == protocol["runtime"], "Runtime identity differs from protocol")
    for field, expected in {"trained_language_model_evaluated": True,
                            "physical_hardware_validated": False, "production_promotion": False,
                            "model_weights_changed": False}.items():
        require(receipt[field] is expected, "Unsupported receipt scope: " + field)
    model = receipt["model"]
    require(model["device"] == "cpu" and model["dtype"] == "float32" and model["layers"] == 28
            and model["training"] is False and model["threads"] == 2 and model["interop_threads"] == 1,
            "Expected the frozen 28-layer CPU FP32 model")
    vocab_size = model["vocab_size"]
    require(type(vocab_size) is int and vocab_size > 0, "Invalid vocabulary size")
    require(all(not model["loading_info"].get(key) for key in
                ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")),
            "Model loading reported unmatched checkpoint data")
    validation = receipt["validation"]
    baseline = score_row(validation["baseline"], "validation", BASELINE, vocab_size)
    candidate = validation["candidate"]
    if "rejected_reason" in candidate:
        rejection_fields = {"candidate", "split", "logit_gate_passed", "rejected_reason"}
        # The runner also persists its clock on completed rejection records.
        require(set(candidate) in (rejection_fields, rejection_fields | {"budget_checkpoint"})
                and ("budget_checkpoint" not in candidate or isinstance(candidate["budget_checkpoint"], dict))
                and candidate["candidate"] == CANDIDATE and candidate["split"] == "validation"
                and candidate["logit_gate_passed"] is False
                and isinstance(candidate["rejected_reason"], str) and candidate["rejected_reason"],
                "Invalid incomplete candidate rejection")
        candidate_complete = False
        validation_drift = validation_delta = None
    else:
        score_row(candidate, "validation", CANDIDATE, vocab_size)
        validation_drift = check_drift(candidate)
        require(candidate["attention_invocations"] == baseline["attention_invocations"],
                "Validation attention traces differ")
        candidate_complete = True
        validation_delta = candidate["mean_nll"] - baseline["mean_nll"]
    selection = receipt["selection"]
    expected_selection = (CANDIDATE if candidate_complete and candidate["logit_gate_passed"]
                          and candidate["mean_nll"] < baseline["mean_nll"] else BASELINE)
    require(selection["selected_candidate"] == expected_selection
            and selection["selected_on"] == "validation mean NLL only"
            and selection["baseline_on_exact_tie"] is True
            and selection["test_forward_passes_before_selection"] == 0
            and selection["production_promotion"] is False, "Validation-only selection is inconsistent")
    test = receipt["test"]
    reused = expected_selection == BASELINE
    require(test["episode_count"] == 1 and test["forward_passes"] == (1 if reused else 2)
            and test["confidence_interval"] is None, "Unsupported held-out episode or interval")
    test_base = score_row(test["baseline"], "test", BASELINE, vocab_size)
    chosen = score_row(test["selected"], "test", expected_selection, vocab_size)
    require(test_base["attention_invocations"] == chosen["attention_invocations"],
            "Held-out attention traces differ")
    test_drift = check_drift(test)
    differences = test["per_token_loss_differences"]
    require(isinstance(differences, list) and len(differences) == TOKENS,
            "Expected exactly 128 held-out loss differences")
    calculated = [b - a for a, b in zip(test_base["per_token_losses"], chosen["per_token_losses"])]
    for observed, expected in zip(differences, calculated):
        same_number(observed, expected, "per-token selected-minus-baseline loss")
    test_delta = math.fsum(calculated) / TOKENS
    same_number(test["paired_mean_nll_delta_selected_minus_baseline"], test_delta, "paired mean NLL delta")
    if reused:
        require(chosen == test_base and test_drift == 0 and all(x == 0 for x in differences),
                "Baseline reuse must retain the identical row and exact zero deltas")
    rows = [baseline] + ([candidate] if candidate_complete else []) + [test_base, chosen]
    derived = {
        "schema": "merlin-parallax-lm-figure-provenance/1",
        "receipt_sha256": sha256(raw), "protocol_sha256": protocol_hash,
        "protocol_file_sha256": sha256(protocol_raw), "source_commit": receipt["source_commit"],
        "run_id": receipt["run_id"], "model_id": protocol["model_id"], "revision": protocol["revision"],
        "selected_candidate": expected_selection, "held_out_baseline_reused": reused,
        "validation_candidate_has_metrics": candidate_complete,
        "validation_mean_nll_delta_candidate_minus_baseline": validation_delta,
        "held_out_mean_nll_delta_selected_minus_baseline": test_delta,
        "held_out_per_token_nll_delta_selected_minus_baseline": calculated,
        "validation_max_abs_logit_difference": validation_drift,
        "held_out_max_abs_logit_difference": test_drift, "logit_gate": GATE,
        "nll_plot_multiplier": 1e6, "nll_plot_units": "micro-nats (1 micro-nat = 1e-6 nats)",
        "perplexity_label_format": ".17g (round-trip precision for the saved float)",
        "scored_targets_per_split": TOKENS, "confidence_interval": None,
        "scope": "Single validation and held-out natural-text windows; CPU FP32 numerical pilot.",
        "limits": ["Tokens within each window are correlated; no token-IID confidence interval.",
                   "Pretraining exposure is unknown; held out only from this candidate selection.",
                   "No general language-quality or physical-chip performance claim."],
        "verification": {"recorded_loss_aggregates_recomputed": True,
                         "selection_and_reuse_consistency_checked": True,
                         "logit_arrays_opened": False, "model_executed": False,
                         "logit_drift_independently_recomputed": False},
        "recorded_scores": [{"split": row["split"], "candidate": row["candidate"],
                             "perplexity": row["perplexity"], "mean_nll": row["mean_nll"],
                             "forward_seconds": row["forward_seconds"],
                             "logits_sha256_declared": row["logits"]["sha256"]} for row in rows],
        "timing_scope": "Recorded CPU forward durations only; no chip benchmark or timing comparison.",
    }
    return receipt, derived


def render(receipt, derived, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import ScalarFormatter

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "text.color": COLORS["navy"], "axes.labelcolor": COLORS["muted"],
                         "xtick.color": COLORS["muted"], "ytick.color": COLORS["muted"],
                         "svg.hashsalt": derived["receipt_sha256"], "text.usetex": False})
    reused = derived["held_out_baseline_reused"]
    complete = derived["validation_candidate_has_metrics"]
    test = receipt["test"]
    selected_label = "Author FP32 (baseline retained)" if reused else "Centered mass-normalized FP32"
    fig = plt.figure(figsize=(16, 12.8), facecolor="white")
    fig.suptitle("PARALLAX LANGUAGE-MODEL PILOT", fontsize=23, weight="bold", y=.970)
    fig.text(.5, .938, "Natural text · original Parallax-0.6B checkpoint · local CPU FP32", ha="center", fontsize=13)
    fig.text(.5, .902, "Validation selection: " + selected_label, ha="center", fontsize=16,
             color=COLORS["teal"], weight="bold")
    fig.text(.5, .875, "128 scored targets per window · one held-out episode · weights unchanged",
             ha="center", fontsize=11, color=COLORS["muted"])

    fig.text(.06, .830, "A  Recorded perplexity", fontsize=15, weight="bold")
    ax_table = fig.add_axes([.06, .635, .49, .17])
    ax_table.axis("off")
    rows = [
        ["Validation", "Author FP32", format(receipt["validation"]["baseline"]["perplexity"], ".17g")],
        ["Validation", "Centered FP32", format(receipt["validation"]["candidate"]["perplexity"], ".17g")
         if complete else "Unavailable (rejected)"],
        ["Held-out", "Author FP32", format(test["baseline"]["perplexity"], ".17g")],
        ["Held-out", "Author FP32 · reused" if reused else "Centered FP32 · selected",
         format(test["selected"]["perplexity"], ".17g")],
    ]
    table = ax_table.table(cellText=rows, colLabels=["Window", "Recorded method", "Perplexity"],
                           colWidths=[.19, .42, .39], cellLoc="left", colLoc="left", bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False)
    table.set_fontsize(10.5)
    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor("white")
        cell.PAD = .10
        if row == 0:
            cell.set_facecolor(COLORS["navy"])
            cell.get_text().set_color("white")
            cell.get_text().set_weight("bold")
        else:
            cell.set_facecolor(COLORS["pale"] if row % 2 else "#eaf3f3")
            if column == 2:
                cell.get_text().set_fontfamily("DejaVu Sans Mono")
                cell.get_text().set_fontsize(10)
    fig.text(.06, .607, "PPL = exp(mean NLL). Numeric labels retain saved float precision.", fontsize=10)

    fig.text(.64, .830, "B  Maximum logit drift", fontsize=15, weight="bold")
    ax_drift = fig.add_axes([.72, .650, .22, .15])
    drift_values = [derived["validation_max_abs_logit_difference"], derived["held_out_max_abs_logit_difference"]]
    maximum = max([GATE] + [x for x in drift_values if x is not None])
    right = maximum * 1.35
    ax_drift.axvspan(GATE, right, color=COLORS["red"], alpha=.06)
    ax_drift.axvline(GATE, color=COLORS["red"], linestyle="--", linewidth=1.2)
    for y, value, color in ((1, drift_values[0], COLORS["purple"]), (0, drift_values[1], COLORS["teal"])):
        if value is None:
            ax_drift.text(.04, y, "Unavailable; rejected", transform=ax_drift.get_yaxis_transform(),
                          va="center", fontsize=9, color=COLORS["red"])
        else:
            ax_drift.scatter(value, y, color=color, s=65, zorder=3)
            ax_drift.annotate(format(value, ".6g"), (value, y), xytext=(7, 10),
                              textcoords="offset points", fontsize=10, color=color)
    ax_drift.set(xlim=(-right * .025, right), ylim=(-.55, 1.65), yticks=[1, 0],
                 yticklabels=["Validation\ncentered", "Held-out\nbaseline reuse" if reused else "Held-out\nselected"])
    ax_drift.tick_params(axis="y", labelsize=9)
    formatter = ScalarFormatter(useMathText=True, useOffset=False)
    formatter.set_powerlimits((0, 0))
    ax_drift.xaxis.set_major_formatter(formatter)
    ax_drift.set_xlabel("max |logit − author logit|", fontsize=10, labelpad=7)
    fig.text(.64, .607, "Dashed line: admission gate ≤ 0.001.", fontsize=10, color=COLORS["red"])

    fig.text(.06, .553, "C  Mean loss changes relative to the author baseline", fontsize=15, weight="bold")
    ax_delta = fig.add_axes([.19, .425, .68, .085])
    means = [derived["validation_mean_nll_delta_candidate_minus_baseline"],
             derived["held_out_mean_nll_delta_selected_minus_baseline"]]
    micro = [None if value is None else value * 1e6 for value in means]
    extent = max([abs(value) for value in micro if value is not None] + [0.0])
    extent = extent * 1.55 if extent else 1.0
    ax_delta.axvline(0, color=COLORS["muted"], linestyle="--", linewidth=1)
    for y, value, color in ((1, micro[0], COLORS["purple"]), (0, micro[1], COLORS["teal"])):
        if value is None:
            ax_delta.text(.02, y, "Unavailable; candidate rejected", transform=ax_delta.get_yaxis_transform(),
                          va="center", color=COLORS["red"], fontsize=10)
        else:
            ax_delta.plot([0, value], [y, y], color=color, linewidth=2, alpha=.5)
            ax_delta.scatter(value, y, color=color, s=65, zorder=3)
            label = "0 (exact baseline reuse)" if y == 0 and reused else f"{value:+.6g} µnat"
            ax_delta.annotate(label, (value, y), xytext=(8 if value >= 0 else -8, 10),
                              textcoords="offset points", ha="left" if value >= 0 else "right",
                              fontsize=10, color=color)
    ax_delta.set(xlim=(-extent, extent), ylim=(-.5, 1.6), yticks=[1, 0],
                 yticklabels=["Validation · centered", "Held-out · selected"])
    ax_delta.ticklabel_format(axis="x", style="plain", useOffset=False)
    ax_delta.set_xlabel("Mean ΔNLL (µnat per target); positive values mean higher loss", fontsize=10)
    fig.text(.06, .369, "µnat = 10⁻⁶ nats. Changes are shown directly; no confidence interval is estimated.", fontsize=10)

    fig.text(.06, .329, "D  Held-out selected-minus-baseline loss at every target position", fontsize=15, weight="bold")
    ax_tokens = fig.add_axes([.09, .125, .85, .16])
    values = [x * 1e6 for x in derived["held_out_per_token_nll_delta_selected_minus_baseline"]]
    positions = list(range(1, TOKENS + 1))
    ax_tokens.axhline(0, color=COLORS["muted"], linewidth=1)
    ax_tokens.plot(positions, values, color=COLORS["navy"], linewidth=.8, alpha=.55)
    ax_tokens.scatter(positions, values, s=13,
                      c=[COLORS["purple"] if x > 0 else COLORS["teal"] for x in values], zorder=3)
    if reused:
        ax_tokens.set_ylim(-1, 1)
        ax_tokens.set_yticks([-1, 0, 1])
        ax_tokens.text(.5, .77, "Baseline forward pass reused: all 128 deltas are exactly zero.",
                       ha="center", transform=ax_tokens.transAxes, fontsize=12, weight="bold",
                       color=COLORS["teal"], bbox={"facecolor": "white", "edgecolor": "none", "alpha": .9})
    else:
        extent_tokens = max(abs(x) for x in values)
        ax_tokens.set_ylim(-1.18 * extent_tokens, 1.18 * extent_tokens) if extent_tokens else ax_tokens.set_ylim(-1, 1)
        ax_tokens.text(.01, .94, f"Mean ΔNLL: {micro[1]:+.6g} µnat per target", va="top",
                       transform=ax_tokens.transAxes, fontsize=10,
                       bbox={"facecolor": "white", "edgecolor": "none", "alpha": .9})
    ax_tokens.set(xlim=(.5, TOKENS + .5), xticks=[1, 16, 32, 48, 64, 80, 96, 112, 128],
                  xlabel="Held-out target position (1–128; tokens within this window are correlated)",
                  ylabel="Per-token ΔNLL (µnat)")
    ax_tokens.ticklabel_format(axis="y", style="plain", useOffset=False)
    for ax in (ax_drift, ax_delta, ax_tokens):
        ax.spines[["right", "top"]].set_visible(False)
        ax.grid(axis="x" if ax is not ax_tokens else "y", color=COLORS["grid"], linewidth=.7)
        ax.set_axisbelow(True)
    fig.text(.06, .059, "Pretraining exposure is unknown. Held out only from this candidate selection; no general language-quality claim.", fontsize=10)
    fig.text(.06, .038, "CPU forward timings are diagnostic; no physical-chip benchmark. Figures use saved records and run no model inference.", fontsize=10)
    fig.text(.06, .017, f"Receipt SHA-256: {derived['receipt_sha256'][:16]}…  |  Run: {receipt['run_id']}",
             fontsize=9, color=COLORS["muted"])
    for extension in ("png", "svg"):
        metadata = {"Creator": "Merlin Parallax LM renderer", "Date": None} if extension == "svg" else {
            "Software": "Merlin Parallax LM renderer", "Description": "Saved CPU FP32 natural-text pilot; no inference rerun"}
        fig.savefig(output / f"parallax_lm_pilot.{extension}", dpi=180, facecolor="white", metadata=metadata)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt, derived = load_data(args.receipt)
    except (KeyError, TypeError, ValueError, OverflowError, OSError) as error:
        parser.error("Unsupported or inconsistent saved pilot: " + str(error))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="parallax-lm-figure-", dir=args.output_dir) as temporary:
        stage = Path(temporary)
        render(receipt, derived, stage)
        derived["renderer_sha256"] = sha256(Path(__file__).read_bytes())
        derived["outputs"] = {p.name: {"sha256": sha256(p.read_bytes()), "bytes": p.stat().st_size}
                              for p in sorted(stage.iterdir()) if p.suffix in (".png", ".svg")}
        name = "parallax_lm_figure_provenance.json"
        (stage / name).write_text(json.dumps(derived, indent=2, sort_keys=True, allow_nan=False) + "\n")
        for path in sorted(stage.iterdir()):
            path.replace(args.output_dir / path.name)
    print(json.dumps({"output_dir": str(args.output_dir), "outputs": list(derived["outputs"]),
                      "provenance": name, "receipt_sha256": derived["receipt_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
