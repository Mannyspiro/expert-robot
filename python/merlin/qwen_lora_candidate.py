"""Opt-in local-only Qwen2.5-Coder-1.5B QLoRA candidate training.

This trains adapter weights only; source Qwen checkpoint is frozen and a GGUF
inference file is NOT trainable input. No network, hosted APIs, private chats,
model publication, automatic replacement or production promotion. Evaluation
requires improvement with zero previously-correct heldout regressions.

Dependencies only when --execute: torch + transformers + peft + accelerate +
bitsandbytes, supported CUDA GPU. The operator must independently provision
and verify the full local HF/safetensors checkpoint, its license and rights.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

MAX_ROWS = 64
EXPECTED_TYPE = "qwen2"
EXPECTED_SOURCE = "Qwen/Qwen2.5-Coder-1.5B-Instruct"


def _absolute_dir(path, *, must_exist=True):
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError("absolute local directory required")
    if path.is_symlink():
        raise ValueError("symlink model/output paths are not permitted")
    if must_exist and not path.is_dir():
        raise ValueError("local directory must exist")
    return path


def _digest(path):
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _examples(path):
    if not isinstance(path, Path) or not path.is_file() or path.is_symlink():
        raise ValueError("existing local JSON examples file required")
    if path.stat().st_size > 65536:
        raise ValueError("example set exceeds byte budget")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if type(rows) is not list or not 2 <= len(rows) <= MAX_ROWS:
        raise ValueError("expected 2..64 examples")
    keys = set()
    for row in rows:
        if type(row) is not dict or set(row) != {"id", "question", "answer"}:
            raise ValueError("exact example fields required")
        if not isinstance(row["id"], str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{2,60}", row["id"]):
            raise ValueError("bounded example identity required")
        if row["id"] in keys:
            raise ValueError("duplicate example id")
        keys.add(row["id"])
        for key, cap in (("question", 512), ("answer", 128)):
            value = row[key]
            if not isinstance(value, str) or not 0 < len(value) <= cap:
                raise ValueError("bounded example text required")
            if any(ord(c) < 32 and c not in "\n\t" for c in value):
                raise ValueError("control character in example")
    return rows


def _sample_key(row):
    return hashlib.sha256(row["question"].strip().casefold().encode()).hexdigest()


def preflight(model_dir: Path, train_file: Path, holdout_file: Path,
              output_parent: Path):
    """Inspect only: no model loading, training, downloads or side effects."""
    _absolute_dir(model_dir)
    _absolute_dir(output_parent)
    if model_dir.resolve() == output_parent.resolve():
        raise ValueError("output must not overwrite the source checkpoint")
    conf = model_dir / "config.json"
    if not conf.is_file() or conf.is_symlink() or conf.stat().st_size > 65536:
        raise ValueError("local trainable config.json missing")
    config = json.loads(conf.read_text(encoding="utf-8"))
    if config.get("model_type") != EXPECTED_TYPE:
        raise ValueError("only Qwen2 trainable HF architecture admitted")
    if not (model_dir / "tokenizer.json").is_file():
        raise ValueError("local tokenizer.json missing")
    checkpoint = sorted(model_dir.glob("*.safetensors"))
    if not checkpoint or any(p.is_symlink() or not p.is_file() for p in checkpoint):
        raise ValueError("local safetensors checkpoint missing")
    if any(p.suffix == ".gguf" for p in model_dir.iterdir()):
        raise ValueError("GGUF inference file is not a trainable base checkpoint")
    training = _examples(train_file)
    holdout = _examples(holdout_file)
    if {r["id"] for r in training} & {r["id"] for r in holdout}:
        raise ValueError("train and holdout identifiers overlap")
    if {_sample_key(r) for r in training} & {_sample_key(r) for r in holdout}:
        raise ValueError("train questions leak into heldout questions")
    return {"schema": "merlin-qwen-lora-candidate-preflight/1",
            "model_architecture": EXPECTED_TYPE,
            "source_identity_requested": EXPECTED_SOURCE,
            "config_sha256": _digest(conf),
            "training_sha256": _digest(train_file),
            "holdout_sha256": _digest(holdout_file),
            "weight_files": len(checkpoint),
            "train_cases": len(training),
            "heldout_cases": len(holdout),
            "candidate_weights_trained": False,
            "checkpoint_verified_by_operator": False,
            "promotion_authority": False}


def _generation(model, tokenizer, question, torch):
    ids = tokenizer.apply_chat_template(
        [{"role": "user", "content": question}],
        tokenize=True, add_generation_prompt=True, return_tensors="pt")
    ids = ids.to("cuda:0")
    with torch.inference_mode():
        out = model.generate(input_ids=ids, max_new_tokens=32,
                             do_sample=False, pad_token_id=tokenizer.eos_token_id)
    return tokenizer.decode(out[0, ids.shape[-1]:], skip_special_tokens=True).strip()


def _score(model, tokenizer, rows, torch):
    model.eval()
    correct = []
    hashes = []
    for row in rows:
        answer = _generation(model, tokenizer, row["question"], torch)
        correct.append(answer.casefold().strip() == row["answer"].casefold().strip())
        hashes.append(hashlib.sha256(answer.encode()).hexdigest())
    return correct, hashes


def execute(model_dir, train_file, holdout_file, output_parent, *,
            steps=12, rank=4):
    if type(steps) is not int or not 1 <= steps <= 30:
        raise ValueError("training step count must be 1..30")
    if rank not in (2, 4, 8) or type(rank) is not int:
        raise ValueError("only bounded LoRA ranks 2,4,8 supported")
    report = preflight(model_dir, train_file, holdout_file, output_parent)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required; CPU Qwen training is not admitted")
    free_bytes, _ = torch.cuda.mem_get_info()
    if free_bytes < 8 * 1024**3:
        raise RuntimeError("requires at least 8GiB free CUDA memory")
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    torch.manual_seed(20261122)
    train_rows = _examples(train_file)
    holdout_rows = _examples(holdout_file)
    precision = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    tokenizer = AutoTokenizer.from_pretrained(
        str(model_dir), local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        str(model_dir), local_files_only=True, trust_remote_code=False,
        device_map={"": 0}, torch_dtype=precision,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=precision))
    model.config.use_cache = True
    before_correct, before_hashes = _score(model, tokenizer, holdout_rows, torch)
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(
        r=rank, lora_alpha=rank*2, lora_dropout=0.0,
        target_modules=["q_proj", "v_proj"],
        bias="none", task_type="CAUSAL_LM"))
    model.config.use_cache = False
    optimizer = torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad),
        lr=3e-4, weight_decay=0.0)
    losses = []
    model.train()
    for step in range(steps):
        row = train_rows[step % len(train_rows)]
        prompt = [{"role": "user", "content": row["question"]}]
        combined = prompt + [{"role": "assistant", "content": row["answer"]}]
        prefix = tokenizer.apply_chat_template(
            prompt, tokenize=True, add_generation_prompt=True)
        full = tokenizer.apply_chat_template(
            combined, tokenize=True, add_generation_prompt=False)
        if (len(full) > 1024 or len(prefix) >= len(full)
                or full[:len(prefix)] != prefix):
            raise ValueError("training chat template prefix differs or too long")
        tokens = torch.tensor([full], device="cuda:0")
        labels = tokens.clone()
        labels[:, :len(prefix)] = -100
        output = model(input_ids=tokens, labels=labels)
        loss = output.loss
        if not bool(torch.isfinite(loss)):
            raise RuntimeError("nonfinite training loss")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            (p for p in model.parameters() if p.requires_grad), 1.0)
        optimizer.step()
        losses.append(round(float(loss.detach().cpu()), 6))
    model.config.use_cache = True
    after_correct, after_hashes = _score(model, tokenizer, holdout_rows, torch)
    gains = sum(not a and b for a, b in zip(before_correct, after_correct))
    regressions = sum(a and not b for a, b in zip(before_correct, after_correct))
    passed = gains > 0 and regressions == 0
    receipt = {**report,
               "schema":"merlin-qwen-lora-candidate/1",
               "training_steps":steps, "rank":rank,
               "losses":losses,
               "baseline_correct":sum(before_correct),
               "candidate_correct":sum(after_correct),
               "improved_cases":gains, "regressed_cases":regressions,
               "baseline_answer_sha256":before_hashes,
               "candidate_answer_sha256":after_hashes,
               "candidate_weights_trained": True,
               "candidate_accepted_for_research": passed,
               "candidate_auto_promoted":False,
               "production_qualified":False}
    # Save a unique adapter candidate only if the exact heldout gate passes.
    if passed:
        saved = Path(tempfile.mkdtemp(prefix="merlin-qwen-lora-candidate-",
                                     dir=str(output_parent)))
        model.save_pretrained(str(saved), safe_serialization=True)
        (saved / "evaluation-receipt.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        receipt["local_adapter_path"] = str(saved)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--train-json", required=True)
    parser.add_argument("--heldout-json", required=True)
    parser.add_argument("--output-parent", required=True)
    parser.add_argument("--execute", action="store_true",
                        help="explicitly perform bounded CUDA adapter training")
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--rank", type=int, default=4)
    args = parser.parse_args(argv)
    params = (Path(args.model_dir), Path(args.train_json),
              Path(args.heldout_json), Path(args.output_parent))
    report = execute(*params, steps=args.steps, rank=args.rank) if args.execute \
        else preflight(*params)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
