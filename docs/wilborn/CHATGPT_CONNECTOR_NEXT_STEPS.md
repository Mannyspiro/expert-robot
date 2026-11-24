# ChatGPT connector milestone: schema only

`wilborn_ops/tool_schema.py` defines a stable, read-only tool schema matching the synthetic business dispatcher.

This is NOT a connected ChatGPT plugin or a deployed API. It does not implement OAuth, a verified identity provider, tenant-bound sessions, per-record permissions, or the actual Artex framework. The current prototype must not be exposed publicly or used with real client records.

## Next verified end-to-end slice
1. Establish an approved, authenticated HTTPS business gateway with server-side authorization.
2. Integrate actual Artex checks at LLM input/tool boundaries, verified against adversarial fixtures.
3. Use production-reviewed encryption and key management; Titan remains unqualified pending source and security review.
4. Register a supported ChatGPT connector with read-only scopes.
5. Verify a real ChatGPT request to `list_cases` against synthetic data and preserve run evidence.
6. Only then add human-approved write operations, audits and customer-data privacy controls.

Business services should remain usable even if Merlin or the ChatGPT connector is unavailable.
