import sys,json
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
ie=engine('import_export');ie.ensure_mmd_tools();base=ROOT/'outputs/keqing_head/proportions_v2';report=json.loads((base/'head_swap_report.json').read_text(encoding='utf-8'));bpy.ops.wm.open_mainfile(filepath=str(base/'work.blend'),load_ui=False,use_scripts=False);body=bpy.data.objects['达妮娅_mesh']
with bpy.data.libraries.load(report['target'],link=False) as (src,dst):dst.objects=['达妮娅_mesh']
old=dst.objects[0];fs=[f for f in old.data.polygons if old.data.materials[f.material_index].mmd_material.name_j in {'Body','Nails'} and min(old.data.vertices[i].co.z for i in f.vertices)<.1953568];ids=sorted({i for f in fs for i in f.vertices});prov=json.loads((base/'neck_vertex_provenance.json').read_text(encoding='utf-8'))['body'];mapped={v[0][0]:i for i,v in enumerate(prov) if len(v)==1 and abs(v[0][1]-1)<1e-7}
errors=[((body.data.vertices[mapped[i]].co-old.data.vertices[i].co).length,i,mapped[i]) for i in ids];errors.sort(reverse=True);print('HEAD_FOOT_MAPPING',len(ids),errors[:5],flush=True)
used={i for f in body.data.polygons if body.data.materials[f.material_index].mmd_material.name_j in {'Body','Nails'} and f.center.z<1.065 and abs(f.center.x)<.205 for i in f.vertices}
missing=[(i,mapped[i],list(body.data.vertices[mapped[i]].co)) for i in ids if mapped[i] not in used];print('UNUSED_BY_PANTS',len(missing),missing[:8],flush=True)
print('TARGET',report['target'],flush=True)
