# Bounded recovery workload experiment
Parent fcbd77d292aac0fe4e9246db7d1121df90a84277: targeted cutover workflow 45308425033 passed 115 Wilborn tests and eight CACE tests, including four new staged cutover checks.

Predeclared workload: one fresh synthetic ledger, fixed round-robin sequence of four event kinds, cumulative checkpoints 16, 64, 128, 256 events. Measure elapsed ingestion per stage, mean milliseconds per event, elapsed report plus history verification, database bytes, encrypted copy and reopen/history elapsed seconds. Acceptance: exact ordered history, independent expected counts and revisions, source untouched, final signed anchor and exact restored history. Stop at 120-second child deadline and 64 MiB database budget. Emit only numerical measurements and runtime versions, no keys, raw database, signing identities or receipt. Upload minimized JSON. This is a single CI-host baseline, not a latency SLA or a measured private-host/OCI qualification.

The current implementation re-verifies the full chain on each write. Expect increasing write cost as history grows; preserve measurements including failures before choosing a performance optimization. Capacity at 1024 revisions is not tested by this run, so do not extrapolate it as qualified. Alternatives include smaller independently anchored segments or cached validation under an explicit trusted storage contract; neither changes the exact integrity or authorization checks. N-ality separates event volume, storage, compute, source identity and integrity; no simplex, fuzzy or continuum representation replaces exact verification. No production policy chosen without measured private-host evidence.

## Subsequent full-capacity evidence — exact source bba73dbe

The paragraph above records the original bounded experiment. The later source
`bba73dbede1dea3beb71a5fc0f78ade66f381b8c` extends the retained experiment to
16, 64, 128, 256, 512 and 1,023 events, reaching revision 1,024. Its
[prototype CI run 45316057367](https://github.com/Mannyspiro/expert-robot/actions/runs/45316057367)
passed 128 Wilborn tests and eight CACE verifier tests. Artifact `14885501367`
retains the minimized synthetic workload JSON. The independent
[native CI run 45316057427](https://github.com/Mannyspiro/expert-robot/actions/runs/45316057427)
passed all 33 C++ tests and the retained smoke/guardrail checks.

At capacity, both event and operator-review overflow were rejected and the
history remained unchanged. The 2,109,440-byte database recovered all 1,023
encrypted event records against the retained signed anchor. Copy took
0.482339 seconds and reopening/history verification took 0.165566 seconds.
The paired combined snapshot took 86.155 ms versus 166.354 ms for separate
report/history reads. Reviewed rotation took 1.700378 seconds and preserved
the predecessor archive bytes and unresolved alerts; the successor remained
at genesis, revision 1, with no writer activation.

These observations close the previously unmeasured full-capacity case for
this exact source and one synthetic Linux x86_64 CI workload (Python 3.11.18,
cryptography 50.0.2). They do not qualify production latency, real signer
custody, concurrent writer handover, the OCI monitoring profile or a private
host. Later code changes require their own affected checks.
