"""Full-head 27-chain prototype using stock Armature and original skin weights.

One-time rest adaptation from the posed source. No Surface Deform, physics,
collision correction, smoothing, per-frame repairs or animation generation.
Controls are fixed calibration poses, never a production motion substitute.
"""
import argparse,json,sys,time,itertools
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector,Quaternion
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);candidate=Path(a.candidate);out=Path(a.out)
out.mkdir(parents=True,exist_ok=True);assert not (out/'result.json').exists(),'Use a fresh prototype directory'
started=time.monotonic();base=ROOT.parent/'work/headswap_xl_codex'
cfg=json.loads((candidate/'configuration.json').read_text('utf8'))
meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'))
rest=np.load(base/'hair_initial_repair_20261030/DELIVER_INITIAL/InitialHairRest.npz')
inspection=np.load(base/'standard_proxy_20261031/inspection/inputs.npz')
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=cfg['blend'],use_scripts=False,load_ui=False)
s=bpy.context.scene
for ob in list(bpy.data.objects):
    for md in list(ob.modifiers):
        if md.type=='CLOTH':ob.modifiers.remove(md)
if s.rigidbody_world:s.rigidbody_world.enabled=False
s.frame_set(1);bpy.context.view_layer.update()
actor=bpy.data.objects['东雪莲x达妮娅_素体'];source_arm=actor.find_armature();old=bpy.data.objects[s['HairDisplayObject']]
anchor=old.parent;assert anchor is not None
body0=coords(actor).copy();expected=coords(old).copy();T=anchor.matrix_world.copy();C=T.inverted()@source_arm.matrix_world
assert np.max(np.abs(np.array(old.matrix_world)-np.array(T)))<5e-6,'Hair source coordinate adapter required'
ids=np.array([v.value for v in old.data.attributes['SourceVertexID'].data],np.int32)
lookup={int(v):i for i,v in enumerate(ids)};order=np.array([lookup[int(v)] for v in rest['ids']])
assert len(ids)==24207 and len(meta['chains'])==27
edges=order[rest['edges']];valid=rest['source_edge_lengths']>.0005
hard=np.zeros(len(ids),bool);hard[order[rest['same_true_hard_root_mask']]]=True
labels=np.full(len(ids),-2);labels[order]=inspection['chain_labels']
hair_names={n for c in meta['chains'] for n in c['bones']};assert len(hair_names)==144
group_names={g.index:g.name for g in actor.vertex_groups}
original_weights=[];weighted_bones=set()
for vi in ids:
    row={group_names[g.group]:float(g.weight) for g in actor.data.vertices[int(vi)].groups
        if group_names[g.group] in source_arm.data.bones and g.weight>0}
    original_weights.append(row);weighted_bones.update(row)
needed=set(weighted_bones)|hair_names
for name in list(needed):
    needed.update(b.name for b in source_arm.data.bones[name].parent_recursive)
source_mode=next(m.use_deform_preserve_volume for m in actor.modifiers if m.type=='ARMATURE')
posed={name:C@source_arm.pose.bones[name].matrix for name in needed}
source_heads={name:C@source_arm.pose.bones[name].head for name in needed}
source_tails={name:C@source_arm.pose.bones[name].tail for name in needed}
lengths={name:((C@source_arm.pose.bones[name].tail)-(C@source_arm.pose.bones[name].head)).length for name in needed}
def new_rig(name,names):
    data=bpy.data.armatures.new(name);obj=bpy.data.objects.new(name,data);s.collection.objects.link(obj)
    obj.parent=anchor;obj.matrix_parent_inverse=Matrix.Identity(4);obj.matrix_basis=Matrix.Identity(4);obj.hide_render=True
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.ops.object.mode_set(mode='EDIT')
    for name in names:
        eb=data.edit_bones.new(name);m=posed[name]
        # Pose matrices may include a reflected basis. Taking only their
        # quaternion discards that reflection and can reverse the bone axis.
        # Standard EditBone head/tail + roll alignment preserves real joints.
        eb.head=source_heads[name];eb.tail=source_tails[name]
        if (eb.tail-eb.head).length<1e-6:eb.tail=eb.head+Vector((0,1e-6,0))
        eb.align_roll(m.to_3x3()@Vector((0,0,1)))
        eb.use_deform=source_arm.data.bones[name].use_deform
    for name in names:
        eb=data.edit_bones[name];parent=source_arm.data.bones[name].parent
        if parent and parent.name in names:eb.parent=data.edit_bones[parent.name]
        eb.use_connect=False
    bpy.ops.object.mode_set(mode='OBJECT');return obj
