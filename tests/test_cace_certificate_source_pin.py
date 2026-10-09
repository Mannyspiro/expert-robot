#!/usr/bin/env python3
"""Trusted external source pin regression and source/receipt swap attacks."""
import copy,hashlib,importlib.util,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
producer=load('producer','scripts/generate_cace_conservation_certificate.py')
pin=load('pin','scripts/verify_cace_certificate_source_pin.py')

def raw(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':')).encode('utf-8')

def check(cert,source,expected=None):
    b=raw(source)
    sha=expected if expected is not None else hashlib.sha256(b).hexdigest()
    return pin.pinned_verify(cert,b,sha)

def reject(cert,source,expected,reason):
    try:
        pin.pinned_verify(cert,source,expected)
    except (ValueError,TypeError,KeyError,ZeroDivisionError,json.JSONDecodeError):
        return
    raise AssertionError('forgery accepted: '+reason)

def main():
    clean={'species':['A','B','C'],'reactions':['r0','r1'],
           'stoichiometry':[['-1','0'],['1','-1'],['0','1']]}
    receipt=producer.generate(clean)
    b=raw(clean); trusted=hashlib.sha256(b).hexdigest()
    assert check(receipt,clean)['external_source_bound'] is True
    # Receipt/biochemical model provenance is not established by self-hashing;
    # the trusted file digest is supplied by an independent controller.
    mutated=copy.deepcopy(clean)
    mutated['stoichiometry'][0][0]='-2'
    forged=producer.generate(mutated)
    swapped=raw(mutated)
    reject(forged,swapped,trusted,'forged source+receipt with old trusted pin')
    reject(receipt,swapped,trusted,'mutated source with old trusted pin')
    reject(forged,b,trusted,'forged receipt against true source')
    reject(receipt,b,'0'*64,'wrong trusted pin')
    reject(receipt,b,'z'*64,'bad hash encoding')
    reject(receipt,b[:4],trusted,'partial source')
    reject(receipt,b'{"species":[],"species":[]}',trusted,'duplicate source keys')
    # Duplicate-key check also applies with a matching byte digest.
    doubled=b'{"species":[],"species":[],"reactions":[],"stoichiometry":[]}'
    reject(receipt,doubled,hashlib.sha256(doubled).hexdigest(),'duplicate keys with matching pin')
    different=copy.deepcopy(clean);different['species'][0]='X'
    reject(receipt,raw(different),hashlib.sha256(raw(different)).hexdigest(),
           'swapped source identity with individually valid file hash')
    # Canonical rational equivalence is allowed, but the exact external input
    # bytes are still pinned to their own digest.
    equivalent=copy.deepcopy(clean);equivalent['stoichiometry'][0][0]='-2/2'
    assert check(receipt,equivalent)['external_source_bound'] is True
    assert trusted!=hashlib.sha256(raw(equivalent)).hexdigest()
    print(json.dumps({'bound_valid':2,'attacks_rejected':9,
                      'external_source_pin_required':True,
                      'formal_kernel_checked':False,
                      'cace_runtime_checked':False,
                      'production_promoted':False}))

if __name__=='__main__':main()
