# Synthetic-versus-real record separation: mandatory release gate

Current code is a synthetic-data prototype only. The provenance module is an explicit
contract and negative test suite; it is not a production ingestion or identity system.

## Required invariant
Never silently infer that a synthetic record is a real person, appointment, quote,
payment, or service completion. Every API response must identify its environment and
data classification. Unknown provenance fails closed.

## Deployment enforcement
- Physically separate production and demo databases, service identities, encryption keys,
  backups, storage and network permissions.
- Trusted server assigns immutable provenance and environment at ingestion.
- Production requires verified source identity, consent and evidence of real-world origin.
- Reject all cross-environment reads/writes, even when labels are modified.
- Never promote synthetic data by relabeling; use separately reviewed real-world ingestion.
- Mark every AI result DEMO or VERIFIED REAL, and disclose mixed or unknown inputs.
- Run adversarial tests for mislabeled imports, mixed joins, backup restores, cloned IDs,
  forged metadata and prompt-injected claims of authenticity.
- Audit classification decisions and approvals without exposing personal information.

## Known limitation
`Provenance` is a caller-constructible Python dataclass, so it cannot attest authenticity
or stop malicious code from constructing false labels. Production must derive provenance
from a trusted server and enforce isolation in storage and authorization. The current
Wilborn gateway and store do not yet enforce this module across all operations.