rig=new_rig('HairRig_27分束_原始蒙皮',sorted(needed))
joint_error=max((rig.data.bones[p].tail_local-rig.data.bones[c].head_local).length
    for chain in meta['chains'] for p,c in zip(chain['bones'][:-1],chain['bones'][1:]))
assert joint_error<5e-6,('Reconstructed chains lost original joint continuity',joint_error)
ev=old.evaluated_get(bpy.context.evaluated_depsgraph_get())
data=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get())
hair=bpy.data.objects.new('完整头发_27分束骨链_原始蒙皮',data);s.collection.objects.link(hair)
hair.parent=anchor;hair.matrix_parent_inverse=Matrix.Identity(4);hair.matrix_basis=Matrix.Identity(4)
hair.vertex_groups.clear()
for name in sorted(weighted_bones):hair.vertex_groups.new(name=name)
for i,row in enumerate(original_weights):
    for name,weight in row.items():hair.vertex_groups[name].add([i],weight,'REPLACE')
mobile=hair.vertex_groups.new(name='Prototype_原始真实硬根保护');mobile.add(np.flatnonzero(~hard).tolist(),1.,'REPLACE')
md=hair.modifiers.new('Native_原始权重_Armature','ARMATURE');md.object=rig
md.use_vertex_groups=True;md.use_bone_envelopes=False;md.use_deform_preserve_volume=source_mode;md.vertex_group=mobile.name
old.hide_render=True;old.hide_set(True);s['HairDisplayObject']=hair.name
for name in ['HairProxy_全头共享几何体积',cfg.get('physics_binding_target','')]:
    ob=bpy.data.objects.get(name)
    if ob:ob.hide_render=True;ob.hide_set(True)
bpy.context.view_layer.update()
initial=coords(hair);initial_error=float(np.max(np.abs(initial-expected)))
new_group_names={g.index:g.name for g in hair.vertex_groups};weight_error=0.
for i,row in enumerate(original_weights):
    new={new_group_names[g.group]:g.weight for g in hair.data.vertices[i].groups if new_group_names[g.group] in weighted_bones}
    assert set(new)==set(row),'Bone weights were lost during the interface adaptation'
    weight_error=max(weight_error,max((abs(new[n]-w) for n,w in row.items()),default=0.))
assert weight_error<1e-7,'Original bone weights changed'
assert initial_error<5e-6,'Native rest skinning changed original complete hair'
print('BONE_PROTOTYPE_INITIAL',json.dumps(dict(initial_error_m=initial_error,weight_error=weight_error,
    chains=27,dynamic_bones=144,total_rig_bones=len(rig.data.bones),original_preserve_volume=source_mode)),flush=True)
# Independent 2-bone native reference for the same rigid deformation field.
# It combines original dynamic/static influences but introduces no cage mapping.
reference_data=data.copy();reference=bpy.data.objects.new('Prototype_刚性原生参考_不渲染',reference_data)
s.collection.objects.link(reference);reference.parent=anchor;reference.matrix_parent_inverse=Matrix.Identity(4)
reference.matrix_basis=Matrix.Identity(4);reference.hide_render=True;reference.vertex_groups.clear()
ref_data=bpy.data.armatures.new('Prototype_ReferenceRig');ref_rig=bpy.data.objects.new('Prototype_ReferenceRig',ref_data)
s.collection.objects.link(ref_rig);ref_rig.parent=anchor;ref_rig.matrix_parent_inverse=Matrix.Identity(4);ref_rig.matrix_basis=Matrix.Identity(4);ref_rig.hide_render=True
bpy.ops.object.select_all(action='DESELECT');ref_rig.select_set(True);bpy.context.view_layer.objects.active=ref_rig
bpy.ops.object.mode_set(mode='EDIT')
for name in ['Dynamic','Static']:
    b=ref_data.edit_bones.new(name);b.head=(0,0,0);b.tail=(0,.1,0)
