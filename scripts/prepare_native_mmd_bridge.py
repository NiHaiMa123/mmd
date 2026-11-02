"""Prepare a separate PMX and visually baked FK input for native MMD physics.

The rendering scene is never overwritten. Hair uses its original PMX rigid
bodies and joints; body bones are animated kinematically with the corrected FK.
"""
import argparse,sys,json,time,importlib
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.track import fcurves
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--input',required=True);p.add_argument('--binding',required=True);p.add_argument('--out',required=True);p.add_argument('--last',type=int,default=450);p.add_argument('--preroll',type=int,default=30);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
out=Path(a.out);out.mkdir(parents=True,exist_ok=True);src=Path(a.input)
manifest=json.loads((src/'export_complete.json').read_text('utf8'));profile=json.loads(Path(manifest['rig_profile']).read_text('utf8'))
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False)
s=bpy.context.scene;arm=bpy.data.objects[profile['armature']];mesh=bpy.data.objects[profile['mesh']];s.frame_set(1);bpy.context.view_layer.update()
root=arm
while root and getattr(root,'mmd_type','')!='ROOT':root=root.parent
assert root and not root.mmd_root.is_built
if s.rigidbody_world:s.rigidbody_world.enabled=False
ids=np.load(src/'hair_ids.npy');initial=np.load(src/'hair_initial.npy');binding=np.load(a.binding);weights=binding['weights'];groupnames=binding['names'].tolist();head=manifest['anchor_bones'][-1]
hair=set(groupnames)-{head}
for name in list(hair):
    parent=arm.data.bones[name].parent
    while parent and parent.name!=head:hair.add(parent.name);parent=parent.parent
attr=mesh.data.attributes[profile['surface_attribute']];skinids={i for f in mesh.data.polygons if attr.data[f.index].value in profile['body_classes']+profile['head_classes'] for i in f.vertices}
skinbones={mesh.vertex_groups[g.group].name for i in skinids for g in mesh.data.vertices[i].groups if g.weight>.01 and mesh.vertex_groups[g.group].name in arm.data.bones}
# Pull the calibrated first-pose display rest back into the original bind space.
aw=np.array(arm.matrix_world);ai=np.linalg.inv(aw);mw=np.array(mesh.matrix_world);transforms=[]
for name in groupnames:
    b=arm.pose.bones[name];transforms.append(aw@np.array(b.matrix)@np.linalg.inv(np.array(b.bone.matrix_local))@ai@mw)
blend=np.einsum('vg,gij->vij',weights.astype(np.float64),np.asarray(transforms));rest=np.linalg.solve(blend[:,:3,:3],(initial-blend[:,:3,3])[...,None])[...,0]
forward=np.einsum('vij,vj->vi',blend[:,:3,:3],rest)+blend[:,:3,3];assert np.max(np.linalg.norm(forward-initial,axis=1))<1e-7
base=np.empty((len(mesh.data.vertices),3),dtype=np.float32);mesh.data.shape_keys.key_blocks[0].data.foreach_get('co',base.ravel());delta=rest-base[ids]
for key in mesh.data.shape_keys.key_blocks:
    co=np.empty_like(base);key.data.foreach_get('co',co.ravel());co[ids]+=delta.astype(np.float32);key.data.foreach_set('co',co.ravel())
mesh.data.update();np.save(out/'calibrated_hair_bind.npy',rest);np.save(out/'hair_ids.npy',ids)
# Native PMX needs only the original armature skinning, not Blender cache nodes.
removed=[]
for mod in list(mesh.modifiers):
    if mod.type!='ARMATURE':removed.append(mod.name);mesh.modifiers.remove(mod)
names=[b.name for b in arm.pose.bones if not b.is_mmd_shadow_bone];indices={name:i for i,name in enumerate(names)}
pose=np.empty((a.last,len(names),4,4),dtype=np.float32);source_head=np.load(src/'anchors.npy',mmap_mode='r');headerr=0.;started=time.monotonic()
for obj in s.objects:
    if obj.type=='MESH':obj.hide_set(True)
for frame in range(1,a.last+1):
    s.frame_set(frame);bpy.context.view_layer.update()
    pose[frame-1]=np.asarray([np.array(arm.pose.bones[n].matrix) for n in names])
    k=round((frame-1)/manifest['sample_step']);headerr=max(headerr,float(np.abs(np.array(arm.matrix_world@arm.pose.bones[head].matrix)-source_head[k,-1]).max()))
    if frame%50==0:print('NATIVE_FK_CAPTURE',frame,'seconds',time.monotonic()-started,flush=True)
assert headerr<3e-6,headerr
np.save(out/'corrected_source_pose.npy',pose)
# Bake the evaluated pose, so native MMD does not solve a different body IK.
arm.animation_data_clear()
for b in arm.pose.bones:
    for c in list(b.constraints):b.constraints.remove(c)
    b.mmd_bone.has_additional_rotation=False;b.mmd_bone.has_additional_location=False
    b.rotation_mode='QUATERNION';b.matrix_basis=Matrix.Identity(4);b.lock_location=(False,False,False);b.lock_rotation=(False,False,False)
    if b.name in indices:b.mmd_bone.name_j=f'B{indices[b.name]:04d}';b.mmd_bone.name_e=b.name
