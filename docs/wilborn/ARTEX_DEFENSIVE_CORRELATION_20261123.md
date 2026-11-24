# ARTEX passive detection integration checkpoint

Parent: `d3f54f88227b42157e0615d5b70841af32394224`. All three CI workflows passed at that revision ([native](https://github.com/Mannyspiro/expert-robot/actions/runs/45304198677), [79 business + 8 CACE tests](https://github.com/Mannyspiro/expert-robot/actions/runs/45304198690), [public probe](https://github.com/Mannyspiro/expert-robot/actions/runs/45304198641)).

## Scope and source identity

Independent passive implementation, informed by the public community fork's experimental detection rules at commit `133f3cf97f2d153227a1a95d3c4b7cd5b72020a6`. Upstream AGPL-3.0 metadata and LICENSE were read in the previous checkpoint. No upstream program or rule engine was imported, built, run or vendored. This does not integrate or qualify the offensive ARTEX framework.

Source ledger (Git blob identity, not independent proof of security):
- guard-audit rule `dd6f8fea5d7564ec0b6fac5dd95fa2653c27fde9`
- recording-CA rule `ea32a3f23ff195cc50cafbb72cc47f0c6b31f629`
- update egress rule `50d94ea93c8de3637341d9a2fb47ed5befc3702a`
- inbound user-agent rule `68e22fa244ecde28a24060ad4ed77cdef94886db`
- guard-block correlation rule `bdb9c8e5f0169dbf3a8e8c7ae36f14a22743c6cf`

These are heuristic leads. The local guard rule uses a runtime-message prefix, and the CA rule an exact path suffix, narrower than upstream search semantics. The other two match exact typed header values. This is not full Sigma conformance. Host-local guard correlation follows the published count/window, with explicit half-open window semantics. Independent local authentication/tool-denial correlations use provisional demo defaults. Sensor authenticity, event deduplication, persistent state, cross-host grouping, production baselines, coverage and false-positive rates are unqualified. A lead is not proof of compromise or framework execution; absence of alerts is not proof of safety.

## Experiment and gates

Before execution: baseline is a payload-free counter. Hypothesis: a fixed per-rule bounded sliding window detects a burst in a single synthetic service, without storing identities or sensitive input. Acceptance: valid typed events and negative fixture controls, exact boundary expiry, independent grouping, malformed/real scope rejection, concurrent counts, no unbounded event queue, no automatic execution. HTTP and tool dispatcher tests must preserve denial of unauthorized operations and ordinary authorized synthetic reads. Native CI and existing business/CACE/public probe must remain intact.

N-ality: separate source channel, event class, scope, timing and authorization; use exact categorical checks. Simplex, continuum and fuzzy structures not applicable to Boolean authorization and exact event counting. Correlation is an alert, not causal attribution: duplicate messages, benign debugging tools, and legitimate repeated failed access attempts are competing explanations. Fresh-process reset loses historical counts. Tune future thresholds using independently labeled samples, not the same fixture tests.

No OCI execution is needed for this portable, credential-free synthetic experiment. Actual ARTEX execution, secret sharing, live host scanning, automated offensive testing and production deployment are outside this change. The release gate remains closed. Next: independent production telemetry source and deduplication contract, private evaluation, operator-reviewed alert workflow, and actual approved framework qualification or a separately reviewed defensive replacement.
