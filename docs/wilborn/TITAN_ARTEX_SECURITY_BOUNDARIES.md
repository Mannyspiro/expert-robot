# Titan encryption and Artex LLM cybersecurity framework

Corrected architecture: **Titan is an encryption scheme; Artex is a cybersecurity framework for LLMs. Neither is an AI agent.** Earlier role descriptions are superseded.

- Merlin: AI research, code proposals and approved business workflow automation.
- Artex: intended LLM security framework for prompt/tool input boundaries, prompt injection defenses, tool permission enforcement and evaluation. Its exact implementation and coverage remain to be verified.
- Titan: candidate cryptographic scheme for protecting business data. Its specification, implementation, version, security properties and key management remain to be verified.
- ChatGPT: intended conversational entry point; a protected service must authenticate and authorize each business operation.
- Authorized human/credential broker: business approvals and repository credential lifecycle.

## Integration and security gates
Artex must not be treated as a human reviewer or an autonomous agent. Test it as an actual middleware/framework component with adversarial fixtures and independent security assessment before making protection claims.

Do not deploy Titan to protect client records or GitHub secrets until its exact cryptographic specification and implementation are independently qualified. Prefer established AEAD encryption and managed keys for production in the meantime. Do not invent a Titan cipher or imply it is active.

GitHub secret rotation must be handled by an approved provider-side broker without exposing secret values to Merlin, prompts, commits or logs. No GitHub secrets were changed by this work.

No real client data in public source control. The prototype policy is not production authentication.
