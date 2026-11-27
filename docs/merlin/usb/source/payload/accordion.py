"""Seekable 3D tensor storage with independently checked bricks and a bounded decoded cache."""
import argparse
from collections import OrderedDict
import ctypes as C
import hashlib
from itertools import product
import json
import math
import os
from pathlib import Path
import tempfile
from time import perf_counter
import zlib

import numpy as np

MAGIC=b"MACC1\n"


class Codec:
    def __init__(self,name):
        self.name=name
        if name=="zstd":
            lib=C.CDLL("libzstd.so.1")
            size=C.c_size_t
            for key,args,result in (
                ("ZSTD_compressBound",[size],size),
                ("ZSTD_compress",[C.c_void_p,size,C.c_void_p,size,C.c_int],size),
                ("ZSTD_decompress",[C.c_void_p,size,C.c_void_p,size],size),
                ("ZSTD_isError",[size],C.c_uint),
            ):
                fn=getattr(lib,key); fn.argtypes=args; fn.restype=result
            self.lib=lib
        elif name not in ("raw","deflate"):
            raise ValueError("Unsupported archive codec")

    def encode(self,data):
        if self.name=="raw": return data
        if self.name=="deflate": return zlib.compress(data,1)
        out=C.create_string_buffer(self.lib.ZSTD_compressBound(len(data)))
        n=self.lib.ZSTD_compress(out,len(out),data,len(data),1)
        if self.lib.ZSTD_isError(n): raise ValueError("Zstandard encoding failed")
        return out.raw[:n]

    def decode(self,data,length):
        if self.name=="raw": return data
        if self.name=="deflate":
            d=zlib.decompressobj()
            restored=d.decompress(data,length+1)
            if len(restored)!=length or not d.eof or d.unused_data:
                raise ValueError("Invalid deflate block")
            return restored
        out=C.create_string_buffer(length)
        n=self.lib.ZSTD_decompress(out,length,data,len(data))
        if n!=length or self.lib.ZSTD_isError(n): raise ValueError("Invalid Zstandard block")
        return out.raw


def morton(p):
    code=0
    for bit in range(max(p).bit_length()):
        for axis,value in enumerate(p):
            code|=((value>>bit)&1)<<(3*bit+axis)
    return code


def save(path,data,shape,codec_name,order):
    data=np.asarray(data,dtype="<f4",order="C")
    if data.ndim!=3 or any(v<=0 for v in (*data.shape,*shape)):
        raise ValueError("Expected a nonempty 3D array and positive chunk edges")
    if order not in ("linear","morton"):
        raise ValueError("Unknown block order")
    codec=Codec(codec_name)
    table={}
    with path.open("wb") as out:
        out.write(MAGIC)
        coords=product(*(range(math.ceil(d/c)) for d,c in zip(data.shape,shape,strict=True)))
        if order=="morton": coords=sorted(coords,key=morton)
        for key in coords:
            slices=tuple(slice(i*c,(i+1)*c) for i,c in zip(key,shape,strict=True))
            raw=data[slices].tobytes()
            payload=codec.encode(raw)
            packed=len(payload)<len(raw)
            if not packed: payload=raw
            table[",".join(map(str,key))]=[out.tell(),len(payload),len(raw),packed,hashlib.blake2s(raw).hexdigest()]
            out.write(payload)
        header=json.dumps({"shape":data.shape,"brick":shape,"codec":codec_name,"order":order,"blocks":table},
                          separators=(",",":")).encode()
        out.write(header)
        out.write(len(header).to_bytes(8,"little"))


