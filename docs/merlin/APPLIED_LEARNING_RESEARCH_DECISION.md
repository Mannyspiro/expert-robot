# Applied learning research: next Merlin change

Date: November 21, 2026, America/Phoenix.

Status: research decision against source `4b1d5e75916570e0a2d37cc2371b3dc27339ad9a` (PR187). The production repair has a separate software/native acceptance record. This note records a concrete next implementation target; it does not claim that a model-learning experiment, new evaluator adapter, training run or weight-space improvement has occurred.

## Decision and code target

Prioritize an **original-task verifier adapter for bounded problem-reframing trials**. Measure whether changing the representation helps Merlin solve the original problem under an equal compute budget. Reuse the existing research workflow and canonical registry.

The inspected source already has two relevant boundaries:

- `python/merlin/scientific_loop.py::decompose_by_analogy` records the original problem, invariant mapping and translation-back requirements. Its explicit epistemic status is `problem_reframing_not_evidence`; creating the record does not provide or execute those tests or verify semantic equivalence.
- `python/dot_ai_os/dual_coder.py::DualCoderWorkflow` separates coder inputs from held-out case identifiers and has a host-supplied evaluator callback. Its report explicitly identifies selection as `declared_evaluator_case_counts_only`. The next adapter should derive those counts from retained per-case checker observations.

The host must pin the task/case manifest, original constraints, checker implementation and experiment budget. A reframe may propose a different representation; it cannot replace the original objective or choose its own correctness criterion. Automatic checking applies only to declared task domains with machine-checkable constraints. Uncheckable semantic-equivalence questions remain unresolved and cannot receive an inferred pass. A successful record must retain the original-task check after translation back. Existing `ArtifactRef`, registry, replay and optional invocation weight binding remain the integration points.

This is the first applied R&D target because it supplies evidence needed by later learning changes. A second orchestration framework or a course about AI is outside this decision.

## Research findings that change the implementation choice

The selected primary sources support mechanisms and expose limitations. They are not a comprehensive survey of all research available in 2026, and their results have not been reproduced on Merlin.

| Finding | Consequence for the next change |
|---|---|
| T5 compares explicit predictive pretraining objectives and downstream transfer [1]. | A later non-RL candidate can use a declared predictive or supervised loss. It still needs data, an objective and actual optimization. |
| Intelligent Adaptive Curiosity selects learnable regions using learning progress and explicitly uses internal reward [2]. | Study progress-based experiment selection as a separate mechanism. Calling it curiosity does not make it reward-free or establish subjective wants. |
| MAML trains parameters to adapt through a few gradient steps [3]. | Defer meta-learning until an editable model and a representative family of related tasks exist. A software wrapper is not a demonstration of rapid learning. |
| BabyAI reports substantial sample-efficiency limitations in its synthetic grounded-language tasks [4]. | Child-development analogies motivate hypotheses; they do not establish that Merlin will learn with human-like efficiency. |
| In the studied reasoning tasks, intrinsic self-correction without external correctness feedback sometimes reduced performance [5]. | Use an external original-task checker and an equal-budget direct baseline. More reflection or a more persuasive explanation is not the outcome metric. |
| Constitutional AI has distinct supervised-revision and reinforcement-learning phases [6]. | Principle-guided supervised updates are a possible later component. The complete published method cannot be described as reward-free. Measure helpfulness and behavioral tradeoffs. |
| Constructed backdoored models retained conditional behavior through several training methods [7]. | Evaluate context shifts and conflicting objectives. Agreeable wording alone is insufficient. This study does not show that Merlin has deceptive motives. |
| The consciousness report derives indicators from scientific theories [8]. | Consciousness remains a legitimate research subject with uncertainty. Topic selection, self-report and prediction-error statistics do not establish subjective wants or experience. |

## Experiment contract

The first real experiment compares an unchanged direct-solving baseline, an ordinary explicit reframing heuristic and one model-proposed reframe. Match total model calls/tokens and count checker calls, failures and elapsed time. Separate development, selection-validation and untouched final-assessment problem families. The current workflow chooses a recommendation using `holdout_passed`; its existing `holdout_ids` therefore serve as selection-validation cases, despite the field name. The proposed experiment needs a separate final-assessment manifest outside that selection step. Final-assessment results cannot guide the same candidate-selection cycle or be relabelled as another independent final test after feedback.

