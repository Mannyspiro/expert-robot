"""Typed, conservative MCFC virtual-fabric contracts."""
from __future__ import annotations
import hashlib, json, time, uuid
from dataclasses import asdict, dataclass
from typing import Any, Mapping

@dataclass(frozen=True)
class ResourceVector:
    cpu_millis:int=0
    memory_mb:int=0
    gpu_units:int=0
    def __post_init__(self):
        if min(self.cpu_millis,self.memory_mb,self.gpu_units)<0: raise ValueError("resource values cannot be negative")
    def fits(self,o): return self.cpu_millis>=o.cpu_millis and self.memory_mb>=o.memory_mb and self.gpu_units>=o.gpu_units
    def __add__(self,o): return ResourceVector(self.cpu_millis+o.cpu_millis,self.memory_mb+o.memory_mb,self.gpu_units+o.gpu_units)
    def __sub__(self,o):
        if not self.fits(o): raise ValueError("resource underflow")
        return ResourceVector(self.cpu_millis-o.cpu_millis,self.memory_mb-o.memory_mb,self.gpu_units-o.gpu_units)

@dataclass(frozen=True)
class ComputeResource:
    resource_id:str
    capacity:ResourceVector
    labels:tuple[str,...]=()
    online:bool=True

@dataclass(frozen=True)
class Workload:
    workload_id:str
    kind:str
    requested:ResourceVector
    required_labels:tuple[str,...]=()
    priority:int=0
    max_runtime_seconds:float=300.0
    artifact_sha256:str|None=None
    def __post_init__(self):
        if not self.workload_id or not self.kind: raise ValueError("workload_id and kind are required")
        if self.priority<0 or self.max_runtime_seconds<=0: raise ValueError("priority must be nonnegative and runtime positive")
        if self.artifact_sha256 is not None and (len(self.artifact_sha256)!=64 or any(c not in "0123456789abcdef" for c in self.artifact_sha256)): raise ValueError("artifact_sha256 must be lowercase SHA-256")

@dataclass(frozen=True)
class ExecutionLease:
    lease_id:str
    workload_id:str
    resource_id:str
    granted:ResourceVector
    issued_monotonic:float
    expires_monotonic:float
    idempotency_key:str

@dataclass(frozen=True)
class FabricEvent:
    schema:str
    event_id:str
    event_type:str
    at_monotonic:float
    workload_id:str|None
    resource_id:str|None
    details:Mapping[str,Any]
    authority_expanded:bool=False

class VirtualFabric:
    """In-memory ledger and lease scheduler; deliberately does not execute jobs."""
    def __init__(self,resources:tuple[ComputeResource,...],*,budget:ResourceVector,clock=time.monotonic):
        ids=[r.resource_id for r in resources]
        if len(ids)!=len(set(ids)): raise ValueError("resource IDs must be unique")
        self.resources={r.resource_id:r for r in resources}; self.budget=budget; self.clock=clock
        self._used={r.resource_id:ResourceVector() for r in resources}; self._leases={}; self._idempotency={}; self.events=[]
    def _emit(self,typ,wid=None,rid=None,**details):
        self.events.append(FabricEvent("mcfc-fabric-event/1",str(uuid.uuid4()),typ,self.clock(),wid,rid,details,False))
    def _reap_expired(self):
        now=self.clock()
        for lid,l in list(self._leases.items()):
            if l.expires_monotonic<=now:
                self._used[l.resource_id]=self._used[l.resource_id]-l.granted; del self._leases[lid]
                self._emit("lease_expired",l.workload_id,l.resource_id,lease_id=lid)
    def schedule(self,workload:Workload,*,idempotency_key:str):
        if not idempotency_key.strip(): raise ValueError("idempotency key required")
        self._reap_expired(); prior_id=self._idempotency.get(idempotency_key)
        if prior_id:
            prior=self._leases.get(prior_id)
            if prior and prior.expires_monotonic>self.clock():
                if prior.workload_id!=workload.workload_id: raise ValueError("idempotency key reused for another workload")
                return prior
        used=ResourceVector()
        for v in self._used.values(): used=used+v
        if not self.budget.fits(used+workload.requested):
            self._emit("schedule_denied_budget",workload.workload_id,requested=asdict(workload.requested)); return None
        choices=[]
        for r in self.resources.values():
            if not r.online or not set(workload.required_labels).issubset(r.labels): continue
            avail=r.capacity-self._used[r.resource_id]
            if avail.fits(workload.requested): choices.append((avail.cpu_millis-workload.requested.cpu_millis,r.resource_id))
        if not choices:
            self._emit("schedule_denied_capacity",workload.workload_id,requested=asdict(workload.requested)); return None
        _,rid=min(choices); now=self.clock()
        lease=ExecutionLease(str(uuid.uuid4()),workload.workload_id,rid,workload.requested,now,now+workload.max_runtime_seconds,idempotency_key)
        self._used[rid]=self._used[rid]+workload.requested; self._leases[lease.lease_id]=lease; self._idempotency[idempotency_key]=lease.lease_id
        self._emit("lease_granted",workload.workload_id,rid,lease_id=lease.lease_id,granted=asdict(lease.granted)); return lease
    def release(self,lease_id:str,*,outcome="completed"):
        l=self._leases.pop(lease_id,None)
        if l is None:return False
        self._used[l.resource_id]=self._used[l.resource_id]-l.granted
        self._emit("lease_released",l.workload_id,l.resource_id,lease_id=lease_id,outcome=outcome); return True
    def snapshot(self):
        self._reap_expired()
        return {"schema":"mcfc-virtual-fabric/1","budget":asdict(self.budget),"resources":[{"resource_id":r.resource_id,"capacity":asdict(r.capacity),"used":asdict(self._used[r.resource_id]),"online":r.online,"labels":list(r.labels)} for r in sorted(self.resources.values(),key=lambda x:x.resource_id)],"active_leases":len(self._leases),"authority_expanded":False}

def event_stream_sha256(events:list[FabricEvent])->str:
    raw=json.dumps([asdict(e) for e in events],sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()
