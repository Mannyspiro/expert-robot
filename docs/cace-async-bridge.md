# Asynchronous CACE capability bridge

Run local transport checks with `python3 tests/cace_bridge_test.py`.
The tests use local temporary repositories and do not contact GitHub or allocate runners.

`python/cace_bridge.py dispatch` creates one fresh CACE request branch and prints a JSON receipt. Keep that receipt. Reusing it does not dispatch a duplicate. `collect` reads once, validates the request and dispatch commit, and exits: 0 for an observation, 2 for pending, 1 for an error. A pending result is not proof success.

```sh
python3 python/cace_bridge.py dispatch --source-sha FULL_40_CHARACTER_SHA \
  --quota /secure/path/quota.json --receipt /secure/path/receipt.json
python3 python/cace_bridge.py collect --receipt /secure/path/receipt.json \
  --output /secure/path/result.json
```

Live dispatch requires authenticated SSH access to `morganaspim/Cace-app` and verified GitHub free allowance for its publisher. In GitHub Actions, the Expert Robot dispatcher account needs its own allowance as well. The template `config/cace_free_quota.example.json` deliberately authorizes nothing. It must be populated from real account evidence; an Avrea balance is not a GitHub-hosted allowance.

The manual `cace-bridge.yml` workflow additionally requires the repository variable `CACE_BRIDGE_ZERO_SPEND_ENFORCED=true`, a fresh `CACE_BRIDGE_QUOTA_JSON` and the existing `RAILWAY_SSH_PRIVATE_KEY` secret. CACE publication requires its own zero-spend variable. These are attestations about actual platform settings, not billing controls implemented by the script. Check platform zero-overage enforcement before enabling them. No additional workflow runs are launched by default.

The CACE probe has a two-minute timeout on the existing serialized ARM64 lane. Hosted dispatch and publication each have a three-minute timeout. Collection is a separate operation; no Avrea runner waits for the result, no artifact storage is allocated, and no candidate code is copied to the self-hosted runner.

Receipts bind observations to commits and requests; they are not cryptographic proof that a repository or runner is uncompromised. Live qualification and the later proof-execution sandbox are outside this initial capability probe.
