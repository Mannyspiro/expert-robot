"""Local inert inspection of the exact retained zvbi RPM; never run its payload.

The native probe supplies the signed RPM and trusted RPM header queries. This
bounded parser recovers only the unit text plus a complete payload identity list
for comparison with those native queries. It is not an installation tool.
"""
import argparse
import gzip
import hashlib
import io
import json
import lzma
from pathlib import Path, PurePosixPath
import stat
import struct

PACKAGE_SHA256='b2df1becc979d6b5faac7398808e262027aa64011704affa36ba3fac49398a29'
PACKAGE_BYTES=446528
MAX_PAYLOAD=8*1024*1024
UNIT='usr/lib/systemd/system/zvbid.service'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def header(raw,offset):
    if raw[offset:offset+8]!=b'\x8e\xad\xe8\x01\0\0\0\0':
        raise ValueError('RPM header magic/version')
    count,size=struct.unpack_from('>II',raw,offset+8)
    end=offset+16+count*16+size
    if count>4096 or size>2*1024*1024 or end>len(raw):
        raise ValueError('RPM header bounds')
    entries=[]
    for i in range(count):
        tag,kind,start,length=struct.unpack_from('>IIII',raw,offset+16+i*16)
        if start>size: raise ValueError('RPM index offset')
        entries.append({'tag':tag,'type':kind,'offset':start,'count':length})
    return end,entries,raw[offset+16+count*16:end]


def payload(raw):
    if len(raw)!=PACKAGE_BYTES or digest(raw)!=PACKAGE_SHA256:
        raise ValueError('exact observed signed RPM identity required')
    if raw[:6]!=b'\xed\xab\xee\xdb\x03\x00':
        raise ValueError('RPM v3 lead required')
    signature_end,_,_=header(raw,96)
    main_offset=(signature_end+7)//8*8
    if any(raw[signature_end:main_offset]): raise ValueError('signature padding')
    start,entries,store=header(raw,main_offset)
    compressors=[row for row in entries if row['tag']==1125]
    if len(compressors)!=1 or compressors[0]['type']!=6 or compressors[0]['count']!=1:
        raise ValueError('RPM payload compressor tag')
    compressor=store[compressors[0]['offset']:].split(b'\0',1)[0].decode('ascii')
    compressed=raw[start:]
    if compressor=='zstd':
        import zstandard
        frame=zstandard.get_frame_parameters(compressed)
        if frame.window_size>MAX_PAYLOAD or frame.dict_id:
            raise ValueError('bounded independent zstd frame required')
        with zstandard.ZstdDecompressor(max_window_size=MAX_PAYLOAD).stream_reader(io.BytesIO(compressed)) as stream:
            uncompressed=stream.read(MAX_PAYLOAD+1)
    elif compressor=='xz':
        decoder=lzma.LZMADecompressor(memlimit=64*1024*1024)
        uncompressed=decoder.decompress(compressed,max_length=MAX_PAYLOAD+1)
        if not decoder.eof or decoder.unused_data: raise ValueError('XZ payload framing')
    elif compressor=='gzip':
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            uncompressed=stream.read(MAX_PAYLOAD+1)
    else: raise ValueError('unreviewed RPM compressor')
    if len(uncompressed)>MAX_PAYLOAD: raise ValueError('decompressed payload ceiling')
    return uncompressed,{'main_header_offset':main_offset,'payload_offset':start,
        'compression':compressor,'compressed_bytes':len(compressed),
        'uncompressed_bytes':len(uncompressed),'cpio_sha256':digest(uncompressed)}


def members(raw):
    offset=0;result=[];names=set();unit=None
    while True:
        if offset+110>len(raw) or raw[offset:offset+6] not in (b'070701',b'070702'):
            raise ValueError('newc payload header')
        values=[int(raw[offset+6+i*8:offset+14+i*8],16) for i in range(13)]
        inode,mode,uid,gid,nlink,mtime,size,devmajor,devminor,rdevmajor,rdevminor,namesize,check=values
        if not 1<=namesize<=4096 or offset+110+namesize>len(raw):
            raise ValueError('newc pathname bounds')
        name=raw[offset+110:offset+110+namesize]
        if name[-1:]!=b'\0' or b'\0' in name[:-1]: raise ValueError('newc pathname framing')
        name=name[:-1].decode('utf-8')
        start=(offset+110+namesize+3)//4*4;end=start+size
        if end>len(raw): raise ValueError('newc file bounds')
        data=raw[start:end]
        offset=(end+3)//4*4
        if name=='TRAILER!!!':
            if size or any(raw[offset:]): raise ValueError('newc trailer/padding')
            break
        if name.startswith('./'): name=name[2:]
        path=PurePosixPath(name)
        if not name or path.is_absolute() or '..' in path.parts or str(path)!=name or name in names:
            raise ValueError('canonical unique payload pathname')
        names.add(name)
        if len(names)>512: raise ValueError('payload file ceiling')
        result.append({'path':name,'bytes':size,'sha256':digest(data),'mode':oct(mode),
            'uid':uid,'gid':gid,'inode':inode,'nlink':nlink,'mtime':mtime})
        if name==UNIT:
            if not stat.S_ISREG(mode) or not 0<size<65536 or unit is not None:
                raise ValueError('bounded regular service unit required')
            unit=data
    if unit is None: raise ValueError('exact expected service unit absent')
    return result,unit


def main():
    parser=argparse.ArgumentParser();parser.add_argument('rpm',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();raw=args.rpm.read_bytes()
    decoded,meta=payload(raw);rows,unit=members(decoded)
    args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    (args.output/'zvbid.service.txt').write_bytes(unit)
    report={'schema':'merlin-retained-rpm-inert-inspection/1','rpm_sha256':digest(raw),'rpm_bytes':len(raw),
        'method':'bounded local RPM header and newc parsing; no payload execution or installation',
        'payload':meta,'members':rows,'service_unit_sha256':digest(unit),'service_unit_bytes':len(unit)}
    (args.output/'payload-identities.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'members':len(rows),'service_unit_sha256':digest(unit),**meta},sort_keys=True))


if __name__=='__main__': main()
