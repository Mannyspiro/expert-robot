"""Trusted local adapter connecting existing typed producers to the signed ledger.

No signer generation, credentials, network API or raw event payloads.
"""
from .security_ledger import SecurityLedger
from .security_monitor import SecurityMonitor,SecurityEvent

class SignedSecurityMonitor:
    def __init__(self,ledger,signer):
        if type(ledger) is not SecurityLedger or not callable(signer):
            raise TypeError("host-configured ledger and local signer required")
        self._ledger=ledger
        self._signer=signer

    def observe(self,event):
        if type(event) is not SecurityEvent:
            raise TypeError("typed event required")
        return self._ledger.observe_local(event,self._signer)

    def summary(self):
        return self._ledger.report()

def require_monitor(monitor):
    if type(monitor) not in (SecurityMonitor,SignedSecurityMonitor):
        raise TypeError("trusted demo monitor required")
    return monitor
