"""Inventory local crotch faces and cloth islands before targeted repair."""
import json,sys
from pathlib import Path
from collections import Counter
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'addon'),str(ROOT/'scripts')]
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/stockings_sleeves/review_ready/work.blend'),load_ui=False,use_scripts=False)
out=ROOT/'outputs/cynical_cloth15';out.mkdir(exist_ok=True)
result={}
def comps(mesh,faces):
    adjacency={};vf={}
    for f in faces:
        for i in f.vertices:vf.setdefault(i,[]).append(f.index)
    remaining={f.index for f in faces};components=[]
    while remaining:
        stack=[remaining.pop()];component=[]
        while stack:
            i=stack.pop();component.append(i)
            for v in mesh.polygons[i].vertices:
                for j in vf[v]:
                    if j in remaining:remaining.remove(j);stack.append(j)
        ids={i for j in component for i in mesh.polygons[j].vertices};points=[mesh.vertices[i].co for i in ids]
        components.append({'faces':component,'vertices':len(ids),'bounds':[[min(p[k] for p in points) for k in range(3)],[max(p[k] for p in points) for k in range(3)]], 'materials':dict(Counter(mesh.materials[mesh.polygons[j].material_index].name for j in component))})
    return sorted(components,key=lambda c:-len(c['faces']))
for name in ('达妮娅_mesh','Stockings','Cloth'):
    obj=bpy.data.objects[name];entry={'base_vertices':len(obj.data.vertices),'modifiers':[(m.name,m.type) for m in obj.modifiers]}
    for evaluated in (False,True):
        ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get()) if evaluated else None;mesh=ev.to_mesh() if ev else obj.data
        selected=[f for f in mesh.polygons if abs(f.center.x)<.075 and -.10<f.center.y<.13 and .83<f.center.z<1.00]
        entry['evaluated' if evaluated else 'base']=comps(mesh,selected)
        if name=='Cloth' and not evaluated:entry['all_islands']=comps(mesh,list(mesh.polygons))
        if ev:ev.to_mesh_clear()
    result[name]=entry
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
result['bones']={b.name:b.mmd_bone.name_j for b in arm.pose.bones}
(out/'inspection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('CYNICAL_MODEL_INSPECTED',flush=True)