data=np.zeros((a.last,len(names),7),dtype=np.float64)
for j,name in enumerate(names):
    b=arm.data.bones[name];parent=b.parent
    assert parent is None or parent.name in indices,('Shadow parent needs explicit adaptation',name,parent.name)
    for k in range(a.last):
        args={} if parent is None else dict(parent_matrix=Matrix(pose[k,indices[parent.name]]),parent_matrix_local=parent.matrix_local)
        basis=b.convert_local_to_pose(Matrix(pose[k,j]),b.matrix_local,invert=True,**args);loc,q,scale=basis.decompose()
        if k and np.dot(data[k-1,j,3:],q)<0:q.negate()
        data[k,j,:3]=loc;data[k,j,3:]=q
action=bpy.data.actions.new('NativeMMD_CorrectedFK_WithPreroll');arm.animation_data_create();arm.animation_data.action=action
dummy=arm.pose.bones[names[0]];dummy.keyframe_insert('location',frame=1)
bag=action.layers[0].strips[0].channelbags[0]
for curve in list(bag.fcurves):bag.fcurves.remove(curve)
times=np.r_[1,np.arange(1,a.last+1)+a.preroll]
curve_count=0
for j,name in enumerate(names):
    for component in range(7):
        default=1. if component==3 else 0.;values=data[:,j,component]
        if np.max(np.abs(values-default))<1e-7:continue
        path=arm.pose.bones[name].path_from_id('location' if component<3 else 'rotation_quaternion');index=component if component<3 else component-3
        curve=bag.fcurves.new(path,index=index);v=np.r_[values[0],values]
        if np.ptp(values)<1e-7:t=np.array([1.]);v=np.array([values[0]])
        else:t=times
        curve.keyframe_points.add(len(t));curve.keyframe_points.foreach_set('co',np.column_stack([t,v]).astype(np.float32).ravel())
        for key in curve.keyframe_points:key.interpolation='LINEAR'
        curve.update();curve_count+=1
if mesh.data.shape_keys:mesh.data.shape_keys.animation_data_clear()
# Preserve original hair types, springs and hair-to-hair masks. Add an unused
# native collision group for the kinematic corrected body.
rigids=[o for o in root.children_recursive if getattr(o,'mmd_type','')=='RIGID_BODY'];hairrig=[o for o in rigids if o.mmd_rigid.bone in hair];used={o.mmd_rigid.collision_group_number for o in hairrig};free=sorted(set(range(16))-used);assert free,'No unused collision group for body'
bodygroup=free[-1];kept=[];dynamic=[];original=[]
for obj in rigids:
    r=obj.mmd_rigid
    if r.bone in hair:
        original.append(dict(name=obj.name,bone=r.bone,type=str(r.type),group=r.collision_group_number,mask=list(r.collision_group_mask)))
        mask=list(r.collision_group_mask);mask[bodygroup]=False;r.collision_group_mask=mask;kept.append(obj)
        if str(r.type)!='0':dynamic.append(obj)
    elif r.bone in skinbones or r.bone==head:
        r.type='0';r.collision_group_number=bodygroup;r.collision_group_mask=tuple(i==bodygroup for i in range(16));kept.append(obj)
keep=set(kept);moving=set(dynamic);joint_count=0
for obj in list(root.children_recursive):
    if getattr(obj,'mmd_type','')=='JOINT':
        c=obj.rigid_body_constraint
        if not c or c.object1 not in keep or c.object2 not in keep or not ({c.object1,c.object2}&moving):bpy.data.objects.remove(obj,do_unlink=True)
        else:joint_count+=1
for obj in rigids:
    if obj not in keep:bpy.data.objects.remove(obj,do_unlink=True)
for obj in root.children_recursive:
    if obj.type=='MESH' and getattr(obj,'mmd_type','') not in ['RIGID_BODY'] and obj!=mesh:obj.hide_set(True)
mesh.hide_set(False);root.hide_set(False);arm.hide_set(False)
for obj in bpy.context.selected_objects:obj.select_set(False)
root.select_set(True);bpy.context.view_layer.objects.active=root
root.mmd_root.name='XL_Dania_Physics';s.frame_start=1;s.frame_end=a.last+a.preroll;s.render.fps=30;s.frame_set(1);bpy.context.view_layer.update()
name_map={f'B{j:04d}':name for j,name in enumerate(names)}
(out/'bone_name_map.json').write_text(json.dumps(name_map,ensure_ascii=False,indent=2),'utf8')
bpy.ops.mmd_tools.export_pmx(filepath=str(out/'character_physics.pmx'),scale=12.5,copy_textures_mode='NONE',visible_meshes_only=True,fix_bone_order=True)
for obj in bpy.context.selected_objects:obj.select_set(False)
arm.select_set(True);bpy.context.view_layer.objects.active=arm
bpy.ops.mmd_tools.export_vmd(filepath=str(out/'corrected_fk_preroll.vmd'),scale=12.5,use_frame_range=True,preserve_curves=True,use_pose_mode=False)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'native_physics_input.blend'),compress=True,relative_remap=False)
report=dict(status='NATIVE_MMD_INPUT_PREPARED_REQUIRES_ROUNDTRIP_AND_PHYSICS_REVIEW',source=a.source,hair_vertices=len(ids),hair_bones=sorted(hair),dynamic_rigids=len(dynamic),kinematic_rigids=len(kept)-len(dynamic),joints=joint_count,body_collision_group=bodygroup,hair_original_physics=original,original_hair_types_and_self_masks_preserved=True,head_motion_capture_error_m=headerr,source_frames=[1,a.last],preroll=a.preroll,native_source_frames=[a.preroll,a.preroll+a.last-1],curve_count=curve_count,removed_blender_only_modifiers=removed,source_unchanged=True)
(out/'preparation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('NATIVE_MMD_INPUT_PREPARED',len(dynamic),joint_count,flush=True)
