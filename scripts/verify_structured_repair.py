"""Verify unchanged character data, matching motion, and coherent anchors."""
import sys,json,hashlib
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
ie=engine('import_export');ie.ensure_mmd_tools();old=ROOT/'outputs/cynical_cloth15/trial3';out=Path(sys.argv[sys.argv.index('--')+1]).resolve()
def digest(obj):
    h=hashlib.sha256();a=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',a);h.update(a.tobytes())
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:key.data.foreach_get('co',a);h.update(a.tobytes())
    return h.hexdigest()
def coordinates(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();co=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',co);ev.to_mesh_clear();return co
bpy.ops.wm.open_mainfile(filepath=str(old/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False)
protected={o.name:digest(o) for o in ie.model_meshes()};poses={}
for frame in (1,270,330):bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();poses[frame]=coordinates(bpy.data.objects['达妮娅_mesh'])
bpy.ops.wm.open_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;first=int(scene.get('outfit_preview_first',1));result={'protected_meshes':{name:digest(bpy.data.objects[name])==value for name,value in protected.items()},'motion_coordinate_error_m':{},'anchors':{},'visual_cloth_motion_m':{}}
assert all(result['protected_meshes'].values()),'Changed original character vertex or morph coordinates'
proxy=bpy.data.objects['ClothSimulationSurface'];reference=bpy.data.objects['ClothKinematicReference'];target=bpy.data.objects['ClothShapePreservingTarget'];pin=proxy.vertex_groups['ClothPins'].index
fixed={v.index for v in proxy.data.vertices if any(g.group==pin and g.weight>=1.-1e-7 for g in v.groups)}
fixed_edges=[e.vertices[:] for e in proxy.data.edges if all(i in fixed for i in e.vertices)];base=np.array([v.co[:] for v in proxy.data.vertices]);pairs=np.array(fixed_edges);rest=np.linalg.norm(base[pairs[:,0]]-base[pairs[:,1]],axis=1)
for source_frame in (1,270,330):
    scene.frame_set(first+source_frame-1);bpy.context.view_layer.update();error=float(np.abs(coordinates(bpy.data.objects['达妮娅_mesh'])-poses[source_frame]).max());result['motion_coordinate_error_m'][str(source_frame)]=error;assert error<1e-5,(source_frame,error)
    co=coordinates(proxy).reshape(-1,3);ratio=np.linalg.norm(co[pairs[:,0]]-co[pairs[:,1]],axis=1)/np.maximum(rest,1e-6);result['anchors'][str(source_frame)]={'fully_pinned_edges':len(pairs),'maximum_ratio_to_rest':float(ratio.max()),'maximum_absolute_edge_change_m':float(np.abs(np.linalg.norm(co[pairs[:,0]]-co[pairs[:,1]],axis=1)-rest).max())}
    print('FIXED_ANCHOR_CHECK',source_frame,json.dumps(result['anchors'][str(source_frame)]),flush=True)
    assert result['anchors'][str(source_frame)]['maximum_absolute_edge_change_m']<.0001,'Fixed attachment edges still stretching'
    delta=np.linalg.norm(coordinates(target).reshape(-1,3)-coordinates(reference).reshape(-1,3),axis=1);result['visual_cloth_motion_m'][str(source_frame)]={'max':float(delta.max()),'rms':float(np.sqrt((delta**2).mean()))};assert delta.max()>.001,'Cloth displacement accidentally disabled'
(out/'repair_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('STRUCTURED_REPAIR_VERIFIED',json.dumps(result,ensure_ascii=False),flush=True)
