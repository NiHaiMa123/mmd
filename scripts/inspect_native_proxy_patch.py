"""Read-only native mesh/deform-layer diagnostics; no simulation advance."""
import argparse,json,sys
from pathlib import Path
import bpy,bmesh,numpy as np
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.candidate)
c=json.loads((out/'configuration.json').read_text('utf8'))
bpy.ops.wm.open_mainfile(filepath=c['blend'],use_scripts=False,load_ui=False)
proxy=bpy.data.objects['HairProxy_全头共享几何体积']
bm=bmesh.new();bm.from_mesh(proxy.data);layer=bm.verts.layers.deform.active
report={}
for g in proxy.vertex_groups:
    objw=np.array([next((x.weight for x in v.groups if x.group==g.index),0.) for v in proxy.data.vertices])
    bmw=np.array([v[layer].get(g.index,0.) for v in bm.verts])
    report[g.name]=dict(index=g.index,object_nonzero=int((objw>.001).sum()),bmesh_nonzero=int((bmw>.001).sum()),
        bmesh_min=float(bmw.min()),bmesh_max=float(bmw.max()))
g=next(g for g in proxy.vertex_groups if g.name.startswith('StaticFit_BodyFacing'))
edges=[e for e in bm.edges if e.calc_length()<.0004]
report['short_edges']=dict(total=len(edges),both_fit=sum(all(v[layer].get(g.index,0.)>.001 for v in e.verts) for e in edges),
    any_fit=sum(any(v[layer].get(g.index,0.)>.001 for v in e.verts) for e in edges))
bm.free();(out/'native_group_inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(report,ensure_ascii=False),flush=True)
