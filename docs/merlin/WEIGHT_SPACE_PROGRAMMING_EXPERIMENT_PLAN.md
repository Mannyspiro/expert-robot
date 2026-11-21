# Weight-space programming experiment plan for Merlin

Date: November 21, 2026 (America/Phoenix).

Status: research proposal. No target model has been selected, no weights have been edited, and no model-quality improvement has been measured. This document does not enable execution or change production behavior.

## Decision

Add weight-space programming (WSP) to Merlin's research roadmap as an optional way to construct a small specialist network or propose a bounded patch to an accessible model. Start with one component, an ordinary-code baseline, and a fixed independent oracle. Preserve the existing worker, canonical artifact, recovery, and acceptance mechanisms.

Here WSP means a general-purpose LLM directly constructs or edits neural parameters, possibly through generated numerical code, without gradient-based optimization of those parameters. It is distinct from training LoRA updates or combining existing fine-tuned models. The initial research reports are recent and do not measure Merlin.

## Evidence and limits

The original report includes a targeted correction to a small model with a severe repetitive-generation defect and a negative result on another model. WeightBench reports a mixed capability profile with limited samples and access-dependent reference solutions. iWSP demonstrates bounded algorithmic constructions and interpretable features, while its broader-language results are weaker. These observations support an experiment, not a production-benefit claim. Primary sources are listed below.

A weight edit can improve an average metric while breaking a specific required behavior. Consequently, the candidate cannot choose its evaluator, redefine success, or modify operational acceptance rules.

## First experiment and falsifiers

Preferred initial production hypothesis: for one already measurable candidate-selection task, a small WSP scorer reduces expensive checker calls or end-to-end cost while preserving independently verified completion. The scorer only orders already eligible candidates. The existing checker establishes validity.

A second, conditional hypothesis is targeted repair of an accessible proposal/coding model with a reproducible looping or termination defect. Do not begin that experiment merely because another model benefited in a published example.

Before either experiment, require the actual task distribution, reference oracle, available baseline implementation, editable target or declared new-network architecture, runtime, and bounded resource budget. Missing prerequisites keep execution disabled.

Compare the following under matched information and execution budgets:

1. Existing Merlin behavior on the selected task.
2. The strongest practical ordinary program or explicit heuristic, including an LLM-written program.
3. A WSP candidate with no behavioral feedback during construction.
4. A separately labeled WSP candidate with a fixed maximum number of development evaluations.

Use the unchanged network and irrelevant or randomized edits as diagnostic controls. They are not substitutes for a strong competitive baseline.

Falsifiers include no improvement over ordinary code, improved visible scores that disappear on held-out tasks, greater cost per verified success, lower retention on unrelated tasks, or numerical behavior that fails at the intended deployment precision. Failure to find an edit means this bounded search failed; it does not prove the task is mathematically impossible.

## Predeclared evaluation

Freeze task, development and final-evaluation inventories before candidate selection. Separate cases semantically as well as by identifier. The weight programmer can see development feedback within its budget; final holdout results cannot be fed back into that same selection cycle.

Record every candidate, invalid artifact, failed attempt, evaluation, and exhausted budget. Report paired task results and uncertainty at the independent task level. Repeated samples from one task do not create independent task coverage.

Primary outcomes:

- Independently verified task completion.
- Expensive checker calls and total cost per verified completion.
- End-to-end latency, including failed attempts.
- Repetitive-output/timeout rate where that is the declared defect.

Retention outcomes:

- Unrelated capability and interface/schema validity.
- Behavior on shifted ranges, unfamiliar labels and task variants.
- Numerical stability at the intended dtype and quantization.
- Exact application requirements independent of average score.
- Repeatability and appropriate abstention.

Choose the minimum useful improvement, allowable quality margin, sample size, candidate limit, forward-pass budget and cost ceiling after baseline characterization and before editing. No operational run is authorized with these values unset.

For a weight-reading claim, where applicable, use independently verified function-preserving neuron permutations or relabelings to test reliance on familiar parameter positions. For a zero-forward-pass claim, the execution host must meter access; a prompt restriction alone is insufficient.

Construction and evaluation costs count toward the outcome. Gradient-free does not mean data-free, feedback-free, or cost-free. Compare lifecycle cost over a stated deployment volume before claiming savings.

## Integration with the current source

Use the existing MerlinRegistry and ArtifactRef for candidate and evidence lineage. Do not create another receipt store.

