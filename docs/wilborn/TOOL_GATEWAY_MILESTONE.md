# Business gateway prototype — milestone

Committed implementation: `wilborn_ops/gateway.py` exposes three synthetic-only operations: list_cases, get_case_status, service_metrics.

The gateway requires a caller-supplied Identity containing subject, tenant and scopes. This is a **domain authorization prototype**, not identity verification: callers can construct identities. Do not expose the gateway directly to untrusted network callers or real customer data.

## Intended ChatGPT architecture
ChatGPT -> authenticated identity provider / connector -> server-side verified identity -> BusinessGateway -> protected database. Merlin receives permitted synthetic or redacted business context. Artex is an LLM cybersecurity framework to be integrated at prompt/tool boundaries, not an agent. Titan is an encryption scheme to be independently qualified, not an agent.

## Remaining production work
- Verify cryptographic identity and tenant membership at trusted server boundary.
- Authorize individual case access, not only operation-level scopes.
- Integrate and independently test the actual Artex framework; identify its source/version and security scope.
- Recover Titan specification and independently validate before use with sensitive records.
- Add audit logs, rate limits, TLS, idempotency, retention and backups.
- Connect and verify a supported ChatGPT plugin/connector; do not claim integration before an actual end-to-end run.
- Keep all real client data, tokens and repository secrets out of public source control.
