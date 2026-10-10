# Offline two-trace CPU information-flow toy

This is **not** a processor simulator or a security exploit. It is a tiny
finite-state example of a *hyperproperty*: two runs with the same public input
but different secrets must produce the same public observation.

The model intentionally distinguishes a program's architectural output from
its hypothetical cache/timing observations. Four synthetic models are compared:
a public-only observation, a speculative cache trace, an artificial rollback
which clears all simulated transient cache effects, and secret-dependent time.
The rollback is a mathematical toy, **not** a physical Spectre mitigation.

Source: `two_trace.py`. Independent closed-form oracle and deliberate negative
controls: `test_two_trace.py`.

Run without external packages or cloud compute:

```sh
python3 -m unittest discover -v -s research/security/experiments -p test_two_trace.py
python3 research/security/experiments/two_trace.py --output /tmp/two-trace.json
```

Initial local result on 2026-10-10: **6/6 unittest groups PASS**,
**96 finite secret-pairs** considered, **8** modeled (mode, observation-layer)
cases, all architectural projections independent of the secret, and **12**
counterexamples each in the secret-dependent cache and secret-dependent time
cases when joint architectural+microarchitectural observations are considered.
Public-only and fully discarded scratch-cache toy cases have zero witnessed
counterexamples. Synthetic report SHA-256
`00a929ed8262554d349c0582fc4bcf66fe3aaace310f6d8c92856cb99b4f6cc7`.
This is **bounded enumeration**, not an independent real hardware measurement,
not Lean verified, not CACE executed, and not promotion-qualified.

The independent oracle must never be trained on or derived solely from the
producer trace. A useful next formal statement (still **unproved**):

For each model `m`, low observation layer `o`, public input `p` and two
secrets `s1,s2`, if `public(s1)=public(s2)=p`, then
`observe(o,run(m,p,s1)) = observe(o,run(m,p,s2))` for all secrets
*iff* the modeled joint-observation leak is absent.
Prove or refute separately at the chosen observation layer; explain exactly
which CPU caches and predictor state an eventual hardware refinement models.

See `docs/computer-security-systems-history-to-mathematics-2026-10.md`
for primary sources, hardware assumptions, historical incident cases,
related tools and the Experiment→Lean→CACE qualification route.
