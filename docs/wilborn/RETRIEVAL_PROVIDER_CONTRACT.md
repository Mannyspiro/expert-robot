# Merlin controlled public retrieval boundary

This milestone adds a strict **offline receipt acceptance boundary** for an external fetch provider. It does not itself perform web requests, DNS resolution, robots inspection, TLS verification, or network egress enforcement.

The receipt requires an approved HTTPS hostname, identical requested/final URLs (no redirects), HTTP 200, supported content type, bounded UTF-8 body, and affirmative provider assertions for network/TLS/access policy. Its hash preserves content identity.

**Security limitation:** a caller can forge the Python receipt and its boolean flags. This is an integration contract, not an independently trusted attestation. Do not expose receipt construction to Merlin, the LLM, or untrusted clients. A future provider must run under separate credentials and network policy and return authenticated evidence. The current component must not be represented as live scraping.

Next acceptance test: connect a real provider with outbound firewall, DNS rebinding resistance, disallowed private/link-local/metadata IPs, no redirects, robots/terms checks, bounded rates and timeouts. Independently exercise permitted public fetch and blocked private fetch, then bind content hashes and citations to Merlin's canonical research ledger.

Data classes remain isolated: public research is neither synthetic Wilborn demo data nor verified client records.
