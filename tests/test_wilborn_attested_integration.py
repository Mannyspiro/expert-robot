import base64
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV
from python.merlin.project_registry import MerlinRegistry
from test_cace_attestation import make_attestation
from wilborn_ops.attestation_boundary import digest
from wilborn_ops.attested_research import (
    ResearchReviewGate,receipt_bindings,source_bindings,candidate_bindings,
    RETRIEVAL_CLAIM,SOURCE_CLAIM,ASSUMPTION_CLAIM)
from wilborn_ops.research_retrieval import FetchReceipt
from wilborn_ops.titan_envelope import seal_demo,open_demo
from wilborn_ops.artex_adapter import SignedArtexAdapter,verdict_bindings,CLAIM
from wilborn_ops.llm_boundary import BusinessToolDispatcher,ToolCall,SecurityUnavailable
from wilborn_ops.gateway import Identity,BusinessGateway
from wilborn_ops.store import CaseStore
from wilborn_ops.workflow import Case
from wilborn_ops.release_evidence import ReleaseEvidenceGate,REQUIRED_GATES

SCOPE="synthetic_fixture"

class Signer:
    """Ephemeral generated test identity, never a live trust root."""
    def __init__(self,name):
        self.name=name
        self.key=Ed25519PrivateKey.generate()
        _,kid,pem=make_attestation(self.key,claim_id="fixture",bundle_sha256="a"*64,bindings={},verifier_id=name)
        self.trust={kid:{"verifier_id":name,"public_key_pem":pem}}

    def sign(self,claim,bundle,bindings,purpose="independent-reproduction",age=0):
        created=(datetime.now(timezone.utc)-timedelta(seconds=age)).strftime("%Y-%m-%dT%H:%M:%SZ")
        envelope,_,_=make_attestation(self.key,claim_id=claim,bundle_sha256=bundle,
            bindings=bindings,verifier_id=self.name,purpose=purpose,created_at_utc=created)
        return envelope

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry=MerlinRegistry(Path(self.temp.name)/"registry")
        self.registry.register_project("wilborn-demo","Synthetic demo")
        self.provider=Signer("fixture-provider")
        self.reviewer=Signer("fixture-reviewer")
        self.gate=ResearchReviewGate(self.registry,project_id="wilborn-demo",
            scope=SCOPE,requester_id="fixture-worker",provider_keys=self.provider.trust,
            reviewer_keys=self.reviewer.trust)

    def put(self,path,body,media="text/plain",project="wilborn-demo"):
        self.registry.put_artifact(project,path,body,media)
        return self.registry.artifact_ref(project,path)

    def source(self,number,url,body):
        prefix="research/wilborn/"+SCOPE+"/"
        provider_ref=self.put(prefix+"provider/"+number,body)
        review_ref=self.put(prefix+"reviewer/"+number,body)
        receipt=FetchReceipt(url,url,200,"text/plain",body,0,True,True,True)
        b=receipt_bindings(receipt,provider_ref,SCOPE)
        signed=self.provider.sign(RETRIEVAL_CLAIM,provider_ref["sha256"],b,"artifact-integrity")
        review=self.reviewer.sign(SOURCE_CLAIM,provider_ref["sha256"],
            source_bindings(b,review_ref,signed["statement_sha256"]))
        return {"receipt":receipt,"provider_ref":provider_ref,"review_ref":review_ref,
                "provider_attestation":signed,"review_attestation":review}

    def sources(self):
        return [self.source("one","https://www.sba.gov/",b"Fictional dataset A, not market data."),
                self.source("two","https://www.census.gov/",b"Fictional dataset B, not market data.")]

    def candidate(self,name,counts,sources):
        scenario=lambda n:dict(monthly_customers=n,price="100",variable_cost="25",fixed_cost="800")
        candidate={"name":name,"evidence_hashes":[x["provider_ref"]["sha256"] for x in sources],
                   "assumptions":dict(zip(("pessimistic","baseline","optimistic"),map(scenario,counts)))}
        b=candidate_bindings(candidate,[x["review_attestation"]["statement_sha256"] for x in sources],SCOPE)
        return {"candidate":candidate,"review_attestation":self.reviewer.sign(ASSUMPTION_CLAIM,digest(candidate),b)}

    def test_signed_sources_and_hypothetical_ranking(self):
        sources=self.sources()
        a=self.candidate("Fictional A",(5,20,30),sources)
        b=self.candidate("Fictional B",(10,15,20),sources)
        result=self.gate.rank([a,b],sources)
        self.assertEqual([x["name"] for x in result["ranked"]],["Fictional B","Fictional A"])
        self.assertEqual(result["scope"],SCOPE)
        self.assertEqual(result["claims_verified"],0)
        self.assertFalse(result["verified_real"])
        self.assertFalse(result["execution_authorized"])
        item=result["ranked"][0]
        self.assertTrue(item["source_attestations_verified"])
        self.assertTrue(item["assumption_review_attested"])
        self.assertFalse(item["evidence_verified"])
        self.assertFalse(item["market_truth_verified"])

    def test_reject_modified_source_receipt_and_reference(self):
        source=self.sources()[0]
        for record in (dict(source,receipt=replace(source["receipt"],body=b"tampered")),
                       dict(source,review_ref=source["provider_ref"]),
                       dict(source,receipt=replace(source["receipt"],final_url="https://www.nist.gov/",requested_url="https://www.nist.gov/"))):
            with self.subTest(record_type="mutated"):
                with self.assertRaises((ValueError,PermissionError)):
                    self.gate.verify_source(record)

    def test_reject_unauthenticated_and_stale_provider(self):
        source=self.sources()[0]
        bindings=receipt_bindings(source["receipt"],source["provider_ref"],SCOPE)
        for signer,age in ((Signer("untrusted"),0),(self.provider,7200),(self.provider,-60)):
            changed=dict(source,provider_attestation=signer.sign(RETRIEVAL_CLAIM,
                source["provider_ref"]["sha256"],bindings,"artifact-integrity",age))
            with self.assertRaises((ValueError,PermissionError)):
                self.gate.verify_source(changed)

    def test_separate_keys_identities_and_scope(self):
        for keys in (self.provider.trust,Signer(self.provider.name).trust):
            with self.assertRaises(PermissionError):
                ResearchReviewGate(self.registry,project_id="wilborn-demo",scope=SCOPE,
                    requester_id="fixture-worker",provider_keys=self.provider.trust,reviewer_keys=keys)
        wrong_scope=ResearchReviewGate(self.registry,project_id="wilborn-demo",scope="public_research",
            requester_id="fixture-worker",provider_keys=self.provider.trust,reviewer_keys=self.reviewer.trust)
        with self.assertRaises((ValueError,PermissionError)):
            wrong_scope.verify_source(self.sources()[0])

    def test_reject_unreviewed_or_changed_scenarios_and_single_host(self):
        sources=self.sources()
        reviewed=self.candidate("Fictional A",(5,20,30),sources)
        changed=deepcopy(reviewed)
        changed["candidate"]["assumptions"]["baseline"]["price"]="200"
        with self.assertRaises((ValueError,PermissionError)):
            self.gate.rank([changed],sources)
        with self.assertRaises((ValueError,PermissionError)):
            self.gate.rank([dict(reviewed,review_attestation={})],sources)
        one=self.candidate("Fictional A",(5,20,30),sources[:1])
        with self.assertRaisesRegex(ValueError,"distinct source hosts"):
            self.gate.rank([one],sources[:1])

    def test_titan_real_encryption_roundtrip_and_rejection(self):
        plain=b"Synthetic fixture only"
        ref=self.put("research/wilborn/synthetic_fixture/provider/envelope",plain)
        key=bytes(range(32)) # Public test bytes, never a deployment key.
        sealed=seal_demo(plain,artifact_ref=ref,key_id="fixture-key",master_key=key)
        self.assertEqual(open_demo(sealed,artifact_ref=ref,key_id="fixture-key",master_key=key),plain)
        self.assertNotEqual(sealed["ciphertext_b64"],base64.b64encode(plain).decode())
        second=seal_demo(plain,artifact_ref=ref,key_id="fixture-key",master_key=key)
        self.assertNotEqual(sealed["nonce_b64"],second["nonce_b64"])
        for field in ("nonce_b64","ciphertext_b64","tag_b64"):
            changed=deepcopy(sealed)
            data=bytearray(base64.b64decode(changed[field])); data[0]^=1
            changed[field]=base64.b64encode(data).decode()
            with self.assertRaises(PermissionError):
                open_demo(changed,artifact_ref=ref,key_id="fixture-key",master_key=key)
        with self.assertRaises(PermissionError):
            open_demo(sealed,artifact_ref=ref,key_id="fixture-key",master_key=b"x"*32)
        with self.assertRaises(PermissionError):
            open_demo(sealed,artifact_ref=ref,key_id="other-key",master_key=key)
        altered=deepcopy(sealed);altered["context"]["purpose"]="other"
        with self.assertRaises(PermissionError):
            open_demo(altered,artifact_ref=ref,key_id="fixture-key",master_key=key)
        with self.assertRaises(PermissionError):
            seal_demo(plain,artifact_ref=dict(ref,project_id="wilborn-production"),key_id="fixture-key",master_key=key)

    def test_titan_primitive_rfc8452_c2_vectors(self):
        # RFC 8452 appendix C.2: independent published AES-256-GCM-SIV vectors.
        aes=AESGCMSIV(b"\x01"+b"\x00"*31)
        nonce=b"\x03"+b"\x00"*11
        for plain,expected in ((b"","07f5f4169bbf55a8400cd47ea6fd400f"),
            (b"\x01"+b"\x00"*7,"c2ef328e5c71c83b843122130f7364b761e0b97427e3df28")):
            self.assertEqual(aes.encrypt(nonce,plain,b"").hex(),expected)
            self.assertEqual(aes.decrypt(nonce,bytes.fromhex(expected),b""),plain)

    def test_signed_artex_seam_and_backend_authorization(self):
        signer=Signer("fixture-framework")
        policy="d"*64
        calls=[]
        def provider(request):
            self.assertNotIn("subject",request)
            self.assertNotIn("case_id",request["arguments"])
            calls.append(request)
            binding=verdict_bindings(request,"allow","fixture-v1",policy)
            return {"decision":"allow","attestation":signer.sign(CLAIM,digest(request),binding,"artifact-integrity")}
        adapter=SignedArtexAdapter(provider,version="fixture-v1",policy_sha256=policy,
                                  trust=signer.trust,requester_id="fixture-worker")
        store=CaseStore(Path(self.temp.name)/"demo.db")
        self.addCleanup(store.close)
        case=Case.open("general"); store.save(case)
        dispatcher=BusinessToolDispatcher(BusinessGateway(store),adapter)
        identity=Identity("fixture-staff","wilborn-demo",frozenset({"cases:read"}))
        result=dispatcher.dispatch(identity,ToolCall("get_case_status",{"case_id":case.id}))
        self.assertEqual(result["data_class"],"synthetic")
        with self.assertRaises(PermissionError):
            dispatcher.dispatch(identity,ToolCall("service_metrics",{}))
        with self.assertRaises(PermissionError):
            dispatcher.dispatch(identity,ToolCall("run_shell",{}))
        previous=provider(calls[0])
        replayed=SignedArtexAdapter(lambda request:previous,version="fixture-v1",
            policy_sha256=policy,trust=signer.trust,requester_id="fixture-worker")
        with self.assertRaises(SecurityUnavailable):
            BusinessToolDispatcher(BusinessGateway(store),replayed).dispatch(identity,ToolCall("list_cases",{}))

    def test_release_gate_remains_non_authorizing(self):
        self.registry.register_project("wilborn-production","Synthetic release gate fixture")
        ref=self.put("releases/fixture",b"Synthetic release fixture",project="wilborn-production")
        gate=ReleaseEvidenceGate(self.registry,trusted_by_gate={"native_build":self.reviewer.trust},
                                requester_id="fixture-worker")
        source_commit="a"*40
        b={"schema":"wilborn-release-evidence/1","scope":"production","source_commit":source_commit,
           "release_ref":ref,"gate":"native_build","outcome":"pass","deployment_authorized":False}
        att=self.reviewer.sign("wilborn:release:native_build",ref["sha256"],b)
        report=gate.report(source_commit=source_commit,release_ref=ref,attestations={"native_build":att})
        self.assertEqual(report["signed_gate_statements"],["native_build"])
        self.assertEqual(len(report["blocked_gates"]),len(REQUIRED_GATES)-1)
        self.assertFalse(report["evidence_complete"])
        self.assertFalse(report["production_qualified"])
        self.assertFalse(report["deployment_authorized"])
        with self.assertRaises((ValueError,PermissionError)):
            gate.report(source_commit="b"*40,release_ref=ref,attestations={"native_build":att})
        with self.assertRaises(PermissionError):
            gate.report(source_commit=source_commit,release_ref=dict(ref,project_id="wilborn-demo"),attestations={})

if __name__=="__main__":
    unittest.main()
