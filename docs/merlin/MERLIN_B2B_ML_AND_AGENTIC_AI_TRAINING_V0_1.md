# Merlin Learning: intuitive ML and agentic AI for B2B teams v0.1

**Status:** curriculum and competency specification; local lab prototype, not a deployed multi-tenant training product.

## Product outcome

Train business teams to understand, evaluate and operate machine-learning and agentic-AI systems in real work. Measure demonstrated operational competence, not prompt memorization or tool familiarity.

Every course maps to canonical idea IDs and a versioned competency graph. Learner attempts use the shared Merlin learner evidence store. Hermes selects the next activity from demonstrated skills, role needs, prerequisites and uncertainty.

## Teach intuitively: one idea, several views

1. **Concrete experience:** a familiar business problem or interactive simulation.
2. **Visual model:** show the flow, state changes, inputs, outputs and failure points.
3. **Plain-language explanation:** one short idea, without unexplained jargon.
4. **Worked example:** reveal reasoning step by step; ask the learner to predict the next step first.
5. **Hands-on practice:** change data, constraints or workflow conditions and observe consequences.
6. **Explain-back:** learner explains why the result occurred.
7. **Transfer:** solve a new business scenario with different constraints.
8. **Delayed retrieval:** revisit later with a fresh problem.

Offer visual, text-first, audio, example-first, historical and technical paths. Adapt modality to accessibility and learner choice, not presumed ability. Use graduated hints rather than revealing full solutions before a useful attempt.

## ML foundations path

| Canonical skill | Intuitive teaching model | Demonstration |
|---|---|---|
| Data and labels | Examples with answer keys | Label invoices or support tickets |
| Features | Clues available before the answer | Compare amount, vendor, wording and date |
| Training | Practice examples used to fit a rule | Fit a simple classifier |
| Validation/test split | Practice exam vs unseen exam | Detect leakage by changing the split |
| Generalization | Does it work on tomorrow's cases? | Test on a new vendor or quarter |
| Classification metrics | Different mistakes have different costs | Compare precision, recall and confusion matrix |
| Calibration | Confidence should match reliability | Inspect confidence buckets |
| Drift | The world changes after training | Shift vendor mix and measure degradation |
| Human review | Escalate uncertain/high-cost cases | Set a review threshold |
| Monitoring | Observe real outcomes over time | Alert on drift and error cost |

Learners distinguish model accuracy from business value. False negatives and false positives can have different costs. Teach leakage, sampling bias, class imbalance, privacy, provenance and evaluation before deployment.

## Agentic AI for B2B

Use a bounded workflow as the core mental model. An agent observes a task, plans bounded steps, calls approved tools, checks results and either continues or requests human approval.

Canonical skills:
- task decomposition and workflow mapping;
- deterministic automation vs model inference vs agentic orchestration;
- model selection by task quality, latency, cost, privacy and reliability;
- context design, retrieval and source-grounded answers;
- tool schemas, least privilege and scoped credentials;
- state, memory, idempotency and event-driven orchestration;
- planning, delegation and bounded retries;
- evaluation sets, trace inspection and regression testing;
- human approvals and escalation;
- auditability, rollback, incident handling and change management;
- cost/latency/quality optimization and vendor portability.

Teach the difference between model, agent, tool, workflow, memory, retrieval, policy and verifier. Learners identify which component owns each decision.

## Interactive B2B scenario: invoice exception handling

A fictional company receives invoices. The learner designs a workflow:
1. Extract fields from the document.
2. Retrieve purchase-order and vendor context.
3. Classify the invoice as routine or exception.
4. Check arithmetic, policy and vendor identity.
5. Route uncertain or high-value cases to a person.
6. Post only an approved transaction to a sandbox ledger.
7. Record evidence and monitor outcomes.

The lab exposes three controls:
- **Automation coverage:** share of routine cases handled without a person.
- **Review threshold:** how uncertain or high-impact a case must be before escalation.
- **Verification depth:** checks performed before a write action.

The simulation reports illustrative cost, latency, unresolved cases and residual error exposure. These are synthetic teaching values, not vendor benchmarks. Learners compare at least three configurations and justify the trade-off. Lowest latency is not automatically best.

## Role-based pathways

- **Executive / sponsor:** opportunity framing, process selection, ROI assumptions, risk ownership, procurement and operating model.
- **Business process owner:** task decomposition, exception taxonomy, service levels, approval boundaries and process redesign.
- **Operations user:** reviewing outputs, handling exceptions, correcting records, escalating safely and recognizing automation limits.
- **Analyst / data practitioner:** data quality, labels, evaluation design, metrics, drift and experiment interpretation.
- **Developer / AI engineer:** retrieval, tool interfaces, agent orchestration, structured outputs, evals, tracing, deployment and cost controls.
- **Risk / legal / compliance:** privacy, retention, provenance, accountability, vendor review, human oversight and incident response.
- **Manager / trainer:** coaching, competency evidence, remediation and team-level aggregate analytics.