DualCoderWorkflow in python/dot_ai_os/dual_coder.py provides host-injected coder and evaluator callbacks. Initially change one proposal/coder role while holding the other coder and evaluator configuration fixed. The current identity declarations do not themselves authenticate providers or prove reviewer independence.

A host-owned configuration should bind a separate weight-candidate manifest containing:

- Exact base checkpoint, architecture and tensor layout.
- Tokenizer, model configuration and inference settings.
- Original and resulting weight/shard hashes, sizes and dtypes.
- Transformation program identity and any small delta artifact.
- Development inputs, numerical settings, prompt and programmer identity.
- Intended role, runtime requirements and baseline rollback reference.
- Evaluation protocol, evaluator identity and all attempt receipts.

The loader must verify the actual bytes it loads. A manifest hash alone is not a loaded-model receipt. Keep large weight bundles outside bounded review packets; packets carry references and bounded evidence.

The existing adapter_sha256 identifies integration code. It must not be silently repurposed as the weight-delta identity. Any new manifest/loader contract is a future implementation task, not implemented by this document.

Current constraints remain explicit: the selected source shard has no verified editable-weight runtime or model-loader integration; the fixed synthetic process runner has not established transformer/GPU inference; DualCoderWorkflow admits only a zero-cost specification and does not enforce external billing. Paid model operations need an explicitly configured budget policy and host enforcement, rather than being labeled zero-cost.

## Two acceptance decisions

Operational acceptance concerns exact code, runtime, software inventory, kernel cases, cancellation, recovery and current authority. The existing BuildGoal contract belongs here.

Model efficacy concerns whether this exact weight candidate improves the selected task against the frozen baselines. It needs its own typed evaluation receipt and review decision in the same canonical registry. The 386 local software-test passes are not observations of WSP model quality.

Approval, leases, replay decisions, artifact integrity, process limits, verification and release authority remain deterministic host mechanisms. A model may propose candidates; its scores cannot grant those rights.

Retain the immutable baseline and never edit the shared production checkpoint in place. A candidate may enter shadow evaluation only after its bytes and runtime are verified. Production selection still requires the existing release decision. Failed and null results remain in the record after rollback.

## Representation checks

The existing four-lens framework is used as a design aid, not evidence that a model improved:

- Simplex: not applicable to a direct edit unless the protocol explicitly introduces a convex mixture.
- n-ality: keep model, transformation, tokenizer, task, evaluator, runtime and authority identities distinct.
- Continuum: nearby weights can have discontinuous measured behavior; test the behavior instead of inferring it from edit size.
- Fuzzy logic: useful only for exploratory ranking; exact validity and operational authority remain Boolean checks.

## Next implementation boundary

Provision one permitted target/runtime and measure its baseline. Then implement and test the host-owned candidate loader/manifest binding using the existing registry and callback interfaces. Freeze the comparison before any model editing. If no representative task and oracle are available, a synthetic demonstration can validate plumbing but cannot establish production benefit.

The current process-recovery candidate remains source commit 4847d90dca4266d42651a8b9538c3eeae8a423b1, with a 117-file selected shard and 386 passing local software tests. Its new native validation is still NOT_RUN because the separate-repository code transfer requires explicit authorization. WSP does not satisfy that pending gate.

## Primary sources

Accessed November 21, 2026. Published results have not been independently reproduced in this Merlin work.

1. Takehi, Teoh, Zhang and Khattab, [Sparks of Weight-Space Programming](https://rikiyat.github.io/blog/weight-space-programming/), November 2, 2026; author report and linked logs.
2. Marasini, Khadka and Rahimi, [WeightBench](https://arxiv.org/html/2611.18553v1), November 13, 2026; preprint.
3. Ahmed, [Can an LLM Actually Reason and Program about Neural Network's Weights](https://arxiv.org/html/2611.08070v1), November 5, 2026; exploratory weight-reading audit.
4. Mehta et al., [Interpretable weight-space programming](https://arxiv.org/html/2611.18114v1), November 13, 2026; preprint.
5. Gross, [Weight-Space Programming of Policies and Their Verification via Model Checking](https://arxiv.org/html/2611.11604v1), November 8, 2026; preprint over modeled finite environments.
6. Ok and Lee, [Weight-Space Programming Doesn't Need Transformers](https://arxiv.org/html/2611.22055v1), November 17, 2026; preprint.
7. Hu et al., [LoRA](https://arxiv.org/abs/2106.09685), 2021; distinct parameter-efficient training method.
