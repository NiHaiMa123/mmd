import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/cynical_cloth15/structured_v2/Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);bpy.context.scene.frame_set(1)
body=bpy.data.objects['达妮娅_mesh'];cloth=bpy.data.objects['Cloth'];ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();matrix=cloth.matrix_world.inverted()@body.matrix_world
report={'body_matrix':[list(r) for r in body.matrix_world],'cloth_matrix':[list(r) for r in cloth.matrix_world],'modifiers':[(m.name,m.type,m.show_viewport) for m in body.modifiers],'materials':[(i,m.name,m.mmd_material.name_j) for i,m in enumerate(mesh.materials)],'bounds':{},'chest_faces':{}}
for label,m in [('base',body.data),('evaluated',mesh)]:
 points=np.array([(matrix@v.co)[:] for v in m.vertices]);report['bounds'][label]=[points.min(axis=0).tolist(),points.max(axis=0).tolist()]
 for f in m.polygons:
  if any(1.07<points[i,2]<1.40 and abs(points[i,0])<.19 for i in f.vertices):
   key=label+':'+m.materials[f.material_index].name;report['chest_faces'][key]=report['chest_faces'].get(key,0)+1
print('SKIN_INVENTORY',json.dumps(report,ensure_ascii=False),flush=True)
