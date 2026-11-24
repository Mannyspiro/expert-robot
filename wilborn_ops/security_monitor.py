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

def expire_windows(windows,now):
    for name,(_,_,seconds) in RULES.items():
        window=windows[name]
        while window and window[0]<=now-seconds:
            window.popleft()

def active_windows(windows):
    return sorted(name for name,(_,limit,_) in RULES.items()
                  if len(windows[name])>=limit)

def advance_windows(windows,kind,now):
    expire_windows(windows,now)
    previous=set(active_windows(windows))
    for name,(kinds,_,_) in RULES.items():
        if kind in kinds:
            windows[name].append(now)
    active=active_windows(windows)
    return sorted(set(active)-previous),active

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
        expire_windows(self._windows,now)

    def _active(self):
        return active_windows(self._windows)

    def observe(self,event):
        if type(event) is not SecurityEvent:
            raise TypeError("typed event required")
        # Validate again at the boundary; never retain the caller's object.
        event.__post_init__()
        with self._lock:
            now=self._now()
            triggered,active=advance_windows(self._windows,event.kind,now)
            self._counts[event.kind]=min(MAX_COUNTER,self._counts[event.kind]+1)
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
