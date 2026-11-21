"""Rebuild the verified derived ZIP with one reviewed launcher replacement."""
import argparse
import ast
import copy
import hashlib
import io
import json
from pathlib import Path
import zipfile

OLD_SHA256='58f9b4fee8b03db777a07e76149ef5fedcc8c1c9b3309c16499b3cadecfbac90'
OLD_BYTES=66068


def sha(raw): return hashlib.sha256(raw).hexdigest()


def blob(raw): return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def canonical(value): return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def render(infos,members,comment):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        archive.comment=comment
        for info in infos:
            archive.writestr(copy.copy(info),members[info.filename],compress_type=info.compress_type,compresslevel=6)
    return output.getvalue()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--original',type=Path,required=True)
    parser.add_argument('--launcher',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();old=args.original.read_bytes();launcher=args.launcher.read_bytes()
    if len(old)!=OLD_BYTES or sha(old)!=OLD_SHA256: raise ValueError('exact original runtime archive required')
    ast.parse(launcher,feature_version=(3,9))
    with zipfile.ZipFile(io.BytesIO(old)) as archive:
        infos=archive.infolist();comment=archive.comment
        if len(infos)!=15 or len({info.filename for info in infos})!=15: raise ValueError('exact original member set required')
        original={info.filename:archive.read(info) for info in infos}
    manifest=json.loads(original['manifest.json'])
    if manifest.get('schema')!='merlin-browser-runtime/1' or len(manifest.get('files',[]))!=14:
        raise ValueError('original runtime contract differs')
    for item in manifest['files']:
        raw=original[item['path']]
        if len(raw)!=item['bytes'] or sha(raw)!=item['sha256'] or blob(raw)!=item['git_blob']:
            raise ValueError('original member differs from its source identity')
    if render(infos,original,comment)!=old: raise ValueError('original deterministic ZIP settings differ')
    changed=[]
    for item in manifest['files']:
        if item['path']=='bin/launch-episode':
            item.update(bytes=len(launcher),sha256=sha(launcher),git_blob=blob(launcher));changed.append(item['path'])
    if changed!=['bin/launch-episode']: raise ValueError('one exact launcher member required')
    members={**original,'bin/launch-episode':launcher,'manifest.json':canonical(manifest)}
    result=render(infos,members,comment);args.output.mkdir(parents=True,exist_ok=False)
    path=args.output/'merlin-browser-runtime.zip';path.write_bytes(result)
    pins={'bytes':len(result),'sha256':sha(result),'git_blob':blob(result),'expert_source_commit':manifest['expert_source_commit']}
    (args.output/'manifest.json').write_bytes(members['manifest.json'])
    (args.output/'runtime-pins.json').write_bytes(canonical(pins))
    verification={'schema':'merlin-browser-runtime-rebuild/1','original_archive_sha256':sha(old),
        'original_archive_reconstructed_exactly':True,'zip_compression_level':6,
        'member_order_preserved':True,'zipinfo_metadata_preserved':True,
        'changed_members':['bin/launch-episode','manifest.json'],
        'unchanged_payload_members':[name for name in members if name not in ('bin/launch-episode','manifest.json')],
        'all_thirteen_other_payloads_identical':all(members[name]==original[name] for name in members if name not in ('bin/launch-episode','manifest.json')),
        'runtime_pin':pins,'runtime_manifest_sha256':sha(members['manifest.json']),
        'launcher':{'bytes':len(launcher),'sha256':sha(launcher),'git_blob':blob(launcher)},
        'authoritative_product_source_unchanged':manifest['expert_source_commit'],'native_execution':False}
    (args.output/'package-verification.json').write_bytes(canonical(verification))
    print(json.dumps(verification,sort_keys=True,indent=2))


if __name__=='__main__': main()