Roles select relevant examples and assessment contexts; they do not lower competency standards.

## Optimize the whole workflow, not only the model

Use a constrained objective:

    utility = task_quality - λ1*cost - λ2*latency - λ3*human_rework - λ4*error_impact

Weights are business-specific and agreed with the process owner. Enforce hard constraints for privacy, policy, quality floors, human approval and reversible actions before optimization. Do not trade away safety or authority boundaries to improve a score.

Teach a progression:
1. Establish a manual baseline.
2. Automate deterministic steps first.
3. Add retrieval for trusted business context.
4. Add a model only where judgment or language understanding is needed.
5. Add agentic planning only where multi-step adaptation is useful.
6. Add verification and human approval around consequential writes.
7. Measure quality, exception rate, latency, total cost and rework.
8. Run held-out evaluation and shadow mode before rollout.
9. Monitor drift and maintain rollback.

## Assessment and learner evidence

Each problem references an idea ID, problem ID, rubric version and evidence dimension. Measure recognition, explanation, procedure, representation translation, estimation/error detection, transfer, proof/justification and delayed retention separately.

B2B competency tasks include:
- identify leakage in a training/test split;
- choose precision or recall based on the cost of each error;
- explain why drift invalidates a previously strong model;
- map an existing process into tools, decisions and human checkpoints;
- diagnose an agent trace and locate the failed step;
- select a model/workflow configuration under explicit cost and latency limits;
- write a least-privilege tool contract;
- decide when to stop, retry, escalate or request approval;
- demonstrate rollback and evidence review.

A multiple-choice answer is one signal only. Qualification requires independent sessions, constructed explanation, scenario transfer and delayed reassessment. Managers see skill-level evidence and cohort patterns, not hidden personality or sensitive-trait inferences.

## Hermes and multi-agent teaching architecture

- Hermes Learning Coordinator: chooses next objective and explains why.
- Subject Teacher: gives intuitive and technical explanations.
- Scenario Coach: presents realistic role-specific cases.
- Assessment Designer: creates parallel problems and rubrics.
- Feedback Coach: diagnoses misconceptions and offers graduated hints.
- ML Evaluator: teaches metrics and checks learner calculations.
- Agent Workflow Coach: inspects traces and workflow design.
- Governance Coach: checks approval, privacy, provenance and rollback understanding.

Agents may draft lessons, feedback and scenarios. Canonical content, scoring rubrics and high-stakes certification require versioning and qualified review. Hermes recommendations are advisory; instructor or organization policy controls certification.

## B2B deployment requirements before production

- Tenant isolation and company-scoped roles.
- SSO/SCIM, audit logs and organization-managed retention.
- Data minimization; pseudonymous learner IDs where possible.
- No training on customer data without explicit contractual authorization.
- Export, deletion and correction paths.
- Accessible alternatives and mobile/low-bandwidth support.
- Instructor/admin review of generated content and rubrics.
- Versioned model, prompt, tool and lesson provenance.
- Evaluation for accuracy, bias, drift, robustness and task-specific performance.
- Human appeal, override, incident response and rollback.
- Separate employee learning records from performance-management decisions unless explicitly governed and disclosed.

## Research grounding

The instructional design uses worked examples with stepwise retrieval prompts and feedback, adaptive difficulty, scaffold fading, transfer tasks and delayed checks. A 2025 study reported improved recall and problem-solving after a week from stepwise retrieval embedded in worked examples; a 2025 meta-analysis found adaptive difficulty and scaffolding among useful adaptive-training interventions. These findings inform the design but do not guarantee outcomes for every workplace or subject.

- [Stepwise worked-example retrieval study](https://doi.org/10.1016/j.learninstruc.2025.102196)
- [Adaptive training meta-analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC12413037/)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [NIST Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)

## Acceptance criteria

- Learner can explain the difference between ML prediction and agentic workflow execution.
- Learner can choose metrics from business error costs and explain the trade-off.
- Learner can design an agent workflow with bounded tools, explicit approvals and verification.
- Hermes recommendations cite learner evidence and canonical prerequisites.
- Performance is measured on unseen scenarios and delayed retrieval, not course completion alone.
- Every recommendation, rubric and agent trace is versioned and auditable.
- No learner model or teaching agent grants production execution authority.
