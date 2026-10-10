# CACE OCI runner and deploy-key handoff (Expert Robot)

> **Purpose:** Make existing infrastructure discoverable by another ChatGPT
> conversation or coding agent reading this repository. **Never store or
> publish secret values, private keys, tokens, SSH key bodies, or credentials.**
>
> Last code-level inspection: 2026-10-10. The user reports that CACE already
> has an OCI self-hosted GitHub runner and that the GitHub-side deploy key is
> available. **Direct online registration and successful SSH access have not
> been independently verified from this chat.**

## Repositories and service boundaries

- Expert Robot source and handoff: `Mannyspiro/expert-robot`
- CACE runner repository (user-supplied existing host):
  `morganaspim/Cace-app`
- Existing CACE OCI GitHub runner, historical host name: `cace-oci-a1`
  (historical project context only; do not assume it is currently online)
- Runner selector in the **generated** CACE workflow:
  `runs-on: [self-hosted, cace, oci, aarch64]`
- Expected free qualification lane identifier:
  `cace-oci-aarch64`
- SSH repository URL configured by the bridge:
  `git@github.com:morganaspim/Cace-app.git`
- Return repository: `Mannyspiro/expert-robot`

**Important:** The GitHub App connected to some ChatGPT sessions may see
Expert Robot but return HTTP 404 for Cace-app. That does not disprove the
user's CACE runner or deploy-key access. It means the ChatGPT connector has
not been granted sufficient visibility. Do not infer live runner status from
historical documents.

## Relevant versioned workflows

1. `.github/workflows/external-free-runner-bridge.yml`: designed to run on
   the Avrea free 8-vCPU runner, check Avrea's half-month budget, then use a
   separately held SSH key to clone/push an isolated
   `executor/expert-robot-bridge` branch in Cace-app. The generated CACE
   workflow requests `[self-hosted, cace, oci, aarch64]` and returns
   qualification evidence. **The bridge is not proven operational until an
   end-to-end source-bound run returns verified evidence.**
2. `.github/workflows/free-runner-capability-probe.yml`: existing probe for
   remote branch/workflow capabilities; does not establish current OCI
   availability unless its run has succeeded and evidence is inspected.
3. `.github/workflows/cace-return-pr.yml` and
   `scripts/validate_cace_return.py`: return-evidence/PR gate.
4. `scripts/check_avrea_halfmonth_budget.py` and
   `config/avrea_half_month_budget.json`: **mandatory fail-closed** Avrea
   accounting. An Avrea runner being assigned is not approval to bypass the
   budget cap.
5. `tests/cace_bridge_budget_order_smoke.py`: asserts that budget checks
   precede deploy-key access or CACE repository mutations.

## Secret **names only** (never values)

The current bridge's **source workflow** refers to the following
repository/Actions secret *names*. This is inventory of references; it is
**not** verification that each secret exists or has the right permissions:

| Name in workflow | Role |
| --- | --- |
| `RAILWAY_SSH_PRIVATE_KEY` | Expert Robot bridge's existing SSH key input used to access the Cace-app repository; historical name, despite the target being CACE |
| `EXPERT_ROBOT_SSH_PRIVATE_KEY` | One of the generated CACE-to-Expert-Robot return-key candidates |
| `EXPERT_ROBOT_DEPLOY_KEY` | Alternate generated return-key candidate |
| `CACE_TO_EXPERT_ROBOT_SSH_KEY` | Alternate generated return-key candidate |
| `EXPERT_ROBOT_DEPLOY_PRIVATE_KEY` | Alternate generated return-key candidate |

Do not expose any `secrets.*` value in logs, PRs, chat transcripts or
artifacts. Only a suitably permissioned GitHub Actions job can read its own
secret environment; the connected ChatGPT GitHub tools cannot retrieve them.
Confirm *read-only vs write* GitHub deploy-key scope before executing the
bridge: the bridge writes its Cace-app dispatch branch, so it requires
explicit, narrowly scoped write authorization. Prefer a separate scoped
credential rather than broad owner/repository access.

## How the bridge is intended to work

```text
Expert Robot commit (untrusted PR source)
  -> Avrea budget / safety gates
  -> pinned source archive and SHA
  -> SSH deploy-key bridge to Cace-app isolated dispatch branch
  -> GitHub Cace-app workflow: [self-hosted, cace, oci, aarch64]
  -> sandboxed checks, bounded artifacts, source hashes
  -> authenticated evidence returned to Expert Robot for review
  -> Lean and CACE independent qualification gates
  -> NO automatic merge, RSI promotion, or authority expansion
```

Never treat an uploaded artifact or a PASS-looking JSON field as a verified
proof merely because it is present. Match request ID, exact source commit,
artifact integrity, provenance and independently audited Lean/CACE criteria
before considering it valid. Preserve CACE's audited-root and one-job rules.

## Safe next action for another chat

1. Open the repository's versioned workflow files above. Reuse existing
   infrastructure and check current PR head; do not recreate deploy keys.
2. Inspect Cace-app's GitHub **Settings → Actions → Runners** (if granted
   access), or a recent known OCI job's `runner_name`, `labels`, and steps
   to confirm online status. The dedicated Cace-app GitHub connector may need
   authorization; lack of visibility must be reported rather than guessed.
3. Run non-secret static/smoke validation first. Resolve any bridge credential
   scope, branch-collision, provenance or budget issues *before* dispatch.
4. Only trigger a free, bounded qualification lane with budget approval.
   Check actual Cace-app evidence against the exact Expert Robot commit.
5. Leave research PRs draft and promotions disabled until formal and
   numerical verification is independently established.

**Restrictions:** Do not use Cloudflare or Fjord for this handoff. Do not
enable paid resources, alter runner registration, publish keys, or change
`cace-app` production deployment.
