"""Inspect actual metric size of the worst stretch, not just ratios."""
import sys,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();out=ROOT/'outputs/cynical_cloth15/trial3';bpy.ops.wm.open_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False)
scene=bpy.context.scene;obj=bpy.data.objects['ClothSimulationSurface'];edges=np.array([e.vertices[:] for e in obj.data.edges]);pin=obj.vertex_groups['ClothPins'].index
def points(frame):
    scene.frame_set(frame);bpy.context.view_layer.update();ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();co=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',co);ev.to_mesh_clear();return co.reshape(-1,3)
start=points(1);initial=np.linalg.norm(start[edges[:,0]]-start[edges[:,1]],axis=1);rows={}
for frame in (240,270,300,330,450):
    co=points(frame);length=np.linalg.norm(co[edges[:,0]]-co[edges[:,1]],axis=1);order=np.argsort(length/np.maximum(initial,1e-6))[-12:][::-1]
    rows[str(frame)]={'max_edge_m':float(length.max()),'extension_p99_m':float(np.quantile(length-initial,.99)),'worst':[{'ids':edges[i].tolist(),'initial_m':float(initial[i]),'length_m':float(length[i]),'points':co[edges[i]].tolist(),'pins':[sum(g.weight for g in obj.data.vertices[j].groups if g.group==pin) for j in edges[i]]} for i in order]}
(out/'stretch_details.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
engine('extraction')._setup_render(scene,560,700);data=bpy.data.cameras.new('StretchDiagnostic');data.type='ORTHO';data.ortho_scale=1.95;cam=bpy.data.objects.new('StretchDiagnostic',data);scene.collection.objects.link(cam);scene.camera=cam;scene.frame_set(270);center=Vector((0,.20,.85));cam.location=center+Vector((.15,-1,.02)).normalized()*4;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/'cache_review'/'full_0270.png');bpy.ops.render.render(write_still=True)
print('STRETCH_DETAILS',json.dumps({k:{n:v[n] for n in ('max_edge_m','extension_p99_m')} for k,v in rows.items()}),flush=True)
