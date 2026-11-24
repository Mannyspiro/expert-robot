"""Bounded passive security correlation for the synthetic business prototype.

Trusted host supplies typed events. No raw payloads, credentials, user identity,
live scanning, external calls, automatic response or authorization decisions.
"""
from collections import Counter, deque
from dataclasses import dataclass
from math import isfinite
from threading import Lock
from time import monotonic
from types import MappingProxyType

SEVERITY = MappingProxyType({
    "auth_failure": "medium",
    "tool_denied": "medium",
    "provenance_rejected": "high",
    "rate_limit": "medium",
    "integrity_failure": "high",
    "unexpected_tool": "high",
    "artex_guard_marker": "high",
    "artex_recording_ca": "medium",
    "artex_update_indicator": "medium",
    "artex_inbound_indicator": "high",
})
KINDS = frozenset(SEVERITY)
REVIEW_KINDS = frozenset(k for k,v in SEVERITY.items() if v=="high")
# Host-local synthetic defaults, not production policy. ARTEX guard window
# references the upstream experimental passive correlation rule in the docs.
RULES = MappingProxyType({
    "authentication_denial_burst": (frozenset({"auth_failure"}), 3, 60),
    "tool_policy_denial_burst": (frozenset({"tool_denied","unexpected_tool"}), 3, 60),
    "artex_guard_marker_burst": (frozenset({"artex_guard_marker"}), 5, 600),
})
MAX_COUNTER = (1 << 63) - 1

@dataclass(frozen=True,slots=True)
class SecurityEvent:
    kind: str
    environment: str
    data_class: str

    def __post_init__(self):
        if type(self.kind) is not str or self.kind not in KINDS:
            raise ValueError("unrecognized event")
        if (type(self.environment) is not str or type(self.data_class) is not str
                or self.environment!="demo" or self.data_class!="synthetic"):
            raise PermissionError("monitor is synthetic-demo only")

class SecurityMonitor:
    """One instance for one trusted demo service; not a cross-host collector."""
    def __init__(self,*,clock=monotonic):
        if not callable(clock):
            raise TypeError("host monotonic clock required")
        self._clock=clock
        self._last=None
        self._lock=Lock()
        self._counts=Counter()
        self._windows={name:deque(maxlen=limit) for name,(_,limit,_) in RULES.items()}

    def _now(self):
        value=self._clock()
        if type(value) not in (int,float) or not isfinite(value) or value<0:
            raise RuntimeError("invalid monotonic clock")
        if self._last is not None and value<self._last:
            raise RuntimeError("monotonic clock moved backward")
        self._last=value
        return value

    def _expire(self,now):
        for name,(_,_,seconds) in RULES.items():
            window=self._windows[name]
            while window and window[0]<=now-seconds:
                window.popleft()

    def _active(self):
        return sorted(name for name,(_,limit,_) in RULES.items()
                      if len(self._windows[name])>=limit)

    def observe(self,event):
        if type(event) is not SecurityEvent:
            raise TypeError("typed event required")
        # Validate again at the boundary; never retain the caller's object.
        event.__post_init__()
        with self._lock:
            now=self._now()
            self._expire(now)
            previous=set(self._active())
            self._counts[event.kind]=min(MAX_COUNTER,self._counts[event.kind]+1)
            for name,(kinds,_,_) in RULES.items():
                if event.kind in kinds:
                    self._windows[name].append(now)
            active=self._active()
            triggered=sorted(set(active)-previous)
            return {"kind":event.kind,"severity":SEVERITY[event.kind],
                    "data_class":"synthetic","environment":"demo",
                    "requires_review":event.kind in REVIEW_KINDS or bool(triggered),
                    "correlation_alerts":triggered,
                    "active_correlations":active,
                    "compromise_confirmed":False}

    def summary(self):
        with self._lock:
            self._expire(self._now())
            return {"environment":"demo","data_class":"synthetic",
                    "counts":dict(sorted(self._counts.items())),
                    "active_correlations":self._active(),
                    "compromise_confirmed":False,
                    "execution_authorized":False}
