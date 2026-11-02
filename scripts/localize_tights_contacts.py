import sys,json
from pathlib import Path
from collections import Counter
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'addon'),str(ROOT/'scripts')]
from mmd_outfit.service import engine
from review_tights_sleeves import evaluate
ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/stockings_sleeves/v5/work.blend'),load_ui=False,use_scripts=False)
body=bpy.data.objects['达妮娅_mesh'];stock=bpy.data.objects['Stockings'];bm,bp=evaluate(body);sm,sp=evaluate(stock)
bt=[t for t in bm.loop_triangles if bm.materials[t.material_index].mmd_material.name_j in {'Body','Nails'} and max(body.data.vertices[i].co.z for i in t.vertices)<1.12 and abs(sum(body.data.vertices[i].co.x for i in t.vertices)/3)<.22]
print('ATTRS',list(sm.attributes.keys()),'BASE',list(stock.data.attributes.keys()),flush=True)
rows=json.loads((ROOT/'outputs/stockings_sleeves/v5/review/contacts.json').read_text(encoding='utf-8'))['vmd_256']['stockings_crossings'];rows=[r for r in rows if sum(sp[i].z for i in sm.loop_triangles[r['cloth_triangle']].vertices)/3>.78]
counts=Counter();examples=[];names={g.index:g.name for g in body.vertex_groups}
for row in rows:
    t=bt[row['body_triangle']];v=body.data.vertices[t.vertices[0]];center=sum((body.data.vertices[i].co for i in t.vertices),__import__('mathutils').Vector())/3
    dominant=max(((g.weight,names[g.group]) for g in v.groups if not names[g.group].startswith('mmd_')),default=(0,''))[1];counts[(round(center.z,2),dominant)]+=1
    if len(examples)<15:examples.append({'body_rest':list(center),'stock_rest':list(sum((sp[i] for i in sm.loop_triangles[row['cloth_triangle']].vertices),__import__('mathutils').Vector())/3),'bone':dominant})
print('HIP_CONTACT_DOMAINS',counts.most_common(25),flush=True);print('EXAMPLES',json.dumps(examples),flush=True)