The primary outcome is independently checked completion of the original task. Report paired task outcomes, uncertainty, total cost per verified completion and retention on unrelated tasks. Freeze the task distribution, minimum useful gain, retention margin, sample size and compute ceiling after baseline characterization and before candidate selection. These numeric parameters are currently unset; no model experiment is enabled by this document.

Reject the mechanism if it only improves visible development cases, loses required constraints, gains disappear against equal-budget controls, or retention/care behavior worsens. Preserve invalid mappings, failures and null results. A failed bounded experiment does not establish universal impossibility.

The adapter's engineering acceptance should reject altered case membership, changed objectives, missing constraints, mismatched checker identities and contradictory per-case/count records, while preserving normal replay without repeating providers. Fixtures can establish those software properties. A genuine model, representative tasks and an independently configured checker are needed to establish improved reasoning.

## Non-RL learning and care-oriented behavior

After the verifier and actual runtime are available, test one separately versioned self-supervised or supervised update against the unchanged checkpoint. One candidate is training on externally verified successful solutions using a declared predictive loss. Keep the original checkpoint, exact loaded-weight observations, tokenizer/runtime identities, approved data, held-out retention and cost bounds. Weight-space programming remains a separate candidate-generation mechanism under its existing experiment plan.

The care-oriented research direction should become observable requirements: proportionate protection, consent, privacy, honest uncertainty, correction acceptance, support for independence and avoidance of unnecessary harm to people, animals and environments. Include cases where comforting language conflicts with a useful action, or where interests conflict. These are proposed behavioral tests and design values, not evidence of a biological maternal instinct. Care criteria do not grant the model additional operational authority.

## Bounded alternative search and representation checks

The concrete gap is unverified translation from a reframe to the original task. A manual design comparison considered three mechanisms (reframing, weight updates, progress-based problem selection) with two evidence regimes (self-report, external task checks): six combinations, all examined by reasoning, with no automated search or model experiment. Three self-report-only combinations were rejected as insufficient evidence. Externally checked weight updates and progress-based selection were deferred until their runtime/data prerequisites exist. Externally checked reframing was selected as the next implementation target. One returned, two deferred, three rejected, zero unexamined within this small declared space; novelty is unknown.

| Lens | Assessment and original-domain check |
|---|---|
| Simplex | Deferred. If example mixtures are introduced later, nonnegative weights must sum to one; a mixture score cannot replace task outcomes. |
| N-ality | Applied only as an organizational lens separating task, representation, checker, model, data, budget and authority identities. No formal n-ary interaction analysis or measured benefit is established. Crossed controls must isolate the proposed mechanism. |
| Continuum | Not applicable to the initial discrete adapter. A later weight edit needs numerical/dtype and retention checks; small parameter distance alone predicts no behavioral guarantee. |
| Fuzzy logic | Deferred to exploratory prioritization. Correctness, artifact integrity and operational permissions remain exact gates; membership values are not probabilities. |

Relevant confounders are extra compute, task/holdout leakage, self-evaluator correlation, selective reporting, human-development analogy and pleasant-language proxies. Equal-budget controls, semantic split checks, independent task measurements, all-attempt retention and behavioral outcomes address these mechanisms. Their effectiveness remains to be measured in the actual model experiment.

## Primary sources

1. Raffel et al., 2020. [Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer](https://www.jmlr.org/papers/v21/20-074.html).
2. Oudeyer, Kaplan and Hafner, 2007. [Intrinsic Motivation Systems for Autonomous Mental Development](https://www.pyoudeyer.com/ims.pdf).
3. Finn, Abbeel and Levine, 2017. [Model-Agnostic Meta-Learning for Fast Adaptation of Deep Networks](https://proceedings.mlr.press/v70/finn17a.html).
4. Chevalier-Boisvert et al., ICLR 2019. [BabyAI: A Platform to Study the Sample Efficiency of Grounded Language Learning](https://arxiv.org/abs/1810.08272).
5. Huang et al., ICLR 2024. [Large Language Models Cannot Self-Correct Reasoning Yet](https://arxiv.org/abs/2310.01798).
6. Bai et al., 2022. [Constitutional AI: Harmlessness from AI Feedback](https://arxiv.org/abs/2212.08073).
7. Hubinger et al., 2024. [Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training](https://www.anthropic.com/research/sleeper-agents-training-deceptive-llms-that-persist-through-safety-training).
8. Butlin et al., 2023. [Consciousness in Artificial Intelligence: Insights from the Science of Consciousness](https://arxiv.org/abs/2308.08708).
