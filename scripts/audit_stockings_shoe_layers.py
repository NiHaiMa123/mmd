"""Independent stockings-versus-shoes triangle checks from captured surfaces."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.motion_contact import triangle_crosses
p=argparse.ArgumentParser();p.add_argument('--surfaces',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.parent.mkdir(parents=True,exist_ok=True)
with np.load(a.surfaces) as z:data={k:z[k] for k in z.files}
v=data['Stockings'];f=data['Stockings_faces'];tree=BVHTree.FromPolygons(v.tolist(),f.tolist(),all_triangles=True);report={'scope':'Static nylon/shoe surface intersections only; no CCD','pairs':{}}
for name in data:
    if not name.startswith('Bridal') or name.endswith(('_faces','_materials')):continue
    sv=data[name];sf=data[name+'_faces'];other=BVHTree.FromPolygons(sv.tolist(),sf.tolist(),all_triangles=True);pairs=[(i,j) for i,j in tree.overlap(other) if triangle_crosses([Vector(p) for p in v[f[i]]],[Vector(p) for p in sv[sf[j]]])];report['pairs'][name]={'crossings':len(pairs)};print('NYLON_SHOE',name,len(pairs),flush=True)
    if pairs:
        ids=np.unique(f[np.unique([i for i,j in pairs])]);report['pairs'][name]['bounds_m']=[v[ids].min(axis=0).tolist(),v[ids].max(axis=0).tolist()]
report['total_crossings']=sum(r['crossings'] for r in report['pairs'].values());report['status']='STATIC_NYLON_SHOE_CLEAR' if not report['total_crossings'] else 'NYLON_SHOE_CONTACT_NOT_CLEAR';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
