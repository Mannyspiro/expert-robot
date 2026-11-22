"""A real, bounded Torch LoRA weight-training proof on a tiny synthetic model.

This DOES NOT modify the production Merlin Qwen GGUF. A frozen base matrix
plus trainable rank-one adapter demonstrates optimizer updates and a heldout
improvement; the result is neither language-model training nor release proof.
Optional dependency: PyTorch CPU. No internet/model downloads or GPU needed.
"""
from __future__ import annotations
import json


def run_demo(*, steps: int = 160):
    import torch
    if type(steps) is not int or not 1 <= steps <= 300:
        raise ValueError("steps must be 1..300")
    torch.set_num_threads(1)
    torch.manual_seed(20261122)
    base = torch.nn.Linear(2, 1, bias=False)
    with torch.no_grad():
        base.weight.zero_()
    base.weight.requires_grad_(False)

    # W_eff = W_frozen + B@A, rank=1; only A and B are optimizer targets.
    A = torch.nn.Parameter(torch.tensor([[1., 1.]], dtype=torch.float32))
    B = torch.nn.Parameter(torch.zeros((1, 1), dtype=torch.float32))
    before_A, before_B = A.detach().clone(), B.detach().clone()
    training_x = torch.tensor([[1.,0.],[0.,1.],[-1.,0.],[0.,-1.]])
    training_y = torch.tensor([[1.],[1.],[-1.],[-1.]])
    holdout_x = torch.tensor([[.5,.5],[2.,1.],[-.5,.25],[-1.,-.75]])
    holdout_y = torch.tensor([[1.],[3.],[-.25],[-1.75]])

    def eval_holdout():
        with torch.no_grad():
            pred = base(holdout_x) + (holdout_x @ A.T) @ B.T
            errors = (pred - holdout_y).abs().flatten()
            return {"correct": int((errors < .05).sum().item()),
                    "mae": float(errors.mean().item())}

    baseline = eval_holdout()
    optimizer = torch.optim.SGD((A, B), lr=.08)
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        output = base(training_x) + (training_x @ A.T) @ B.T
        loss = (output - training_y).square().mean()
        loss.backward()
        optimizer.step()
        if not bool(torch.isfinite(A).all() and torch.isfinite(B).all()):
            raise RuntimeError("nonfinite LoRA parameters")
    candidate = eval_holdout()
    changed = not bool(torch.equal(before_A, A) and torch.equal(before_B, B))
    if (not changed or candidate["correct"] <= baseline["correct"]
            or candidate["mae"] >= baseline["mae"]
            or not torch.equal(base.weight.detach(), torch.zeros_like(base.weight))):
        raise RuntimeError("trained adapter did not pass its isolated holdout gate")

    return {"schema":"merlin-tiny-torch-lora-proof/1",
            "torch_version":torch.__version__,
            "base_model":"synthetic-linear-2-input-1-output",
            "steps":steps,"adapter_rank":1,
            "train_examples":4,"heldout_examples":4,
            "baseline":baseline,"candidate":candidate,
            "adapter_parameters_changed":True,
            "base_model_parameters_unchanged":True,
            "weights_gradient_trained":True,
            "merlin_qwen_parameters_changed":False,
            "candidate_auto_promoted":False,
            "independent_model_qualification":False}


if __name__=="__main__":
    print(json.dumps(run_demo(),sort_keys=True))
