"""Run the preregistered HTTP checks using the host's public ASGI builder."""
import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--checkout", type=Path, required=True)
args = parser.parse_args()
sys.path[:0] = [str(args.checkout / "python"), str(args.checkout / "scripts/merlin")]
from starlette.testclient import TestClient
from ask_receipt import ReceiptConversation
from dot_ai_os.bridge import DotContextBridge
from dot_ai_os.http_gateway import GatewayConfig, ReadOnlyMerlinRegistry, SubjectReadScope, build_http_gateway
from merlin.project_registry import MerlinRegistry

protocol = Path(__file__).with_name("daily-holdout.json").read_bytes()
assert hashlib.sha256(protocol).hexdigest() == "5493eaaeef5e9f861c68bcdb7fe4a37c42e667f31a1ecc7e41ebe5b160a7d68d"
names = ("violet", "amber")
config = GatewayConfig(issuer_url="https://issuer.example.test",
    introspection_url="https://issuer.example.test/introspect", resource_url="https://resource.example.test/mcp",
    allowed_subjects=names, port=8766)
tokens = dict(zip(("synthetic-v","synthetic-a"),names))
enabled = set(names)
lookups = []
scopes, writers, catalogue, refs, cases = {}, {}, {}, {}, []

async def introspect(token):
    subject = tokens.get(token)
    lookups.append(subject)
    if subject not in enabled:
        return {"active":False}
    return {"active":True,"iss":config.issuer_url,"aud":config.resource_url,
            "sub":subject,"client_id":"synthetic-app","exp":time.time()+60,"scope":"merlin:context:read"}

def install(who, version, value):
    body = json.dumps({"run_id":"8091","tests":{"tests":value}}).encode()
    pin = writers[who].ingest(namespace="merlin",source_id="single-run",
        source_version=str(version),title="Synthetic research review fixture",
        source_url="https://example.test/receipt",epistemic="historical_report",
        captured_at="2026-11-18T12:00:00Z",content=body)["source_ref"]
    assert pin["version"] == version and pin["sha256"] == hashlib.sha256(body).hexdigest()
    refs[who,version] = pin
    catalogue[who] = {"8091":{version:pin}}

start = time.perf_counter()
with tempfile.TemporaryDirectory() as directory:
    for who, count in zip(names,(43,68)):
        root = Path(directory)/who
        writer = DotContextBridge(MerlinRegistry(root))
        writer.initialize()
        writers[who] = writer
        install(who,1,count)
        # The operator refreshes this pointer. It is never derived from tool input.
        scopes[who] = SubjectReadScope(DotContextBridge(ReadOnlyMerlinRegistry(root)),
                        lambda reader, name=who: ReceiptConversation(reader,catalogue[name]))
    app = build_http_gateway(root=root,namespaces=("merlin",),config=config,introspect=introspect,
                             subject_scopes=scopes).streamable_http_app()
    with TestClient(app,base_url="http://127.0.0.1:8766") as client:
        for idx, (token, code, status, value, version) in enumerate([
            ("synthetic-v",200,"supported",43,1),("synthetic-a",200,"supported",68,1),
            ("synthetic-v",401,None,None,None),("synthetic-a",200,"supported",68,1),
            ("synthetic-v",200,"supported",52,2),("synthetic-a",200,"supported",68,1),
            ("synthetic-v",200,"abstain",None,None),("synthetic-a",200,"supported",68,1)],1):
            if idx == 3:
                enabled.remove("violet")
            if idx == 5:
                install("violet",2,52)
                enabled.add("violet")
            if idx == 7:
                catalogue["violet"] = {}
            response = client.post("/mcp", headers={"Authorization":"Bearer "+token,
                "Accept":"application/json, text/event-stream","MCP-Protocol-Version":"2025-06-18"},
                json={"jsonrpc":"2.0","id":idx,"method":"tools/call","params":{"name":"receipt_dialogue",
                      "arguments":{"turns":["For run 8091, how many main shard tests ran?"]}}})
            content = response.json()
            outer = content.get("result",{})
            actual = outer.get("structuredContent",{})
            expected_pin = refs.get((tokens[token], version))
            citation = actual.get("citation")
            pin_ok = citation == ({"source_ref":expected_pin,"pointer":"/tests/tests"} if version is not None else None)
            passed = (response.status_code == code and actual.get("disposition") == status
                      and type(actual.get("value")) is type(value) and actual.get("value")==value and pin_ok
                      and ("result" not in content if code==401 else outer.get("isError") is False))
            cases.append({"id":f"H{idx}","http_status":response.status_code,"disposition":actual.get("disposition"),
                          "value":actual.get("value"),"citation_check":pin_ok,"passed":passed})
report = dict(protocol_sha256=hashlib.sha256(protocol).hexdigest(),
              summary=dict(checks=len(cases),passed=sum(c["passed"] for c in cases),
                           supported=sum(c["disposition"]=="supported" for c in cases),
                           abstained=sum(c["disposition"]=="abstain" for c in cases),
                           denied=sum(c["http_status"]==401 for c in cases),introspections=len(lookups)),
              cases=cases,wall_seconds=round(time.perf_counter()-start,4),
              limits="Trusted host callback swaps immutable pins, simulated introspection, same in-process ASGI client, no live issuer/catalogue reload daemon.")
print(json.dumps(report,indent=2))
sys.exit(0 if all(c["passed"] for c in cases) else 1)
