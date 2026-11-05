"""Composition root for mounting the read-only Merlin HUD into a WSGI runtime.

The caller supplies the same canonical stores used by project/research services.
This module creates no shadow databases and starts no workers or external jobs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from merlin.hud_activity import HudActivityProjector, HudOutboxConsumer
from merlin.hud_http import HudActivityWSGI
from merlin.registry_queries import MerlinReadAPI


HUD_PATHS = frozenset({
    "/api/hud/activity", "/api/hud/graph", "/api/hud/node",
})


@dataclass(frozen=True)
class HudRuntime:
    read_api: MerlinReadAPI
    projector: HudActivityProjector
    consumer: HudOutboxConsumer | None
    application: HudActivityWSGI


def build_hud_runtime(*, registry: Any, hypotheses: Any = None,
                      graph: Any = None, outbox: Any = None,
                      max_events: int = 500,
                      max_drain_per_request: int = 100) -> HudRuntime:
    """Inject canonical stores into the HUD API and event projection.

    Pass the exact registry/ledger/graph/outbox instances already owned by the
    running Merlin process. No filesystem paths or replacement stores are
    guessed here. If graph is absent, graph endpoints remain explicitly
    unavailable (503); activity can still operate.
    """
    from merlin.project_registry import MerlinRegistry
    if not isinstance(registry, MerlinRegistry):
        raise ValueError("registry must be the canonical MerlinRegistry instance")
    read_api = MerlinReadAPI(
        registry, hypotheses=hypotheses, graph=graph, outbox=outbox
    )
    projector = HudActivityProjector(max_events=max_events)
    consumer = HudOutboxConsumer(outbox, projector) if outbox is not None else None
    application = HudActivityWSGI(
        projector, consumer, read_api=read_api,
        max_drain_per_request=max_drain_per_request,
    )
    return HudRuntime(read_api, projector, consumer, application)


def mount_hud_runtime(application: Callable[..., Any],
                      hud: HudRuntime) -> Callable[..., Any]:
    """Mount the HUD routes without replacing the host WSGI application.

    The host runtime remains responsible for authentication, authorization,
    loopback/network binding, and TLS. The HUD routes are read-only GETs.
    """
    if not callable(application):
        raise ValueError("application must be a WSGI callable")

    def mounted(environ: dict[str, Any], start_response: Callable[..., Any]):
        if environ.get("PATH_INFO") in HUD_PATHS:
            return hud.application(environ, start_response)
        return application(environ, start_response)

    return mounted


__all__ = ["HudRuntime", "build_hud_runtime", "mount_hud_runtime", "HUD_PATHS"]
