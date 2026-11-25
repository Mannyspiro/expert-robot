#!/usr/bin/env python3
"""Freeze and execute one offline, bounded Parallax language-model pilot.

This is an isolated CPU evaluation, not a training or deployment service.
An interrupted episode cannot replay, renew its budget, or select on test data.
Completed episodes return stored receipts without loading the model again.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import importlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time

# Set before any Hugging Face or numerical dependency import.
for _key, _value in {
    "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1", "TOKENIZERS_PARALLELISM": "false",
    "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2",
}.items():
    os.environ[_key] = _value

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))
from experimental_self_healing import EvidenceLedger
from merlin.research_window import ResearchWindow
from merlin_loop_coordinator import Loop
from merlin_loop_persistence import checkpoint, restore

MAX_SECONDS = 300
MODEL_ID = "YifeiZuo/Parallax-0.6B"
REVISION = "0cf73e2d49ea1a09a9ef85178b73ad68e019ae36"
BASELINE = "author_fp32"
CANDIDATE = "centered_mass_fp32"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def file_hash(path):
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_new(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def source_hashes():
    paths = ["scripts/merlin/parallax_lm_rsi.py", "python/merlin/parallax_torch_centered.py"]
    return {path: file_hash(ROOT / path) for path in paths}


def validate_protocol(protocol):
    fixed = {"schema": "merlin-parallax-lm-protocol/1", "model_id": MODEL_ID,
             "revision": REVISION, "cpu_threads": 2, "interop_threads": 1,
             "max_wall_seconds": MAX_SECONDS, "model_dtype": "float32",
             "input_positions": 128, "scored_targets": 128, "total_token_ids": 129,
             "input_rule": "token_ids[:-1]", "target_rule": "token_ids[1:]",
             "add_special_tokens": False, "padding": False, "chat_template": False,
             "use_cache": False, "inference_mode": True, "autocast": False,
             "attention_implementation": "eager",
             "test_episodes": 1, "test_forward_passes_max": 2,
             "candidates": [BASELINE, CANDIDATE],
             "candidate_description": "centered covariance with explicit softmax-mass normalization",
             "candidate_admission": {"finite_logits": True, "max_abs_logit_difference": 0.001},
             "selection": "lowest validation mean NLL among eligible; baseline on exact tie",
             "loss": "float64 stable logsumexp minus target logit; mean over all 128 targets",
             "perplexity": "exp(mean_nll)", "loss_chunk_positions": 16,
             "interval": None, "interval_reason": "tokens within one text window are correlated",
             "pretraining_exposure": "unknown; split held out only from this candidate selection",
             "hardware_scope": "local CPU reference; no calibrated Parallax chip simulator",
             "model_downloads": False, "model_updates": False, "production_promotion": False,
             "full_logits_retained": True, "max_logit_artifacts": 4,
             "max_logit_artifact_bytes": 128 * 1024 * 1024,
             "budget_scope": "Model load, validation, selection, test and persistence; external timeout also bounds imports and finalization",
             "required_supervisor": "GNU timeout --signal=KILL 300s"}
    if any(canonical(protocol.get(key)) != canonical(value) for key, value in fixed.items()):
        raise ValueError("unsupported or altered frozen pilot scope")
    if set(protocol.get("splits", {})) != {"validation", "test"}:
        raise ValueError("exact validation and test splits required")
    for split in protocol["splits"].values():
        ids = split["token_ids"]
        if (len(ids) != 129 or any(type(x) is not int or x < 0 for x in ids)
                or sha256(canonical(ids)).hexdigest() != split["token_ids_sha256"]):
            raise ValueError("invalid frozen token sequence")


def runtime():
    import numpy
    import torch
    import transformers
    import tokenizers
    import safetensors
    return {"python": sys.version.split()[0], "numpy": numpy.__version__,
            "torch": torch.__version__, "transformers": transformers.__version__,
            "tokenizers": tokenizers.__version__, "safetensors": safetensors.__version__}


def verify_checkpoint(checkpoint_dir, lock_path):
    lock = json.loads(lock_path.read_bytes())
    if lock.get("model_id") != MODEL_ID or lock.get("revision") != REVISION:
        raise ValueError("unexpected checkpoint identity")
    paths = []
    for entry in lock["files"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] != "checkpoint":
            raise ValueError("unsafe checkpoint lock path")
        path = checkpoint_dir.joinpath(*relative.parts[1:])
        if path.is_symlink() or not path.is_file() or path.stat().st_size != entry["bytes"]:
            raise ValueError("checkpoint file type or byte count changed")
        if file_hash(path) != entry["sha256"]:
            raise ValueError("checkpoint hash changed: " + relative.name)
        paths.append(relative.name)
    if len(paths) != 10 or len(set(paths)) != 10:
        raise ValueError("exact ten-file pinned checkpoint required")
    return lock


def prepare(checkpoint_dir, corpus_dir, lock_path, protocol_path):
    """Freeze text and token identities before any model forward pass."""
    lock = verify_checkpoint(checkpoint_dir, lock_path)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(checkpoint_dir), local_files_only=True,
                                              trust_remote_code=False)
    corpus_manifest = corpus_dir / "corpus-manifest.json"
    manifest = json.loads(corpus_manifest.read_bytes())
    splits = {}
    for split in ("validation", "test"):
        path = corpus_dir / (split + ".txt")
        text_bytes = path.read_bytes()
        entry = next(item for item in manifest["sources"] if item["split"] == split)
        if entry["sha256"] != sha256(text_bytes).hexdigest():
            raise ValueError("corpus source manifest does not match text")
        ids = tokenizer.encode(text_bytes.decode("utf-8"), add_special_tokens=False)
        if len(ids) < 129 or any(type(x) is not int or x < 0 for x in ids):
            raise ValueError("each frozen excerpt must contain at least 129 tokens")
        selected = ids[:129]
        splits[split] = {"text_sha256": sha256(text_bytes).hexdigest(),
                         "available_token_count": len(ids), "token_ids": selected,
                         "token_ids_sha256": sha256(canonical(selected)).hexdigest()}
    if splits["validation"]["token_ids_sha256"] == splits["test"]["token_ids_sha256"]:
        raise ValueError("validation and test must be distinct")
    protocol = {
        "schema": "merlin-parallax-lm-protocol/1", "model_id": MODEL_ID,
        "revision": REVISION, "checkpoint_lock_sha256": file_hash(lock_path),
        "checkpoint_files": lock["files"], "source_sha256": source_hashes(),
        "corpus_manifest_sha256": file_hash(corpus_manifest), "splits": splits,
        "tokenizer": {"class": type(tokenizer).__name__, "module": type(tokenizer).__module__,
                      "vocabulary_size": len(tokenizer), "bos_token_id": tokenizer.bos_token_id,
                      "eos_token_id": tokenizer.eos_token_id, "pad_token_id": tokenizer.pad_token_id,
                      "all_special_ids": tokenizer.all_special_ids,
                      "special_tokens_map": tokenizer.special_tokens_map},
        "runtime": runtime(), "cpu_threads": 2, "interop_threads": 1,
        "max_wall_seconds": MAX_SECONDS, "model_dtype": "float32",
        "input_positions": 128, "scored_targets": 128, "total_token_ids": 129,
        "input_rule": "token_ids[:-1]", "target_rule": "token_ids[1:]",
        "add_special_tokens": False, "padding": False, "chat_template": False,
        "use_cache": False, "inference_mode": True, "autocast": False,
        "attention_implementation": "eager", "candidates": [BASELINE, CANDIDATE],
        "candidate_description": "centered covariance with explicit softmax-mass normalization",
        "candidate_admission": {"finite_logits": True, "max_abs_logit_difference": 0.001},
        "selection": "lowest validation mean NLL among eligible; baseline on exact tie",
        "test_episodes": 1, "test_forward_passes_max": 2,
        "loss": "float64 stable logsumexp minus target logit; mean over all 128 targets",
        "perplexity": "exp(mean_nll)", "loss_chunk_positions": 16,
        "interval": None, "interval_reason": "tokens within one text window are correlated",
        "pretraining_exposure": "unknown; split held out only from this candidate selection",
        "hardware_scope": "local CPU reference; no calibrated Parallax chip simulator",
        "model_downloads": False, "model_updates": False, "production_promotion": False,
        "full_logits_retained": True, "max_logit_artifacts": 4,
        "max_logit_artifact_bytes": 128 * 1024 * 1024,
        "logit_storage_scope": "Full-vocabulary output artifacts; separate from the prior attention-input trace budget",
        "budget_scope": "Model load, validation, selection, test and persistence; external timeout also bounds imports and finalization",
        "required_supervisor": "GNU timeout --signal=KILL 300s",
    }
    write_new(protocol_path, canonical(protocol) + b"\n")
    return {"protocol_path": str(protocol_path), "sha256": file_hash(protocol_path),
            "tokens_per_split": 129, "model_forward_passes": 0}


def loss_summary(logits, token_ids):
    import numpy as np
    if logits.dtype != np.float32 or logits.ndim != 2 or logits.shape[0] != 128:
        raise ValueError("expected full FP32 logits for 128 positions")
    if (not np.isfinite(logits).all() or len(token_ids) != 129
            or any(type(x) is not int or x < 0 for x in token_ids)):
        raise ValueError("nonfinite logits or invalid target sequence")
    targets = np.asarray(token_ids[1:], dtype=np.int64)
    if targets.min() < 0 or targets.max() >= logits.shape[1]:
        raise ValueError("target token is outside vocabulary")
    losses = []
    for start in range(0, 128, 16):
        values = logits[start:start + 16].astype(np.float64)
        maximum = values.max(axis=1)
        shifted = values - maximum[:, None]
        # Keep the target shifted too: adding a huge common offset back and
        # subtracting it again can erase log(vocabulary) even in float64.
        log_mass = np.log(np.exp(shifted).sum(axis=1))
        block = log_mass - shifted[np.arange(len(values)), targets[start:start + len(values)]]
        losses.extend(block.tolist())
    mean_nll = math.fsum(losses) / len(losses)
    return {"scored_tokens": len(losses), "sum_nll": math.fsum(losses),
            "mean_nll": mean_nll, "perplexity": math.exp(mean_nll),
            "per_token_losses": losses}


def normalize_loading_info(info):
    """The pinned Transformers API returns empty sets, not JSON arrays."""
    expected = {"missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs"}
    if not isinstance(info, dict) or set(info) != expected:
        raise ValueError("unexpected checkpoint loading diagnostic schema")
    if any(not isinstance(info[key], (set, list, tuple)) or len(info[key]) for key in expected):
        raise ValueError("checkpoint did not load exactly")
    return {key: [] for key in sorted(expected)}


def verify_pre_forward_recovery(protocol, registry, ledger, run_id):
    """One explicitly reviewed metadata repair, retaining the original deadline.

    No scored or ambiguous numerical operation is eligible. The original run
    remains immutable and blocked. A single claim prevents budget multiplication.
    """
    review = protocol.get("reviewed_pre_forward_recovery")
    if review is None:
        return None
    parent = review["parent_run"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", parent) or parent == run_id:
        raise ValueError("invalid recovery parent")
    if file_hash(ledger.path) != review["parent_ledger_file_sha256"]:
        raise ValueError("parent evidence ledger changed before recovery")
    old_loops = restore(ledger, plan_id=parent)
    expected_names = {"initialization", "load", "validation-baseline", "validation-candidate", "selection", "test"}
    if set(old_loops.loops) != expected_names:
        raise ValueError("unexpected recovery parent loop structure")
    for name, loop in old_loops.loops.items():
        expected = ("passed", 1) if name == "initialization" else ("blocked", 1) if name == "load" else ("pending", 0)
        if (loop.state, loop.attempts) != expected:
            raise ValueError("only a reviewed pre-forward load interruption is eligible")
    parent_prefix = "research/parallax-lm/" + parent + "/"

    def parent_json(name):
        ref = registry.artifact_ref("parallax-rsi", parent_prefix + name, version=1)
        if registry.artifact_ref("parallax-rsi", parent_prefix + name) != ref:
            raise ValueError("parent artifact superseded")
        return json.loads(registry.read_artifact_ref(ref, max_bytes=8 * 1024 * 1024)["content"])

    initial = parent_json("initialization.json")
    original = parent_json("protocol.json")
    if (sha256(canonical(initial)).hexdigest() != review["parent_initialization_sha256"]
            or initial["protocol_sha256"] != sha256(canonical(original)).hexdigest()
            or "sha256:" + review["parent_initialization_sha256"] not in old_loops.loops["initialization"].evidence):
        raise ValueError("parent initialization anchor mismatch")
    revised_semantics = {k: v for k, v in protocol.items() if k not in {"source_sha256", "reviewed_pre_forward_recovery"}}
    original_semantics = {k: v for k, v in original.items() if k != "source_sha256"}
    if canonical(revised_semantics) != canonical(original_semantics):
        raise ValueError("recovery changed frozen experiment semantics")
    if protocol["source_sha256"]["python/merlin/parallax_torch_centered.py"] != original["source_sha256"]["python/merlin/parallax_torch_centered.py"]:
        raise ValueError("recovery changed the candidate")
    for name in expected_names - {"initialization"}:
        if registry.artifact_history("parallax-rsi", parent_prefix + name + ".json"):
            raise ValueError("parent has unexpected completed operation evidence")
    deadline = initial["clock"]["started_unix_seconds"] + MAX_SECONDS
    if (deadline != review["original_deadline_unix_seconds"]
            or time.time() < initial["clock"]["last_seen_unix_seconds"] or time.time() >= deadline):
        raise TimeoutError("original episode budget exhausted; recovery cannot renew it")
    claim = parent_prefix + "reviewed-recovery-claim.json"
    if registry.artifact_history("parallax-rsi", claim):
        raise RuntimeError("parent recovery allowance already consumed")
    registry.put_artifact("parallax-rsi", claim, canonical({"child_run": run_id,
        "protocol_sha256": sha256(canonical(protocol)).hexdigest(), "deadline_unix_seconds": deadline}), "application/json")
    return {"started_unix_seconds": initial["clock"]["started_unix_seconds"],
            "deadline_unix_seconds": deadline}


def execute(checkpoint_dir, protocol_path, lock_path, state_dir, output_dir, run_id, source_commit):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", run_id) or not re.fullmatch(r"[a-f0-9]{40}", source_commit):
        raise ValueError("bounded run ID and exact source commit required")
    state_dir.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(state_dir / "parallax-lm.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _execute(checkpoint_dir, protocol_path, lock_path, state_dir, output_dir, run_id, source_commit)
    finally:
        os.close(descriptor)


def _execute(checkpoint_dir, protocol_path, lock_path, state_dir, output_dir, run_id, source_commit):
    protocol = json.loads(protocol_path.read_bytes())
    validate_protocol(protocol)
    if protocol["source_sha256"] != source_hashes() or protocol["checkpoint_lock_sha256"] != file_hash(lock_path):
        raise ValueError("frozen source or checkpoint lock changed")
    window = ResearchWindow(state_dir, project_id="parallax-rsi", project_title="Parallax mathematics and model research")
    registry = window.registry
    ledger = EvidenceLedger(state_dir / "parallax-lm-evidence.jsonl")
    loops = restore(ledger, plan_id=run_id)
    prefix = "research/parallax-lm/" + run_id + "/"
    output_dir.mkdir(parents=True, exist_ok=True)

    def read(name):
        ref = registry.artifact_ref(window.project_id, prefix + name, version=1)
        if registry.artifact_ref(window.project_id, prefix + name)["version"] != 1:
            raise RuntimeError("immutable artifact superseded; review required")
        content = registry.read_artifact_ref(ref, max_bytes=8 * 1024 * 1024)["content"]
        loop = loops.loops.get(name.removesuffix(".json"))
        if loop is not None and loop.state == "passed" and "sha256:" + sha256(content).hexdigest() not in loop.evidence:
            raise RuntimeError("artifact does not match loop evidence")
        return json.loads(content)

    def put(name, record):
        if registry.artifact_history(window.project_id, prefix + name):
            raise RuntimeError("artifact already exists; do not replay partial execution")
        content = canonical(record)
        write_new(output_dir / name, content + b"\n")
        registry.put_artifact(window.project_id, prefix + name, content, "application/json")
        return "sha256:" + sha256(content).hexdigest()

    def finalize(receipt):
        # Verify every retained logit payload without another model invocation.
        rows = [receipt["validation"]["baseline"], receipt["validation"]["candidate"],
                receipt["test"]["baseline"], receipt["test"]["selected"]]
        seen = set()
        for row in rows:
            payload = row.get("logits")
            if payload is None:
                continue
            identity = sha256(canonical(payload)).hexdigest()
            if identity in seen:
                continue
            seen.add(identity)
            name = payload["filename"]
            if (Path(name).name != name or
                    registry.artifact_ref(window.project_id, prefix + name) != payload["artifact_ref"] or
                    payload["artifact_ref"]["version"] != 1 or
                    not registry.verify_artifact(payload["sha256"])):
                raise RuntimeError("frozen logit artifact changed")
            local = output_dir / name
            if (not local.is_file() or local.is_symlink() or local.stat().st_size != payload["bytes"]
                    or file_hash(local) != payload["sha256"]):
                raise RuntimeError("exported logit payload changed or is missing")
        if registry.artifact_history(window.project_id, prefix + "receipt.json"):
            if read("receipt.json") != receipt:
                raise RuntimeError("receipt changed")
        else:
            put("receipt.json", receipt)
        if registry.artifact_history(window.project_id, prefix + "finalization.json"):
            if read("finalization.json")["receipt_sha256"] != sha256(canonical(receipt)).hexdigest():
                raise RuntimeError("finalization digest changed")
        else:
            window.register_artifact(output_dir / "receipt.json", allowed_roots=[output_dir], run_id=run_id,
                logical_path=prefix + "display/receipt.json", title="Pinned Parallax language-model pilot",
                display_kind="data", caption="One held-out natural-text window; CPU reference, no production promotion",
                evidence_class="observed")
            window.emit({"source": "runtime", "kind": "task.completed", "run_id": run_id,
                "event_id": "parallax-lm-complete-" + sha256(canonical(receipt)).hexdigest(),
                "payload": {"summary": "Bounded actual-model evaluation completed", **receipt["selection"]}})
            put("finalization.json", {"receipt_sha256": sha256(canonical(receipt)).hexdigest(), "status": "exported"})
        return receipt

    if loops.loops:
        initial = read("initialization.json")
        if initial["source_commit"] != source_commit or read("protocol.json") != protocol:
            raise RuntimeError("frozen episode identity changed")
        if initial["protocol_sha256"] != sha256(canonical(protocol)).hexdigest():
            raise RuntimeError("protocol anchor changed")
        for name, loop in loops.loops.items():
            if loop.state == "passed":
                read(name + ".json")
        if loops.loops["test"].state == "passed":
            return finalize(read("test.json"))
        raise RuntimeError("incomplete episode requires review; no replay or renewed time budget")

    # All content and environment gates precede the first model forward pass.
    recovery_clock = verify_pre_forward_recovery(protocol, registry, ledger, run_id)
    verified_lock = verify_checkpoint(checkpoint_dir, lock_path)
    if protocol["checkpoint_files"] != verified_lock["files"]:
        raise ValueError("frozen checkpoint manifest changed")
    if protocol["runtime"] != runtime():
        raise ValueError("frozen runtime changed")
    import numpy as np
    import torch
    from transformers import AutoModelForCausalLM
    from merlin.parallax_torch_centered import centered_parallax_forward
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(0)
    protocol_hash = put("protocol.json", protocol).removeprefix("sha256:")
    now = time.time()
    started = recovery_clock["started_unix_seconds"] if recovery_clock else now
    remaining = MAX_SECONDS - (now - started)
    if remaining <= 0:
        raise TimeoutError("original budget exhausted before model load")
    clock = {"started_unix_seconds": started, "consumed_seconds": now - started,
             "last_seen_unix_seconds": now}
    deadline = time.monotonic() + remaining
    loops.add(Loop("initialization", "research"))
    loops.start("initialization")
    evidence = put("initialization.json", {"source_commit": source_commit, "protocol_sha256": protocol_hash,
                                          "clock": dict(clock)})
    loops.finish("initialization", passed=True, evidence=evidence)
    previous = "initialization"
    for name in ("load", "validation-baseline", "validation-candidate", "selection", "test"):
        loops.add(Loop(name, "research", dependencies=(previous,)))
        previous = name
    checkpoint(loops, ledger, plan_id=run_id)
    window.emit({"source": "runtime", "kind": "task.started", "run_id": run_id,
        "payload": {"summary": "Frozen offline Parallax-0.6B model pilot", "question": "Does the centered mass-normalized candidate preserve logits and improve this validation NLL?"}})

    def operation(name, callback):
        if time.monotonic() >= deadline:
            loops.block(name, "persisted cycle wall budget exhausted")
            checkpoint(loops, ledger, plan_id=run_id)
            raise TimeoutError("300-second model episode exhausted")
        loops.start(name)
        checkpoint(loops, ledger, plan_id=run_id)
        window.emit({"source": "runtime", "kind": "task.started", "run_id": run_id,
                     "payload": {"summary": name}})
        result = callback()
        if time.monotonic() >= deadline or time.time() < clock["last_seen_unix_seconds"]:
            raise TimeoutError("time boundary crossed; interrupted episode requires review")
        clock["last_seen_unix_seconds"] = time.time()
        clock["consumed_seconds"] = MAX_SECONDS - (deadline - time.monotonic())
        result["budget_checkpoint"] = dict(clock)
        evidence = put(name + ".json", result)
        loops.finish(name, passed=True, evidence=evidence)
        checkpoint(loops, ledger, plan_id=run_id)
        window.emit({"source": "runtime", "kind": "experiment.completed", "run_id": run_id,
                     "payload": {"summary": name + " completed", "mean_nll": result.get("mean_nll")},
                     "evidence_refs": [evidence]})
        print(json.dumps({"completed": name, "seconds": clock["consumed_seconds"]}), flush=True)
        return result

    context = {}

    def load_model():
        model, info = AutoModelForCausalLM.from_pretrained(str(checkpoint_dir), local_files_only=True,
            trust_remote_code=True, dtype=torch.float32, attn_implementation="eager", output_loading_info=True)
        info = normalize_loading_info(info)
        model.eval().requires_grad_(False)
        if any(p.device.type != "cpu" or p.dtype != torch.float32 for p in model.parameters()):
            raise ValueError("all model parameters must be CPU FP32")
        author = importlib.import_module(type(model).__module__)
        if file_hash(Path(author.__file__)) != next(e["sha256"] for e in protocol["checkpoint_files"] if e["path"] == "checkpoint/modeling_parallax.py"):
            raise ValueError("executed modeling source differs from inspected pin")
        config_source = importlib.import_module(type(model.config).__module__)
        if file_hash(Path(config_source.__file__)) != next(e["sha256"] for e in protocol["checkpoint_files"] if e["path"] == "checkpoint/configuration_parallax.py"):
            raise ValueError("executed configuration source differs from inspected pin")
        if model.config.attn_type != "parallax" or model.config.num_hidden_layers != 28:
            raise ValueError("unexpected model architecture")
        context.update(model=model, author=author, original=author.parallax_forward)
        return {"parameter_count": sum(p.numel() for p in model.parameters()), "loading_info": info,
                "dtype": "float32", "device": "cpu", "layers": model.config.num_hidden_layers,
                "vocab_size": model.config.vocab_size, "training": model.training,
                "threads": torch.get_num_threads(), "interop_threads": torch.get_num_interop_threads()}

    loaded = operation("load", load_model)

    def score(split, variant):
        if time.monotonic() >= deadline:
            raise TimeoutError("no forward pass may start after the frozen deadline")
        ids = protocol["splits"][split]["token_ids"]
        if sha256(canonical(ids)).hexdigest() != protocol["splits"][split]["token_ids_sha256"]:
            raise ValueError("frozen tokens changed")
        inputs = torch.tensor([ids[:-1]], dtype=torch.long)
        author = context["author"]
        kernel = context["original"] if variant == BASELINE else centered_parallax_forward
        calls = []

        def observed_kernel(module, query, r, key, value, attention_mask, scaling, dropout=0.0, **kwargs):
            calls.append({"layer": module.layer_idx, "query_shape": list(query.shape),
                          "key_shape": list(key.shape), "dtype": str(query.dtype),
                          "mask_shape": None if attention_mask is None else list(attention_mask.shape),
                          "mask_sha256": None if attention_mask is None else
                              sha256(attention_mask.contiguous().numpy().tobytes()).hexdigest()})
            if len(calls) > loaded["layers"]:
                raise ValueError("unexpected repeated attention invocation")
            return kernel(module, query, r, key, value, attention_mask, scaling, dropout, **kwargs)

        author.parallax_forward = observed_kernel
        start = time.monotonic()
        try:
            if start >= deadline:
                raise TimeoutError("no forward pass may start after the frozen deadline")
            with torch.inference_mode(), torch.autocast("cpu", enabled=False):
                outputs = context["model"](input_ids=inputs, attention_mask=torch.ones_like(inputs),
                                           use_cache=False, return_dict=True)
                if outputs.past_key_values is not None:
                    raise ValueError("KV cache unexpectedly returned")
                logits = outputs.logits[0].contiguous().numpy()
        finally:
            author.parallax_forward = context["original"]
        forward_seconds = time.monotonic() - start
        if [call["layer"] for call in calls] != list(range(loaded["layers"])):
            raise ValueError("installed kernel did not run once through every model layer")
        if logits.shape != (128, loaded["vocab_size"]) or logits.dtype != np.float32:
            raise ValueError("unexpected full-logit shape or dtype")
        if logits.nbytes + 128 > 128 * 1024 * 1024:
            raise ValueError("full-logit artifact exceeds the frozen output budget")
        summary = loss_summary(logits, ids)
        name = split + "-" + variant + "-logits.npy"
        path = output_dir / name
        with path.open("xb") as handle:
            np.save(handle, logits, allow_pickle=False)
            handle.flush()
            os.fsync(handle.fileno())
        if registry.artifact_history(window.project_id, prefix + name):
            raise RuntimeError("logit artifact already exists")
        digest = registry.put_artifact(window.project_id, prefix + name, path.read_bytes(), "application/octet-stream")
        return {"candidate": variant, "split": split, **summary, "forward_seconds": forward_seconds,
                "attention_invocations": calls,
                "finite_logits": True, "logits": {"filename": name, "shape": list(logits.shape),
                "dtype": "float32", "bytes": path.stat().st_size, "sha256": digest,
                "artifact_ref": registry.artifact_ref(window.project_id, prefix + name)}}

    def drift(left, right):
        if left["attention_invocations"] != right["attention_invocations"]:
            raise ValueError("baseline and candidate attention mask or shape traces differ")
        a = np.load(output_dir / left["logits"]["filename"], mmap_mode="r", allow_pickle=False)
        b = np.load(output_dir / right["logits"]["filename"], mmap_mode="r", allow_pickle=False)
        maximum = max(float(np.abs(a[i:i+16].astype(np.float64) - b[i:i+16].astype(np.float64)).max())
                      for i in range(0, 128, 16))
        return {"max_abs_logit_difference": maximum, "logit_gate_passed": maximum <= 0.001}

    baseline = operation("validation-baseline", lambda: score("validation", BASELINE))

    def validation_candidate():
        try:
            candidate = score("validation", CANDIDATE)
            candidate.update(drift(baseline, candidate))
            return candidate
        except (ValueError, FloatingPointError, OverflowError) as error:
            return {"candidate": CANDIDATE, "split": "validation", "logit_gate_passed": False,
                    "rejected_reason": str(error)}

    candidate = operation("validation-candidate", validation_candidate)

    def select():
        chosen = CANDIDATE if candidate["logit_gate_passed"] and candidate["mean_nll"] < baseline["mean_nll"] else BASELINE
        return {"selected_candidate": chosen, "selected_on": "validation mean NLL only",
                "baseline_on_exact_tie": True, "test_forward_passes_before_selection": 0,
                "production_promotion": False}

    selection = operation("selection", select)

    def test_once():
        base_test = score("test", BASELINE)
        selected_test = base_test if selection["selected_candidate"] == BASELINE else score("test", CANDIDATE)
        test_drift = drift(base_test, selected_test)
        differences = [b - a for a, b in zip(base_test["per_token_losses"], selected_test["per_token_losses"])]
        return {"schema": "merlin-parallax-lm-receipt/1", "run_id": run_id,
                "source_commit": source_commit, "protocol_sha256": protocol_hash, "runtime": protocol["runtime"],
                "model": loaded, "validation": {"baseline": baseline, "candidate": candidate},
                "selection": selection, "test": {"episode_count": 1,
                    "forward_passes": 1 if selection["selected_candidate"] == BASELINE else 2,
                    "baseline": base_test, "selected": selected_test, **test_drift,
                    "paired_mean_nll_delta_selected_minus_baseline": math.fsum(differences) / len(differences),
                    "per_token_loss_differences": differences, "confidence_interval": None,
                    "scope": "single 128-target text window; correlated tokens; pretraining exposure unknown"},
                "trained_language_model_evaluated": True, "physical_hardware_validated": False,
                "production_promotion": False, "model_weights_changed": False,
                "result_scope": "bounded CPU numerical diagnostic; no general quality claim"}

    receipt = operation("test", test_once)
    return finalize(receipt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "execute"])
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--checkpoint-lock", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.checkpoint_dir, args.corpus_dir, args.checkpoint_lock, args.protocol)
    else:
        result = execute(args.checkpoint_dir, args.protocol, args.checkpoint_lock, args.state_dir,
                         args.output_dir, args.run_id, args.source_commit)
        result = {"run_id": result["run_id"], "selected_candidate": result["selection"]["selected_candidate"],
                  "test_baseline_perplexity": result["test"]["baseline"]["perplexity"],
                  "test_selected_perplexity": result["test"]["selected"]["perplexity"]}
    print(json.dumps(result, indent=2), flush=True)
