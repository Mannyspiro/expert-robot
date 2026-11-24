"""Host-only authenticated retrieval and independent review contract.

A signature authenticates a trusted signer's statement, not market truth. No
network, secrets, business-storage access, or automatic promotion here.
"""
from copy import deepcopy
from urllib.parse import urlsplit
from python.merlin.artifact_ref import ArtifactRef
from .attestation_boundary import canonical,digest,fresh_attestation,separated_trust
from .research_retrieval import accept_receipt,FetchReceipt
from .research_ingest import MAX_BYTES
from .business_decision import rank_opportunities,implementation_plan

SCOPES={"synthetic_fixture","public_research"}
RETRIEVAL_CLAIM="wilborn:research:retrieval:v1"
SOURCE_CLAIM="wilborn:research:independent-source:v1"
ASSUMPTION_CLAIM="wilborn:research:assumption-review:v1"

def receipt_bindings(receipt,ref,scope):
    accepted=accept_receipt(receipt)
    parsed=ArtifactRef.from_mapping(ref)
    if scope not in SCOPES or parsed.sha256!=accepted["evidence"].sha256:
        raise ValueError("receipt/artifact mismatch")
    return {"schema":"wilborn-fetch-binding/1","scope":scope,
            "artifact_ref":parsed.to_dict(),"requested_url":receipt.requested_url,
            "final_url":receipt.final_url,"status":receipt.status,
            "content_type":receipt.content_type,"redirect_count":receipt.redirect_count,
            "egress_policy_verified":receipt.egress_policy_verified,
            "tls_verified":receipt.tls_verified,
            "access_policy_verified":receipt.access_policy_verified}

def source_bindings(retrieval,review_ref,provider_statement_sha256):
    return {"schema":"wilborn-source-review/1","scope":retrieval["scope"],
            "retrieval":retrieval,"review_artifact_ref":ArtifactRef.from_mapping(review_ref).to_dict(),
            "provider_statement_sha256":provider_statement_sha256,
            "method":"independent_exact_byte_retrieval"}

def candidate_bindings(candidate,source_reviews,scope):
    return {"schema":"wilborn-assumption-review/1","scope":scope,
            "candidate_sha256":digest(candidate),
            "source_review_statement_sha256":sorted(source_reviews),
            "method":"reviewed_scenario_assumptions",
            "execution_authorized":False}