bpy.ops.object.mode_set(mode='OBJECT')
g_dynamic=reference.vertex_groups.new(name='Dynamic');g_static=reference.vertex_groups.new(name='Static')
dynamic_weight=[]
for i,row in enumerate(original_weights):
    deform={n:w for n,w in row.items() if rig.data.bones[n].use_deform};total=sum(deform.values())
    d=sum(w for n,w in deform.items() if n in hair_names)/total if total else 0.
    if hard[i]:d=0.
    dynamic_weight.append(d)
    if d:g_dynamic.add([i],d,'REPLACE')
    if d<1:g_static.add([i],1-d,'REPLACE')
ref_md=reference.modifiers.new('Native_两骨参考','ARMATURE');ref_md.object=ref_rig;ref_md.use_vertex_groups=True
ref_md.use_bone_envelopes=False;ref_md.use_deform_preserve_volume=source_mode
# One separate edge guide per authored chain, attached to its own bones.
guides=[];chain_gap=[]
for chain in meta['chains']:
    names=chain['bones'];points=[rig.data.bones[n].head_local.copy() for n in names]+[rig.data.bones[names[-1]].tail_local.copy()]
    mesh=bpy.data.meshes.new('Guide_'+chain['name']);mesh.from_pydata(points,[(i,i+1) for i in range(len(points)-1)],[]);mesh.update()
    ob=bpy.data.objects.new('Guide_'+chain['name'],mesh);s.collection.objects.link(ob)
    ob.parent=anchor;ob.matrix_parent_inverse=Matrix.Identity(4);ob.matrix_basis=Matrix.Identity(4);ob.hide_render=True;ob.display_type='WIRE'
    for i,name in enumerate(names):ob.vertex_groups.new(name=name).add([i],1.,'REPLACE')
    ob.vertex_groups[names[-1]].add([len(points)-1],1.,'REPLACE')
    gm=ob.modifiers.new('Native_发骨导向显示','ARMATURE');gm.object=rig;gm.use_vertex_groups=True;gm.use_bone_envelopes=False
    guides.append(ob)
    chain_gap.append(dict(name=chain['name'],bones=len(names),points=len(points),
        maximum_original_parent_tail_to_child_head_gap_m=max(((rig.data.bones[names[i-1]].tail_local-rig.data.bones[names[i]].head_local).length for i in range(1,len(names))),default=0.)))
s['HairPrototypeOnly']=True;s['HairPrototypeRig']=rig.name;s.frame_end=1
neutral_path=out/'完整角色_27分束原始蒙皮_未启用物理.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(neutral_path))
def neutral():
    for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
    for bone in ref_rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
    bpy.context.view_layer.update()
def rigid_field(transform):
    desired={b.name:(transform@b.matrix_local if b.name in hair_names else b.matrix_local.copy()) for b in rig.data.bones}
    for pb in rig.pose.bones:
        kw=dict(parent_matrix=desired[pb.parent.name],parent_matrix_local=pb.parent.bone.matrix_local) if pb.parent else {}
        pb.matrix_basis=pb.bone.convert_local_to_pose(desired[pb.name],pb.bone.matrix_local,invert=True,**kw)
    ref_rig.pose.bones['Dynamic'].matrix_basis=transform.copy();bpy.context.view_layer.update()
def stats(x):
    return dict(min=float(x.min()),p01=float(np.quantile(x,.01)),p50=float(np.median(x)),p99=float(np.quantile(x,.99)),max=float(x.max()))
