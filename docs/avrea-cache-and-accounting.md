# Avrea cache and half-month accounting

Verified against Avrea and GitHub documentation on 2026-10-07.

## Reusable storage

Avrea documents a default **25 GB cache quota per repository**, shared across
GitHub Actions, Git LFS, compiler/build and package-manager caches. Entries
unused for seven days are eligible for eviction; quota pressure evicts the
least recently used entries first. This is the documented default, not an
inspection of this account's configured quota or remaining capacity.

`actions/cache@v4` and its restore/save variants work through Avrea's colocated
cache proxy. Namespaces follow GitHub repository and ref scoping. Separate
repositories do not share cache entries. Keys are immutable once created.

The CI workflow already restores a local C++ ccache directory and configures
the CMake compiler launcher when ccache is present. Avrea also documents a
preconfigured remote ccache backend on its runners. Actual cache availability,
hits and performance must be read from a completed job; configuration alone
does not establish a hit rate or speedup.

Compiled functions, dependency packages and rebuildable analysis intermediates
can be retained as cache files. A cache hit does not qualify a scientific
result, a proof or an optimization. Any future result cache must bind inputs,
source, backend/version, policy and validation evidence, and tolerate eviction.
Project source belongs in Git; qualification evidence needs retained artifacts
or persistent storage. Cache is not the only copy of either.

## Accounting corrections

The repository policy retains independent **1,500-credit limits for days 1–15
and 16–month-end in America/Phoenix**, with no borrowing. Runner weights and
full-timeout reservations are unchanged.

The budget guard now:

- Charges proven unassigned queue entries zero. The API must explicitly report
  no runner ID/name and an empty step list; missing metadata stays conservative.
- Reserves the full timeout for assigned or in-progress jobs.
- Counts all workflow attempts (`filter=all`), including earlier reruns.
- Enumerates bounded repository run metadata rather than filtering by creation
  date. A run created in an older period can be rerun or start during this one.
- Avoids querying jobs for completed runs last updated before the period.
- Rejects ambiguous completed-job timing and API/enumeration failures.

On 2026-10-08, the completed queue-cancellation lifecycle was reproduced from
jobs 113033122335 and 113033823214: their synthetic `started_at` equals
`created_at`, the later completion records cancellation, runner ID/name are
explicitly empty, and `steps` is empty. These jobs waited about two hours
without acquiring a runner. That exact cancelled/skipped case now charges zero.
Missing or differing creation time, backwards completion time and failed
startup remain fail-closed. Assigned or stepped cancellations remain billable.
Diagnostics now include the run/job IDs needed to investigate an ambiguous
record. This correction does not change caps, weights, reservations or the
authority of provider billing.

The 2026-10-08 repository audit examined 1,309 relevant workflow runs and
1,271 job records. It found 3,396 known weighted credits and 204 unresolved
job records. The known estimate alone exceeds the first-half 1,500-credit
cap; unknown records cannot establish additional available credit. This
is a historical snapshot, not an account balance or a qualification result.

Nine research validation workflows have therefore moved to existing free
GitHub-hosted Ubuntu runners. Their old Avrea workflow registrations and
timeout estimates remain in the accounting allowlist so previous attempts
still count. A job is excluded as hosted only when its requested labels are
recognized Ubuntu-hosted labels, its runner ID is positive and its runner
name identifies GitHub Actions. Unknown or Avrea-labelled assignments remain
conservative. Specialized Avrea workflows retain the cap and reservation gate.

Regression tests cover synthetic scheduling timestamps, queued jobs with and
without assignment evidence, rejected jobs, ambiguous completions, runner
weights, rerun history and older runs updated in the current period.

This remains a **repository-scoped estimate**. Avrea's account-wide billing
usage is authoritative; work in other repositories must be reconciled before
treating this estimate as the organization's remaining allowance.

## Sources

- https://docs.avrea.com/cache/storage/
- https://docs.avrea.com/cache/github-actions/
- https://docs.avrea.com/cache/build-cache/ccache/
- https://docs.github.com/en/rest/actions/workflow-jobs#list-jobs-for-a-workflow-run
