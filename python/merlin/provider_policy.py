"""Provider selection policy for Merlin's conversational gateway."""


def select_chat_provider(provider: str) -> str:
    """Select a provider without allowing configuration to imply cloud consent.

    Auto is deliberately local-first. Cloud inference requires an explicit
    provider='cloud' request; unavailable local inference fails closed.
    """
    if provider not in {"auto", "local", "cloud"}:
        raise ValueError("provider must be auto, local, or cloud")
    return "cloud" if provider == "cloud" else "local"