l0=np.linalg.norm(initial[edges[:,0]]-initial[edges[:,1]],axis=1)
def check(name,reference_expected=None):
    t=time.monotonic();hair.update_tag();rig.update_tag();bpy.context.view_layer.update();actual=coords(hair)
    ratio=np.linalg.norm(actual[edges[:,0]]-actual[edges[:,1]],axis=1)/np.maximum(l0,1e-20)
    per=[dict(name=c['name'],edge_ratio=stats(ratio[valid&(labels[edges[:,0]]==i)&(labels[edges[:,1]]==i)])) for i,c in enumerate(meta['chains'])]
    row=dict(name=name,edge_ratio_from_neutral=stats(ratio[valid]),fixed_root_error_m=float(np.linalg.norm(actual[hard]-initial[hard],axis=1).max()),
        body_error_m=float(np.max(np.abs(coords(actor)-body0))),per_clump=per,geometry_evaluation_s=time.monotonic()-t)
    if reference_expected is not None:
        error=np.linalg.norm(actual-reference_expected,axis=1);row['rigid_reference_error_m']=stats(error)
        row['pass']=bool(error.max()<5e-6 and row['fixed_root_error_m']<.0001 and row['body_error_m']<5e-6)
    else:row['pass']=bool(ratio[valid].max()<1.5 and np.quantile(ratio[valid],.01)>.85 and np.quantile(ratio[valid],.99)<1.15
        and row['fixed_root_error_m']<.0001 and row['body_error_m']<5e-6)
    np.savez_compressed(out/(name+'.npz'),actual=actual,source_vertex_ids=ids,bone_pose_matrices=np.array([rig.pose.bones[n].matrix for n in sorted(hair_names)]),
        bone_names=np.array(sorted(hair_names)),guide_points=np.concatenate([coords(g) for g in guides]))
    print('BONE_PROTOTYPE_CONTROL',json.dumps({k:v for k,v in row.items() if k!='per_clump'},ensure_ascii=False),flush=True);return row
rows=[];failure=None
for name,transform in [('identity',Matrix.Identity(4)),('translate_2mm_x',Matrix.Translation((.002,0,0))),
    ('rotate_3deg_y',Matrix.Rotation(np.deg2rad(3),4,'Y'))]:
    neutral();rigid_field(transform);row=check(name,coords(reference));rows.append(row)
    if not row['pass']:failure=name;break
if failure is None:
    for sign in [1,-1]:
        neutral()
        for chain in meta['chains']:
            count=len(chain['bones'])-1
            for name in chain['bones'][1:]:
                pb=rig.pose.bones[name];pb.rotation_mode='QUATERNION'
                pb.rotation_quaternion=Quaternion((0,0,1),sign*np.deg2rad(5)/max(count,1))
        bpy.context.view_layer.update();name='chain_bend_plus_5deg' if sign>0 else 'chain_bend_minus_5deg'
        row=check(name);rows.append(row)
        if not row['pass']:failure=name;break
result=dict(status='STOPPED_NATIVE_BONE_PROTOTYPE_CONTROL_FAILURE' if failure else 'NATIVE_BONE_PROTOTYPE_CONTROLS_PASS_NOT_PHYSICS_ACCEPTED',
    source=cfg['blend'],neutral_blend=str(neutral_path),failed_control=failure,
    all_27_groups_preserved=True,dynamic_bones=144,guide_objects=len(guides),guide_points=sum(len(g.data.vertices) for g in guides),
    full_rig_bones=len(rig.data.bones),full_hair_vertices=len(ids),original_fixed_roots=int(hard.sum()),
    initial_display_error_m=initial_error,original_skin_weight_error=weight_error,original_preserve_volume=source_mode,
    maximum_chain_junction_error_m=joint_error,
    guides_follow_bones_only=True,guide_physics_or_spline_ik_installed=False,new_physics_frames=0,
    original_chain_junctions=chain_gap,controls=rows,
    bend_comparison_scope='FK bone-chain bends are different deformation fields from the prior whole-cage Simple Deform. No numerical accuracy comparison between the two bend fields is claimed.',
    eleven_second_validated=False,normal_15_second_video_created=False,elapsed_s=time.monotonic()-started,shutdown_forbidden=True)
(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'完整角色_27分束骨链_控制姿态非物理.blend'))
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
s.cycles.device='GPU';s.cycles.samples=32;s.cycles.use_denoising=True
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.filepath=str(out/'完整角色_27分束骨链_控制姿态.png')
bpy.ops.render.render(write_still=True)
print(json.dumps(dict(status=result['status'],failed_control=failure,normal_image=s.render.filepath),ensure_ascii=False),flush=True)
