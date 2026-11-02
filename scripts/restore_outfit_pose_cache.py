"""Retarget existing cloth shape cache to the corrected attachment bones.

Restores pose-consistent garments, fixes inward lining thickness and nylon
normal sampling. This is cache retargeting, not a new physical cloth bake.
"""
import argparse,hashlib,json,struct,sys,time
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm=bpy.data.objects['达妮娅_arm'];cloth=bpy.data.objects['Cloth'];target=bpy.data.objects['ClothShapePreservingTarget'];corrected=arm.animation_data.action;original=bpy.data.actions['シニカルナイトプラン_bone'];report={'status':'PREPARING','method':'existing cloth shapes retargeted by same-time attachment bone deltas','new_physical_cloth_solve':False,'source_mesh_coordinates_changed':False}
def digest(obj):
    h=hashlib.sha256();co=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',co);h.update(co.tobytes())
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:key.data.foreach_get('co',co);h.update(co.tobytes())
    return h.hexdigest()
protected={o.name:digest(o) for o in engine('import_export').model_meshes()};cache=target.modifiers.get('Rotation-aware constrained sleeve cache');path=Path(bpy.path.abspath(cache.filepath));raw=path.read_bytes();header=struct.unpack('<12siiffi',raw[:32]);signature,version,n,start,spacing,count=header
if signature!=b'POINTCACHE2\0' or n!=len(target.data.vertices) or spacing!=1.:raise ValueError('Unexpected source cloth cache')
source=np.frombuffer(raw[32:],dtype='<f4').reshape(count,n,3).copy();weights={g.index:g.name for g in target.vertex_groups if g.name in arm.pose.bones};names=sorted(set(weights.values()));w=np.zeros((n,len(names)))
for v in target.data.vertices:
    for g in v.groups:
        if g.group in weights:w[v.index,names.index(weights[g.group])]+=g.weight
if np.any(w.sum(axis=1)<.999):raise ValueError('Attachment mapping does not cover every cloth proxy point')
w/=w.sum(axis=1,keepdims=True);visibility={o:o.hide_viewport for o in bpy.data.objects if o.type=='MESH'}
for o in visibility:o.hide_viewport=True
to_world=np.array(target.matrix_world);to_local=np.linalg.inv(to_world);arm_world=np.array(arm.matrix_world);world_inv=np.linalg.inv(arm_world);result=[];begin=time.perf_counter()
for index in range(count):
    frame=int(start+index*spacing)+1;arm.animation_data.action=original;scene.frame_set(frame);bpy.context.view_layer.update();before={name:np.array(arm.pose.bones[name].matrix) for name in names};arm.animation_data.action=corrected;scene.frame_set(frame);bpy.context.view_layer.update();after={name:np.array(arm.pose.bones[name].matrix) for name in names};points=source[index];final=np.zeros_like(points,dtype=float)
    for j,name in enumerate(names):
        delta=to_local@arm_world@after[name]@np.linalg.inv(before[name])@world_inv@to_world;final+=(points@delta[:3,:3].T+delta[:3,3])*w[:,j,None]
    result.append(final.astype('<f4'))
    if index%100==0:print('RETARGET_CLOTH_CACHE',frame,flush=True)
for o,value in visibility.items():o.hide_viewport=value
arm.animation_data.action=corrected;result=np.array(result);newpath=out/'PoseConsistentCloth.pc2'
with newpath.open('wb') as f:f.write(raw[:32]);f.write(result.tobytes())
cache.filepath=str(newpath);cache.show_viewport=True;cache.show_render=True;cloth.modifiers['Structured cloth absolute positions'].show_viewport=True;cloth.modifiers['Structured cloth absolute positions'].show_render=True
report['retarget']={'samples':count,'attachment_bones':names,'max_cache_change_m':float(np.linalg.norm(result-source,axis=-1).max()),'seconds':time.perf_counter()-begin}
# Put the entire fitted lining outside skin; old offset=-1 straddled skin.
lining=bpy.data.objects['SleeveLining'];solid=next(m for m in lining.modifiers if m.type=='SOLIDIFY');report['old_lining_thickness']={'thickness':solid.thickness,'offset':solid.offset};solid.thickness=.0006;solid.offset=1.;solid.use_even_offset=False
for m in lining.modifiers:
    if m.type=='NODES':
        for node in m.node_group.nodes:
            if node.bl_idname=='ShaderNodeVectorMath' and node.operation=='SCALE':node.inputs['Scale'].default_value=.001
report['new_lining_thickness']={'base_clearance_m':.001,'thickness_m':.0006,'offset':1.}
# Compute hosiery normals on complete welded skin BEFORE selecting the band.
stock=bpy.data.objects['Stockings'];nylon=stock.modifiers['Nylon from evaluated body surface'].node_group;n=nylon.nodes;l=nylon.links;info=next(x for x in n if x.bl_idname=='GeometryNodeObjectInfo');weld=next(x for x in n if x.bl_idname=='GeometryNodeMergeByDistance');move=next(x for x in n if x.bl_idname=='GeometryNodeSetPosition' and x.inputs['Offset'].is_linked);seam=next(x for x in n if x.bl_idname=='GeometryNodeSetPosition' and x!=move and x.inputs['Selection'].is_linked)
l.new(info.outputs['Geometry'],weld.inputs['Geometry']);select=n.new('GeometryNodeSeparateGeometry');select.domain='FACE';l.new(move.outputs['Geometry'],select.inputs['Geometry']);field=n.new('GeometryNodeInputNamedAttribute');field.data_type='BOOLEAN';field.inputs['Name'].default_value='OutfitNylonFaces';l.new(field.outputs['Attribute'],select.inputs['Selection']);l.new(select.outputs['Selection'],seam.inputs['Geometry'])
scale=move.inputs['Offset'].links[0].from_node;scale.inputs['Scale'].default_value=.0005;report['nylon']={'normal_source':'complete welded evaluated body before garment face selection','margin_m':.0005,'foot_patch_preserved':True}
assert all(digest(bpy.data.objects[name])==value for name,value in protected.items()),'Original mesh/morph data changed';report['protected_meshes_and_morphs']=len(protected);report['status']='POSE_CONSISTENT_CACHE_RESTORED_REQUIRES_CONTACT_AUDIT';scene.frame_set(325);scene['outfit_contact_status']=report['status'];bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_PoseConsistent.blend'),compress=True);cache.filepath=bpy.path.relpath(str(newpath));bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_PoseConsistent.blend'),compress=True);(out/'restore_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('OUTFIT_RESTORED',json.dumps(report),flush=True)
