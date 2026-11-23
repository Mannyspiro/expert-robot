# Differential path parser contract

This offline experiment compares a deliberately naive policy parser with a toy downstream router. It does not identify a vulnerability in Python or a deployed application. No sockets or external targets are used.

The repaired accepted language is an absolute ASCII path, at most 256 characters, with nonempty segments containing letters, digits, underscore or hyphen. Root is accepted. One layer of percent encoding of those characters is accepted. Queries, fragments, authorities, controls, dots, encoded separators and residual percent signs are rejected. This intentionally small language is not a general URL implementation.

Policy permits only root or a first segment exactly `public`. The consumer receives the validated canonical path. An independent oracle decodes bytes and checks segment characters without using the production canonicalizer. Required constraints on accepted x:

- Idempotence: N(N(x)) = N(x).
- Consumer agreement: R(N(x)) = N(x).
- Independent representation agreement: O(x) = N(x).
- Authorization: permit(x) implies consumed resource is root or its first segment is public.

Enumerate root plus one through three segments from a recorded finite vocabulary, with empty/query/fragment suffix variants and malformed fixed cases. Keep all counterexamples and deletion-minimized witnesses. Verify both original and minimized witnesses. Mutation checks must detect an identity canonicalizer, raw-prefix policy and downstream resource rewrite. An extra decoding pass has no effect on this accepted language, since residual percent signs are excluded. Exhaustive here means exhaustive within this grammar, not every string or every URL standard. Rejecting most inputs alone is insufficient: positive encoded/public/private cases must match the oracle.

CACE's existing numerical CRL/FEM compiler is not a path-parser proof engine. The JSON report is a candidate experiment-to-math handoff only; CACE execution and Lean qualification remain false. The next suitable bridge is a finite-language relation proof with explicitly bounded quantifiers, before considering a richer language.