class ResearchReviewGate:
    def __init__(self,registry,*,project_id,scope,requester_id,provider_keys,reviewer_keys):
        if scope not in SCOPES or not requester_id or not project_id:
            raise ValueError("explicit research scope and identity required")
        separated_trust(provider_keys,reviewer_keys)
        self._registry=registry
        self._project=project_id
        self._scope=scope
        self._requester=requester_id
        self._providers=deepcopy(provider_keys)
        self._reviewers=deepcopy(reviewer_keys)

    def _read(self,value,role,media_type):
        ref=ArtifactRef.from_mapping(value)
        prefix="research/wilborn/"+self._scope+"/"+role+"/"
        if ref.project_id!=self._project or not ref.logical_path.startswith(prefix):
            raise PermissionError("artifact outside scoped research registry")
        result=self._registry.read_artifact_ref(ref.to_dict(),max_bytes=MAX_BYTES)
        if result["resolution"]["media_type"]!=media_type:
            raise PermissionError("artifact media type mismatch")
        return ref,result["content"]

    def verify_source(self,record):
        if type(record) is not dict or set(record)!={"receipt","provider_ref","review_ref","provider_attestation","review_attestation"}:
            raise ValueError("exact signed source record required")
        receipt=record["receipt"]
        if type(receipt) is not FetchReceipt:
            raise TypeError("typed provider receipt required")
        bindings=receipt_bindings(receipt,record["provider_ref"],self._scope)
        provider_ref,body=self._read(record["provider_ref"],"provider",receipt.content_type)
        reviewer_ref,review_body=self._read(record["review_ref"],"reviewer",receipt.content_type)
        if body!=receipt.body or review_body!=body or provider_ref.sha256!=reviewer_ref.sha256:
            raise ValueError("independent source byte comparison failed")
        provider=fresh_attestation(record["provider_attestation"],trust=self._providers,
            claim_id=RETRIEVAL_CLAIM,bundle_sha256=provider_ref.sha256,bindings=bindings,
            requester_id=self._requester,purpose="artifact-integrity")
        review_binding=source_bindings(bindings,reviewer_ref.to_dict(),provider["statement_sha256"])
        reviewer=fresh_attestation(record["review_attestation"],trust=self._reviewers,
            claim_id=SOURCE_CLAIM,bundle_sha256=provider_ref.sha256,bindings=review_binding,
            requester_id=provider["verifier_id"],purpose="independent-reproduction")
        if reviewer["verifier_id"]==self._requester or reviewer["verifier_key_id"]==provider["verifier_key_id"]:
            raise PermissionError("reviewer not independent")
        if record["review_attestation"]["statement"]["created_at_utc"]<record["provider_attestation"]["statement"]["created_at_utc"]:
            raise PermissionError("review predates retrieval attestation")
        return {"sha256":provider_ref.sha256,"url":receipt.final_url,
                "provider_ref":provider_ref.to_dict(),"review_ref":reviewer_ref.to_dict(),
                "provider_statement_sha256":provider["statement_sha256"],
                "review_statement_sha256":reviewer["statement_sha256"],
                "review_created_at_utc":record["review_attestation"]["statement"]["created_at_utc"],
                "scope":self._scope,"source_attestations_verified":True,
                "claims_verified":0}

    def rank(self,reviewed_candidates,source_records):
        if type(source_records) is not list or not 1<=len(source_records)<=20:
            raise ValueError("bounded signed sources required")
        if type(reviewed_candidates) is not list or not 1<=len(reviewed_candidates)<=50:
            raise ValueError("bounded reviewed candidates required")
        sources={}
        for record in source_records:
            result=self.verify_source(record)
            if result["sha256"] in sources:
                raise ValueError("duplicate or ambiguous source hash")
            sources[result["sha256"]]=result
        candidates=[]
        evidence_by_name={}
        for entry in reviewed_candidates:
            if type(entry) is not dict or set(entry)!={"candidate","review_attestation"}:
                raise ValueError("exact reviewed candidate required")
            candidate=deepcopy(entry["candidate"])
            if type(candidate) is not dict or set(candidate)!={"name","evidence_hashes","assumptions"}:
                raise ValueError("exact candidate fields required")
            if len(canonical(candidate))>16384:
                raise ValueError("candidate exceeds limit")
            rank_opportunities([candidate])
            name=candidate["name"]
            hashes=candidate["evidence_hashes"]
            if name in evidence_by_name or len(hashes)!=len(set(hashes)) or not set(hashes)<=set(sources):
                raise ValueError("duplicate candidate or unresolved evidence")
            selected=[sources[h] for h in sorted(hashes)]
            if len({urlsplit(s["url"]).hostname for s in selected})<2:
                raise ValueError("at least two distinct source hosts required; not proof of independence")
            bindings=candidate_bindings(candidate,[s["review_statement_sha256"] for s in selected],self._scope)
            review=fresh_attestation(entry["review_attestation"],trust=self._reviewers,
                claim_id=ASSUMPTION_CLAIM,bundle_sha256=digest(candidate),bindings=bindings,
                requester_id=self._requester,purpose="independent-reproduction")
            if entry["review_attestation"]["statement"]["created_at_utc"]<max(s["review_created_at_utc"] for s in selected):
                raise PermissionError("assumption review predates source review")
            evidence_by_name[name]={"sources":selected,"assumption_review_sha256":review["statement_sha256"]}
            candidates.append(candidate)
        ranked=rank_opportunities(candidates)
        for item in ranked:
            item.update(evidence_by_name[item["name"]])
            item.update({"source_attestations_verified":True,"assumption_review_attested":True,
                         "ranking_basis":"independently_attested_hypothetical_assumptions",
                         "market_truth_verified":False})
        return {"schema":"wilborn-attested-ranking/1","scope":self._scope,
                "data_class":"hypothetical_scenario","verified_real":False,
                "claims_verified":0,"execution_authorized":False,
                "ranked":ranked,"plans":[implementation_plan(item) for item in ranked]}