class Store:
    def __init__(self,path,cache_limit=256*1024):
        self.file=path.open("rb")
        try:
            limit=self.file.seek(0,2)
            self.file.seek(0); assert self.file.read(len(MAGIC))==MAGIC
            self.file.seek(-8,2)
            length=int.from_bytes(self.file.read(8),"little")
            if not 0<length<=min(64*1024**2,limit-8-len(MAGIC)): raise ValueError("Invalid index length")
            self.end=limit-8-length
            self.file.seek(self.end)
            h=json.loads(self.file.read(length))
            self.shape,self.brick=tuple(h["shape"]),tuple(h["brick"])
            if len(self.shape)!=3 or len(self.brick)!=3 or any(v<=0 for v in (*self.brick,*self.shape)):
                raise ValueError("Invalid shape")
            self.blocks=h["blocks"];self.codec=Codec(h["codec"])
        except BaseException:
            self.file.close()
            raise
        self.cache=OrderedDict();self.cache_limit=cache_limit;self.cached=0
        self.payload_read=0;self.decoded=0;self.hits=0;self.misses=0

    def __enter__(self):
        return self

    def __exit__(self,*_):
        self.file.close()

    def block(self,indices):
        key=",".join(map(str,indices))
        if key in self.cache:
            self.cache.move_to_end(key);self.hits+=1
            return self.cache[key]
        size=tuple(min(c,n-i*c) for i,c,n in zip(indices,self.brick,self.shape,strict=True))
        offset,count,length,packed,check=self.blocks[key]
        if length!=4*math.prod(size) or not 0<count<=length or not len(MAGIC)<=offset<=self.end-count:
            raise ValueError("Invalid block entry")
        encoded=os.pread(self.file.fileno(),count,offset)
        if len(encoded)!=count: raise ValueError("Truncated block")
        raw=self.codec.decode(encoded,length) if packed else encoded
        if len(raw)!=length or hashlib.blake2s(raw).hexdigest()!=check:
            raise ValueError("Block checksum mismatch")
        self.payload_read+=count;self.decoded+=length;self.misses+=1
        array=np.frombuffer(raw,dtype="<f4").reshape(size)
        if length<=self.cache_limit:
            while self.cached+length>self.cache_limit:
                self.cached-=self.cache.popitem(last=False)[1].nbytes
            self.cache[key]=array;self.cached+=length
        return array

    def read(self,lower,upper):
        if len(lower)!=3 or len(upper)!=3 or any(not 0<=a<b<=d
            for a,b,d in zip(lower,upper,self.shape,strict=True)):
            raise ValueError("Query is outside the archive")
        out=np.empty(tuple(b-a for a,b in zip(lower,upper,strict=True)),dtype="<f4")
        index=product(*(range(a//k,(b-1)//k+1) for a,b,k in zip(lower,upper,self.brick,strict=True)))
        for tile in index:
            origin=[a*b for a,b in zip(tile,self.brick,strict=True)]
            brick=self.block(tile)
            left=[max(a,o) for a,o in zip(lower,origin,strict=True)]
            right=[min(b,o+s) for b,o,s in zip(upper,origin,brick.shape,strict=True)]
            def bounds(base):
                return tuple(slice(a-i,b-i) for a,b,i in zip(left,right,base,strict=True))
            out[bounds(lower)]=brick[bounds(origin)]
        return out


CONFIGS=(
    ("Linear raw",(1,1,256),"raw","linear"),
    ("Linear Zstd",(1,1,256),"zstd","linear"),
    ("8³ Zstd row-major",(8,8,8),"zstd","linear"),
    ("8³ Zstd Morton",(8,8,8),"zstd","morton"),
    ("8³ Deflate Morton",(8,8,8),"deflate","morton"),
    ("16³ Zstd Morton",(16,16,16),"zstd","morton"),
    ("Token-page Zstd",(1,8,256),"zstd","linear"),
    ("Token-page raw",(1,8,256),"raw","linear")
)


def example():
    from physics import frame_field
    return np.stack(frame_field("sink",24),axis=0).astype("<f4")


def query_cases(shape,seed,extents,n=80):
    rng=np.random.default_rng(seed)
    for i in range(n):
        lengths=tuple(min(a,b) for a,b in zip(extents[i%len(extents)],shape,strict=True))
        a=tuple(int(rng.integers(0,d-l+1)) for l,d in zip(lengths,shape,strict=True))
        yield a,tuple(i+j for i,j in zip(a,lengths,strict=True))


def study(data,profile,extents):
    queries=tuple(query_cases(data.shape,217,extents))
    rows=[]
    with tempfile.TemporaryDirectory() as scratch:
        target=Path(scratch)/"tensor.macc"
        for name,tile,codec,order in CONFIGS:
            save(target,data,tile,codec,order)
            repetitions=[]
            for _ in range(3):
                with Store(target) as reader:
                    timing=[]
                    for lower,upper in queries:
                        start=perf_counter()
                        actual=reader.read(lower,upper)
                        timing.append((perf_counter()-start)*1000)
                        expected=data[tuple(slice(a,b) for a,b in zip(lower,upper,strict=True))]
                        assert actual.tobytes()==expected.tobytes()
                    repetitions.append(float(np.percentile(timing,95)))
                    io=reader.payload_read; decoded=reader.decoded; misses=reader.misses
            rows.append({"design":name,"bytes":target.stat().st_size,
                         "payload_bytes_read":io,"decoded_bytes":decoded,
                         "p95_read_ms":float(np.median(repetitions)),"chunk_misses":misses,"exact":True})
    mins={k:min(x[k] for x in rows) for k in ("bytes","payload_bytes_read","p95_read_ms")}
    for row in rows:
        row["score"]=sum(row[k]/mins[k]*weight for k,weight in (
            ("bytes",.4),("payload_bytes_read",.35),("p95_read_ms",.25)))
    ranked=sorted(rows,key=lambda row:row["score"])
    return {"profile":profile,"shape":list(data.shape),"raw_bytes":data.nbytes,"queries":len(queries),
            "cache_bytes":256*1024,"ranking":"Lower is better. 40% archive bytes, 35% block payload read, 25% p95 latency, normalized to best per metric.","ranked":ranked}


def capture(portable,runtime):
    import sys
    sys.path.insert(0,str(portable/"simulator"))
    from full_sim import CellStore, fit_layouts, verified_model
    from replay import Decoder
    from usb import kernel_file
    model=verified_model(portable/"model/qwen2.5-0.5b-instruct-q4_0.gguf")
    library=kernel_file(runtime,"auto")
    engine=Decoder(CellStore(model,library,fit_layouts(portable/"simulator/Cell_Results.json")["tetrahedral"],"corrected"))
    engine.forward([785,6722,315,9625,374]*8)
    return np.stack([np.stack(layer,axis=0) for layer in engine.cache],axis=0).astype("<f4").reshape(engine.layers*2,40,-1)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report",required=True,type=Path)
    p.add_argument("--archive",required=True,type=Path)
    p.add_argument("--portable",type=Path)
    p.add_argument("--runtime",type=Path)
    args=p.parse_args()
    data=example()
    audits=[study(data,"3D heat history",[(2,6,6),(1,20,20),(5,5,5)])]
    if args.portable and args.runtime:
        audits.append(study(capture(args.portable,args.runtime),"Qwen 2.5 prefill K/V snapshot",
                            [(2,8,96),(1,1,256),(6,4,48)]))
    selected=audits[0]["ranked"][0]["design"]
    name,tile,codec,order=next(cfg for cfg in CONFIGS if cfg[0]==selected)
    save(args.archive,data,tile,codec,order)
    with Store(args.archive) as reader:
        assert reader.read((0,0,0),data.shape).tobytes()==data.tobytes()
    args.report.write_text(json.dumps({"study":audits,"persisted_design":selected},indent=2)+"\n")


if __name__=="__main__":
    main()
