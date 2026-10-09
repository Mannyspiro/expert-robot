#!/usr/bin/env python3
"""Bind an exact conservation receipt to externally pinned source-model bytes.

The certificate's self-declared hash cannot establish provenance. This
independent check requires an expected SHA-256 from outside the certificate.
Only research status is reported; it does not sign or promote a certificate.
"""
import argparse,hashlib,importlib.util,json
from fractions import Fraction as Q
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load_verifier():
    spec=importlib.util.spec_from_file_location(
        'independent_conservation_verifier',
        ROOT/'scripts/verify_cace_conservation_certificate.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def unique_pairs(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise ValueError('duplicate JSON key '+k)
        d[k]=v
    return d

def pinned_verify(receipt,source_bytes,pinned_source_sha256):
    if not isinstance(pinned_source_sha256,str) or len(pinned_source_sha256)!=64 or any(
        ch not in '0123456789abcdef' for ch in pinned_source_sha256):
        raise ValueError('expected pinned lowercase SHA-256')
    if not isinstance(source_bytes,bytes) or len(source_bytes)>200000:
        raise ValueError('unbounded source bytes')
    actual=hashlib.sha256(source_bytes).hexdigest()
    if actual!=pinned_source_sha256:
        raise ValueError('independently pinned source SHA mismatch')
    source=json.loads(source_bytes.decode('utf-8'),object_pairs_hook=unique_pairs)
    if not isinstance(source,dict) or set(source)!={'species','reactions','stoichiometry'}:
        raise ValueError('source schema')
    raw=source['stoichiometry']
    if not isinstance(raw,list) or any(not isinstance(row,list) for row in raw):
        raise ValueError('source matrix shape')
    # Allow syntactically different but mathematically equal exact inputs,
    # e.g. -2/2 and -1; preserve explicit external file-byte pin.
    normalized={
        'species':source['species'],
        'reactions':source['reactions'],
        'stoichiometry':[[str(Q(v)) for v in row] for row in raw],
    }
    if normalized!={k:receipt[k] for k in ('species','reactions','stoichiometry')}:
        raise ValueError('receipt is for a different source model')
    independent=load_verifier()
    result=independent.verify(receipt)
    result['externally_pinned_source_sha256']=actual
    result['external_source_bound']=True
    result['source_bytes_trusted_only_by_external_digest']=True
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('certificate',type=Path)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--expected-source-sha256',required=True)
    args=p.parse_args()
    receipt=json.loads(args.certificate.read_text(encoding='utf-8'),
                       object_pairs_hook=unique_pairs)
    print(json.dumps(pinned_verify(
        receipt,args.source.read_bytes(),args.expected_source_sha256)))
