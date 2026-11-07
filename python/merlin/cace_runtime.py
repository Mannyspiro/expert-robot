"""Fail-closed environment composition for the external CACE verifier."""
from __future__ import annotations

from typing import Any

from .cace_adapter import CaceVerificationAdapter
from .cace_attestation import trusted_cace_verifier_keys_from_environment
from .cace_http_transport import cace_transport_from_environment
from .event_outbox import MerlinEventOutbox
from .knowledge_graph import MerlinKnowledgeGraph
from .project_registry import MerlinRegistry


def cace_verification_adapter_from_environment(
    *,
    registry: MerlinRegistry,
    outbox: MerlinEventOutbox,
    graph: MerlinKnowledgeGraph | None = None,
    opener: Any | None = None,
) -> CaceVerificationAdapter | None:
    """Build the real HTTPS CACE adapter only when endpoint, token and signer pins exist.

    No local verifier or test double is substituted. Completely absent configuration
    returns None so capability state can remain unavailable. Partial configuration
    fails at startup rather than silently downgrading to unsigned verification.
    """
    transport = cace_transport_from_environment(opener=opener)
    trusted_keys = trusted_cace_verifier_keys_from_environment()
    if transport is None and not trusted_keys:
        return None
    if transport is None:
        raise ValueError("CACE verifier trust keys are configured but CACE transport is absent")
    if not trusted_keys:
        raise ValueError("CACE transport is configured but no trusted verifier keys are pinned")
    return CaceVerificationAdapter(
        verify_transport=transport,
        registry=registry,
        outbox=outbox,
        graph=graph,
        trusted_verifier_keys=trusted_keys,
    )


__all__ = ["cace_verification_adapter_from_environment"]
