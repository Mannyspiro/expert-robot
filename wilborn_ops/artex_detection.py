"""Independent, narrow passive interpretation of public ARTEX detection leads.

Only trusted synthetic sensor fixtures are supported. No upstream executable,
Sigma runtime, log scraping, host discovery, network or subprocess access.
"""
from dataclasses import dataclass
from .security_monitor import SecurityEvent, SecurityMonitor

SOURCE_REVISION="133f3cf97f2d153227a1a95d3c4b7cd5b72020a6"
CHANNELS=frozenset({"runtime_audit","file_created","outbound_user_agent","inbound_user_agent"})
MAX_FIELD=1024

@dataclass(frozen=True,slots=True)
class ArtexObservation:
    channel: str
    value: str
    environment: str="demo"
    data_class: str="synthetic"

    def __post_init__(self):
        if (type(self.environment) is not str or type(self.data_class) is not str
                or self.environment!="demo" or self.data_class!="synthetic"):
            raise PermissionError("only synthetic observations accepted")
        if type(self.channel) is not str or self.channel not in CHANNELS:
            raise ValueError("unsupported observation channel")
        if type(self.value) is not str or len(self.value)>MAX_FIELD or "\x00" in self.value:
            raise ValueError("invalid bounded observation")

def classify(observation):
    """Return a typed lead, never the observed field, not proof of compromise."""
    if type(observation) is not ArtexObservation:
        raise TypeError("typed synthetic observation required")
    observation.__post_init__()
    channel,value=observation.channel,observation.value
    kind=None
    if channel=="runtime_audit" and value.startswith("【ARTEX 平台管控·非目标防御】"):
        kind="artex_guard_marker"
    elif channel=="file_created":
        # Narrower than the upstream contains-all rule: require exact suffix.
        parts=value.replace("\\","/").split("/")
        if parts[-2:]==["_ca","mitmproxy-ca-cert.pem"]:
            kind="artex_recording_ca"
    elif channel=="outbound_user_agent" and value=="artex-selfupdate":
        kind="artex_update_indicator"
    elif channel=="inbound_user_agent" and value=="artex-enrich/1.0":
        kind="artex_inbound_indicator"
    return None if kind is None else SecurityEvent(kind,"demo","synthetic")

def observe_lead(monitor,observation):
    if type(monitor) is not SecurityMonitor:
        raise TypeError("trusted host monitor required")
    event=classify(observation)
    if event is None:
        return None
    result=monitor.observe(event)
    return {**result,"source_revision":SOURCE_REVISION,
            "evidence_class":"experimental_detection_lead",
            "framework_execution_verified":False}
