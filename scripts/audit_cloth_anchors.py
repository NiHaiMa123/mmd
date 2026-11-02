"""Check anchor motion against base geometry before assigning wrinkle causes."""
import sys,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();folder=ROOT/'outputs/cynical_cloth15/trial3';bpy.ops.wm.open_mainfile(filepath=str(folder/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False)
scene=bpy.context.scene;obj=bpy.data.objects['ClothSimulationSurface'];arm=next(m.object for m in obj.modifiers if m.type=='ARMATURE');edges=np.array([e.vertices[:] for e in obj.data.edges]);base=np.array([v.co[:] for v in obj.data.vertices]);lengths=np.linalg.norm(base[edges[:,0]]-base[edges[:,1]],axis=1);pairs=[(219,258),(218,259),(150,151)];result={'edge_reference':'base proxy geometry and first evaluated dance frame reported separately','frames':{}}
def evaluated():
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();co=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('co',co);ev.to_mesh_clear();return co.reshape(-1,3)
for frame in (1,240,270,300):
    scene.frame_set(frame);bpy.context.view_layer.update();co=evaluated();cur=np.linalg.norm(co[edges[:,0]]-co[edges[:,1]],axis=1);row={'edge_ratio_to_base_p99':float(np.quantile(cur/np.maximum(lengths,1e-6),.99)),'edges':[]}
    for a,b in pairs:
        row['edges'].append({'ids':[a,b],'base_length_m':float(np.linalg.norm(base[a]-base[b])),'evaluated_length_m':float(np.linalg.norm(co[a]-co[b])),'weights':[[[obj.vertex_groups[g.group].name,g.weight] for g in obj.data.vertices[i].groups if g.weight>.001] for i in (a,b)]})
    result['frames'][str(frame)]=row
out=ROOT/'outputs/cynical_cloth15/research_wrinkles/anchor_audit.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('CLOTH_ANCHOR_AUDIT',json.dumps(result,ensure_ascii=False),flush=True)
