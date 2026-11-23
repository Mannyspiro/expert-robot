# Artex LLM cybersecurity framework — fail-closed integration seam

The `BusinessToolDispatcher` in `wilborn_ops/llm_boundary.py` is a synthetic-data tool dispatcher, **not** Artex itself. It defaults to a deny-all security adapter. Only a trusted host may supply an independently configured adapter; a caller cannot set an `artex_verified` flag anymore.

The permissive `SyntheticTestAdapter` in tests is **only a test double** and MUST NOT be deployed. Host injection alone is not an authentication or integrity guarantee; a trusted deployment, actual framework integration and independent tests remain necessary.

## Acceptance gates
1. Locate authoritative Artex source, version and supported security API.
2. Implement a production adapter that invokes real Artex checks and cannot be replaced by untrusted input.
3. Independently test prompt/tool injection, exfiltration, denial and failure cases with synthetic fixtures.
4. Enforce verified user identity and record-level authorization in the backend regardless of Artex result.
5. Identify and independently qualify Titan cryptography before applying it to real client data.
6. Keep the prototype loopback-only; never expose it publicly or store client records.

No production security qualification or live ChatGPT connector is claimed.
