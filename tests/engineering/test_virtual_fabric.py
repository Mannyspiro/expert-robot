from merlin.virtual_fabric import ComputeResource, ResourceVector, VirtualFabric, Workload, event_stream_sha256

def make(clock=lambda:100.0):
    return VirtualFabric((ComputeResource("cpu-a",ResourceVector(4000,8192),("cpu",)),ComputeResource("gpu-b",ResourceVector(8000,16384,1),("cpu","gpu"))),budget=ResourceVector(10000,20000,1),clock=clock)

def test_schedule_and_capacity():
    f=make(); l=f.schedule(Workload("j","lean",ResourceVector(2000,2048),("cpu",)),idempotency_key="k")
    assert l and l.resource_id=="cpu-a" and f.snapshot()["active_leases"]==1

def test_idempotency_prevents_double_reservation():
    f=make(); w=Workload("j","sim",ResourceVector(1000,512))
    assert f.schedule(w,idempotency_key="k")==f.schedule(w,idempotency_key="k")
    assert f.snapshot()["resources"][0]["used"]["cpu_millis"]==1000

def test_global_budget_denies():
    f=make(); assert f.schedule(Workload("big","render",ResourceVector(11000,1)),idempotency_key="b") is None
    assert f.snapshot()["active_leases"]==0

def test_release_restores_capacity():
    f=make(); l=f.schedule(Workload("j","proof",ResourceVector(1000,1000)),idempotency_key="r")
    assert l and f.release(l.lease_id) and not f.release(l.lease_id)

def test_expiry_reclaims_lease():
    t=[1.0]; f=make(clock=lambda:t[0]); l=f.schedule(Workload("j","render",ResourceVector(1000,1000),max_runtime_seconds=2),idempotency_key="e")
    t[0]=4.0; assert l and f.snapshot()["active_leases"]==0
    assert any(x.event_type=="lease_expired" for x in f.events)

def test_labels_constrain_resource_choice():
    f=make(); l=f.schedule(Workload("g","render",ResourceVector(1000,1000),("gpu",)),idempotency_key="g")
    assert l and l.resource_id=="gpu-b"

def test_event_digest_is_stable():
    f=make(); f.schedule(Workload("x","test",ResourceVector(1,1)),idempotency_key="x")
    assert len(event_stream_sha256(f.events))==64 and event_stream_sha256(f.events)==event_stream_sha256(f.events)
