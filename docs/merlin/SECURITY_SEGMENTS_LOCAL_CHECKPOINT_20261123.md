# Studio review of a staged security rotation

Local continuation of draft PR #229 from
`f6f29c5b664f2c89c435eec4a6719a0c07874233`. The producer candidate is local
commit `16adbead569d81aaf9e7029dee29038a95a3d24a`, based on draft PR #228 at
`bba73dbede1dea3beb71a5fc0f78ade66f381b8c`.

## Implemented and observed

Studio continues to accept the existing v1 single-ledger summary. The v2
summary shows the reviewed predecessor archive and untouched successor genesis
as two ordered segments, retaining their own revisions and pending alerts.
The page labels the view as a staged rotation, reports that writer handover
has not been verified and that the successor has not been activated, and
distinguishes host claims from independent verification by Studio.

The import rejects additional fields, identities or payloads; unknown event
categories; inconsistent counts; duplicate JSON keys; reordered segments;
missing current anchors; incident ordering errors; successor activity; and
attempted changes to the synthetic-data and authority flags. The read-only
route keeps the existing loopback, origin and mutation protections.

Observed local checks on Python 3.12.14 and cryptography 50.0.0:

- All 48 portable Studio tests passed, including 12 security-view tests.
- The source-only ZIP passed its complete inventory and shipped-byte hashes:
  30 payload files plus the package manifest. SHA-256:
  `62327585e33464bfff0b72a4f0e8d65d15e4300fb84a2697de03c01517d92dac`.
- A fresh producer process generated the real v1 fixture export after encrypted
  backup/recovery: five events, one review, anchor revision seven. A separate
  process loaded the extracted package and verified the actual HTTP page.
- A second producer process staged and reviewed a real encrypted rotation and
  exported v2: two predecessor events, one unresolved integrity alert, and an
  empty successor at revision one. Another extracted-package process verified
  the two-segment page, segment-local revisions, pending predecessor alert,
  origin rejection and stable startup snapshot. Source/archive bytes were
  preserved.

`portable/tests/security_handoff_smoke.py` pins the producer commit and now
rejects an altered tracked or nonignored untracked producer worktree before
and after running the fixture. A matching HEAD alone is insufficient evidence
that the executed source matches the pin.

## Publication and release state

These changes and the producer commit remain local. Automatic approval review
rejected a GitHub tree creation because recovered user context included an
earlier repository-write denial. No alternate publication route was used.
The workflow's new producer pin is a local review commit; publication must
preserve the producer commit first, then the Studio commit, before remote CI
can check out that pin. The original remote PR heads are unchanged.

The test package contains source only: no model weights, Python runtime or
inference engine. This is integration evidence, not a full Merlin release.
Single-writer transfer and restart, independent operational key/anchor custody,
the approved isolated OCI monitoring profile, private-host validation and
production release remain open. Existing provider, browser and model work is
not requalified by these checks.

## Subsequent approved publication

The user explicitly authorized publishing these prepared security and Studio
changes to the existing review branches. The local-only rejection recorded
above describes the earlier checkpoint and no longer blocks this specific
publication. Merge and deployment are separate from this publication.

Local Git had no authenticated push credentials, so the connected GitHub
account created the producer commit
`e619f14b0ac0b1439065bb99a7ea41ae52c95f7f`. Its complete Git tree
`7a82598831a5491b7b6c034a52e22bc81fb4495b` exactly matches approved local
commit `16adbead569d81aaf9e7029dee29038a95a3d24a`. Only commit metadata
differs. The branch update was a fast-forward guarded by the expected parent.

Studio's workflow checkout and handoff constant now pin that published
producer. The cross-process v1 and v2 handoff was rerun against a clean
checkout of the published producer and passed with the same package and
snapshot hashes. No application logic, workflow permissions, dependency or
runner scope changed during this pin reconciliation. Refer to the PR's exact
source CI results for the publication outcome; the original local results
above remain historical evidence rather than a substitute for remote CI.
