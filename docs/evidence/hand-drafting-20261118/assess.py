from pathlib import Path
import math,json,hashlib,subprocess,xml.etree.ElementTree as et
import ezdxf
root=Path(__file__).resolve().parent
runs=json.loads((root/'runs.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result={'protocol_sha256':sha(root/'frozen.json'),'oracle':'GDAL 3.10.3 OGR DXF driver and ElementTree SVG parser','runs':runs,'valid':[]}
for name in ['clean-bend','spacing']:
    inp=root/(name+'.json');out=root/('out-'+name)
    source=json.loads(inp.read_text());rs=json.loads((out/'receipt.json').read_text())
    quantities=[c['length_mm'] for c in rs['connections']]
    feats=json.loads(subprocess.check_output(['ogr2ogr','-f','GeoJSON','/vsistdout/',str(out/'wiring.dxf')]))['features']
    dxf={f['properties']['Layer']:f['geometry']['coordinates'] for f in feats if f['properties']['Layer'].startswith('NET_')}
    svg=et.parse(out/'wiring.svg');tags={'s':'http://www.w3.org/2000/svg'}
    observed={}
    pins={}
    for group in svg.findall('.//s:g',tags):
        if 'data-net' in group.attrib:
            e=group.find('s:polyline',tags)
            observed[group.get('data-net')]=(e.get('data-from'),e.get('data-to'),[list(map(float,v.split(','))) for v in e.get('points').split()])
        elif 'data-pin' in group.attrib:
            e=group.find('s:circle',tags);pins[group.get('data-pin')]=[float(e.get(x)) for x in ['cx','cy']]
    s0=source['nets'][0]['routes'][0];p0=s0['points'][0];anchor=observed['N0'][2][0]
    offset=[anchor[0]-p0[0],anchor[1]+p0[1]]
    for i,n in enumerate(source['nets']):
        r=n['routes'][0];a,b,xy=observed[n['id']]
        assert dxf['NET_'+n['id']]==r['points']
        assert (a,b)==(r['from'],r['to'])
        assert xy==[[x+offset[0],offset[1]-y] for x,y in r['points']]
        assert (xy[0],xy[-1])==(pins[a],pins[b])
        assert quantities[i]==sum(math.dist(j,k) for j,k in zip(r['points'],r['points'][1:]))
    assert all(sha(out/k)==v for k,v in rs['artifact_sha256'].items()) and sha(inp)==rs['source_sha256']
    assert ezdxf.readfile(out/'wiring.dxf').units==4
    result['valid'].append(dict(name=name,nets=len(dxf),svg_translation_after_y_flip_mm=offset,lengths_mm=quantities,source_and_artifact_hashes='matched',dxf_units='mm',svg_and_dxf_coordinates='exact'))
assert [r['exit'] for r in runs]==[0,2,0,2] and not runs[1]['files'] and not runs[3]['files']
result.update(limits='No bend-radius or minimum physical-spacing rule in this CLI. Parallel paths 1 mm apart remain separate, and cross-net contact is rejected. Synthetic planar signal sheets only.')
(root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['valid'])
