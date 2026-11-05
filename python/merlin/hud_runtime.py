"""Composition root for mounting the read-only Merlin HUD into a WSGI runtime.

The caller supplies the same canonical stores used by project/research services.
This module creates no shadow databases or external execution jobs. Its optional
background pump only projects and acknowledges local telemetry outbox records.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Thread
from typing import Any, Callable

from merlin.hud_activity import HudActivityProjector, HudOutboxConsumer
from merlin.hud_http import HudActivityWSGI
from merlin.registry_queries import MerlinReadAPI


HUD_PATHS = frozenset({
    "/api/hud/activity", "/api/hud/graph", "/api/hud/node",
})


class HudEventPump:
    """Background outbox consumer; HTTP GET routes never acknowledge events."""

    def __init__(self, consumer: HudOutboxConsumer, *, interval_seconds: float = 0.5):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.consumer = consumer
        self.interval_seconds = interval_seconds
        self._stop = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, name="merlin-hud-outbox", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                drained = False
                for _ in range(50):
                    if self.consumer.drain_one() is None:
                        break
                    drained = True
                if not drained:
                    self._stop.wait(self.interval_seconds)
            except Exception:
                self._stop.wait(self.interval_seconds)

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)


@dataclass
class HudRuntime:
    read_api: MerlinReadAPI
    projector: HudActivityProjector
    consumer: HudOutboxConsumer | None
    application: HudActivityWSGI
    event_pump: HudEventPump | None = None

    def start(self) -> None:
        if self.event_pump is not None:
            self.event_pump.start()

    def stop(self) -> None:
        if self.event_pump is not None:
            self.event_pump.stop()


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
    pump = HudEventPump(consumer) if consumer is not None else None
    return HudRuntime(read_api, projector, consumer, application, pump)


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


__all__ = ["HudRuntime", "HudEventPump", "build_hud_runtime", "mount_hud_runtime", "HUD_PATHS"]
