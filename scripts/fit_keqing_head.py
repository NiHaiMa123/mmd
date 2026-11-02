"""Transplant Keqing's complete head onto the dressed Daniya, in a new file."""
import sys,argparse,json,importlib,shutil,math
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
from mmd_outfit.head_swap import material_name,clipped_subset,opening,adapt_neck,connect_necks,repair_neck_alpha
from mmd_outfit.preserved_shoe import replace_mesh
p=argparse.ArgumentParser();p.add_argument('--target',required=True);p.add_argument('--profile',required=True);p.add_argument('--out',required=True);p.add_argument('--scale',type=float);p.add_argument('--neck-z',type=float,default=1.33)
p.add_argument('--head-lift',type=float,default=0.)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
ie,dressing,physics,render=[engine(n) for n in ('import_export','dressing','physics','extraction')]
package=ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.target,load_ui=False,use_scripts=False)
target_objects=list(bpy.data.objects);target_arm=next(o for o in target_objects if o.type=='ARMATURE');target_root=ie.mmd_root(target_arm)
body=next(o for o in ie.model_meshes() if not o.get('mmd_garment'))
protected={o.name:([tuple(v.co) for v in o.data.vertices],o.matrix_world.copy()) for o in ie.model_meshes() if o!=body}
profile=read_json(a.profile);source_objects=ie.import_pmx(profile['source']['path']);source_arm=next(o for o in source_objects if o.type=='ARMATURE');source=ie.model_meshes(source_objects)[0];source_root=ie.mmd_root(source_arm)
core=importlib.import_module(package+'.core.bone').FnBone
core.clean_additional_transformation(target_arm);core.clean_additional_transformation(source_arm)
source_head={source_arm.data.bones['頭'].name,*[b.name for b in source_arm.data.bones['頭'].children_recursive]}
source_head={n for n in source_head if not n.startswith(('_dummy_','_shadow_'))}
old_head={target_arm.data.bones['頭'].name,*[b.name for b in target_arm.data.bones['頭'].children_recursive]}
common={'頭','両目','目.L','目.R'};remove_bones=old_head-common
old_target_head_materials=[]
for mi,material in enumerate(body.data.materials):
    ids={i for f in body.data.polygons if f.material_index==mi for i in f.vertices}
    if not ids:continue
    names={g.index:g.name for g in body.vertex_groups}
    influence=sum(sum(g.weight for g in body.data.vertices[i].groups if names[g.group] in old_head) for i in ids)/len(ids)
    if influence>.75:old_target_head_materials.append(material)
assert len(old_target_head_materials)>=20,'Cannot safely identify the original head material domains'
target_face=next(m for m in body.data.materials if material_name(m)=='face1')
source_face=next(m for m in source.data.materials if material_name(m)=='面')
def width(obj,material):
    ids={i for f in obj.data.polygons if obj.data.materials[f.material_index]==material for i in f.vertices}
    return max(obj.data.vertices[i].co.x for i in ids)-min(obj.data.vertices[i].co.x for i in ids)
scale=a.scale or width(body,target_face)/width(source,source_face)
head_anchor=target_arm.data.bones['頭'].head_local+Vector((0,0,a.head_lift))
matrix=Matrix.Translation(head_anchor)@Matrix.Scale(scale,4)@Matrix.Translation(-source_arm.data.bones['頭'].head_local)
head_neck_z=a.neck_z+.004+a.head_lift
report={'target':a.target,'source':profile['source']['path'],'scale':scale,'head_lift_m':a.head_lift,'head_transform':[list(r) for r in matrix],'neck_cut_m':a.neck_z,'head_neck_cut_m':head_neck_z,'old_head_materials':[material_name(m) for m in old_target_head_materials]}
body_faces=[f.index for f in body.data.polygons if body.data.materials[f.material_index] not in old_target_head_materials]
body_part,body_provenance=clipped_subset(body,body_faces,'HeadlessTargetBody',clip_material='Body',plane_z=a.neck_z,above=False)
head_materials={'面','面1','白目','目','睫','二重','眉','口舌','目星','发','发饰','辫','照れ','发jinshu','肌'}
head_faces=[f.index for f in source.data.polygons if material_name(source.data.materials[f.material_index]) in head_materials]
head_part,head_provenance=clipped_subset(source,head_faces,'KeqingHeadSource',transform=matrix,clip_material='肌',plane_z=head_neck_z,above=True)
low,center=opening(body_part,a.neck_z);high,head_center=opening(head_part,head_neck_z)
radius=Vector((max(abs(body_part.data.vertices[i].co.x-center.x) for i in low),max(abs(body_part.data.vertices[i].co.y-center.y) for i in low),1))
report['neck_adaptation_max_m']=adapt_neck(head_part,high,center,radius)
replacement,bridge=connect_necks(body_part,head_part,low,high,'KeqingHeadDaniyaBody')
report['neck_bridge']=bridge;report['body_provenance_vertices']=len(body_provenance);report['head_source_vertices']=len(head_provenance)
replace_mesh(body,replacement)
textures=out/'textures';textures.mkdir(exist_ok=True)
report['neck_texture_repair']=repair_neck_alpha(body,a.neck_z,textures/'keqing_neck_skin.png')
for obj in (body_part,head_part):bpy.data.objects.remove(obj,do_unlink=True)
# Replace facial and hair bones, keeping the target torso/neck/limbs intact.
for obj in ie.model_meshes(target_objects):
    if obj==body:continue
    affected=[g.name for g in obj.vertex_groups if g.name in remove_bones and any(vg.group==g.index and vg.weight>1e-6 for v in obj.data.vertices for vg in v.groups)]
    if affected:raise ValueError('Removing a head bone still used by other clothing: '+repr(affected))
old_rigids=[o for o in target_objects if getattr(o,'mmd_type','')=='RIGID_BODY' and o.mmd_rigid.bone in old_head]
old_set=set(old_rigids);old_joints=[o for o in target_objects if getattr(o,'mmd_type','')=='JOINT' and o.rigid_body_constraint and (o.rigid_body_constraint.object1 in old_set or o.rigid_body_constraint.object2 in old_set)]
for obj in [*old_joints,*old_rigids]:bpy.data.objects.remove(obj,do_unlink=True)
target_objects=[o for o in bpy.data.objects if o not in set(source_objects)]
target_arm.hide_set(False);bpy.context.view_layer.objects.active=target_arm;target_arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for name in remove_bones:
    bone=target_arm.data.edit_bones.get(name)
    if bone:target_arm.data.edit_bones.remove(bone)
for name in source_head:
    src=source_arm.data.bones[name];dst=target_arm.data.edit_bones.get(name) or target_arm.data.edit_bones.new(name)
    dst.head=matrix@src.head_local;dst.tail=matrix@src.tail_local;dst.use_connect=False;dst.use_deform=src.use_deform
    dst.align_roll(matrix.to_3x3()@src.matrix_local.to_3x3().col[2])
for name in source_head:
    src=source_arm.data.bones[name];parent=src.parent.name if src.parent else None
    if parent:target_arm.data.edit_bones[name].parent=target_arm.data.edit_bones.get(parent)
if a.head_lift:
    target_arm.data.edit_bones['首'].tail=target_arm.data.edit_bones['頭'].head
bpy.ops.object.mode_set(mode='OBJECT')
next_id=max(b.mmd_bone.bone_id for b in target_arm.pose.bones)+1
for name in sorted(source_head):
    if target_arm.pose.bones[name].mmd_bone.bone_id<0:
        target_arm.pose.bones[name].mmd_bone.bone_id=next_id;next_id+=1
for name in source_head:
    src=source_arm.pose.bones[name];dst=target_arm.pose.bones[name]
    for prop in src.mmd_bone.bl_rna.properties:
        key=prop.identifier
        if key in {'rna_type','bone_id'} or key.endswith('_bone_id') or prop.is_readonly or prop.type not in {'BOOLEAN','INT','FLOAT','STRING','ENUM'}:continue
        try:setattr(dst.mmd_bone,key,getattr(src.mmd_bone,key))
        except (TypeError,AttributeError):pass
    dst.rotation_mode=src.rotation_mode;dst.lock_location=src.lock_location;dst.lock_rotation=src.lock_rotation;dst.lock_scale=src.lock_scale
for name in source_head:
    target_arm.pose.bones[name].mmd_bone.additional_transform_bone=source_arm.pose.bones[name].mmd_bone.additional_transform_bone
report['head_bones']={'removed':len(remove_bones),'source':sorted(source_head),'removed_rigid_bodies':len(old_rigids),'removed_joints':len(old_joints)}
report['hair_physics']=physics.migrate_physics(source_objects,target_objects,source_arm,target_arm,{n:matrix for n in source_head},source_head)
assert not report['hair_physics'].get('joints_skipped',0),'Hair joints lost their endpoints'
# Preserve useful target channels; give standard facial morph names to Keqing.
source_morphs=[{key:getattr(m,key) for key in ('name','name_e','category')} for m in source_root.mmd_root.vertex_morphs]
write_json(out/'source_head_morphs.json',source_morphs)
available={k.name for obj in ie.model_meshes(target_objects) if obj.data.shape_keys for k in obj.data.shape_keys.key_blocks}
root=target_root.mmd_root
root.name_j='刻晴头 · 达妮娅素体';root.name_e='Keqing head / Daniya body'
for m in source_morphs:
    entry=root.vertex_morphs.get(m['name']) or root.vertex_morphs.add()
    for key,value in m.items():setattr(entry,key,value)
# Remove references to the old face, retaining body morphs and extra UV layers.
kept_materials={m.name for obj in ie.model_meshes(target_objects) for m in obj.data.materials}
pruned={};old_material_names={m.name for m in old_target_head_materials}
for collection_name in ('bone_morphs','material_morphs'):
    collection=getattr(root,collection_name);removed_items=removed_morphs=0
    for j in range(len(collection)-1,-1,-1):
        morph=collection[j];had_data=bool(len(morph.data))
        for i in range(len(morph.data)-1,-1,-1):
            item=morph.data[i]
            bad=(item.bone in old_head or item.bone not in target_arm.data.bones) if collection_name=='bone_morphs' else item.material in old_material_names
            if bad:morph.data.remove(i);removed_items+=1
        if had_data and not len(morph.data):collection.remove(j);removed_morphs+=1
    pruned[collection_name]={'removed_items':removed_items,'removed_morphs':removed_morphs,'retained':len(collection)}
for morph in root.group_morphs:
    for i in range(len(morph.data)-1,-1,-1):
        item=morph.data[i]
        if getattr(root,item.morph_type).get(item.name) is None:morph.data.remove(i)
report['old_head_morph_references_pruned']=pruned
for frame in root.display_item_frames:
    for i in range(len(frame.data)-1,-1,-1):
        item=frame.data[i]
        if item.type=='BONE' and item.name not in target_arm.data.bones:frame.data.remove(i)
report['keqing_vertex_morphs']=len(source_morphs)
for obj in source_objects:
    if obj.name in bpy.data.objects:bpy.data.objects.remove(obj,do_unlink=True)
core.apply_additional_transformation(target_arm);bpy.context.view_layer.update()
for side in ('L','R'):
    assert target_arm.pose.bones['目.'+side].mmd_bone.additional_transform_bone=='両目','Eye control points at the wrong source bone id'
for name,(coords,world) in protected.items():
    obj=bpy.data.objects[name]
    assert coords==[tuple(v.co) for v in obj.data.vertices],name+' geometry changed during head transfer'
    assert world==obj.matrix_world,name+' transform changed during head transfer'
report['outfit_and_shoes_geometry_unchanged']=True
report['body_mesh']={'vertices':len(body.data.vertices),'faces':len(body.data.polygons),'morph_keys':len(body.data.shape_keys.key_blocks)}
write_json(out/'head_swap_report.json',report)
write_json(out/'neck_vertex_provenance.json',{'body':body_provenance,'head':head_provenance})
previous_fit=Path(a.target).parent/'fit_report.json'
if previous_fit.exists():
    metadata=read_json(previous_fit);metadata['head_followup']={'report':str(out/'head_swap_report.json'),'neck_texture':str(textures/'keqing_neck_skin.png')}
    write_json(out/'fit_report.json',metadata)
scene=bpy.context.scene;scene.frame_set(1)
model=ie.model_meshes()
for obj in bpy.data.objects:
    obj.hide_set(obj not in model)
    obj.hide_render=obj.type=='MESH' and obj not in model
for prop in ('show_armature','show_rigid_bodies','show_joints','show_temporary_objects'):setattr(target_root.mmd_root,prop,False)
for obj in bpy.data.objects:
    if obj not in model:obj.hide_set(True)
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   space=area.spaces.active;space.overlay.show_overlays=False;space.show_gizmo=False;space.shading.type='MATERIAL'
   space.region_3d.view_location=Vector((0,.025,1.35));space.region_3d.view_distance=.70;space.region_3d.view_rotation=Vector((.25,-1,.02)).to_track_quat('Z','Y');space.region_3d.view_perspective='ORTHO'
bpy.ops.wm.save_as_mainfile(filepath=str(out/'work.blend'));shutil.copyfile(out/'work.blend',out/'Keqing_Head_Daniya_Body.blend')
render._setup_render(scene,1000,1000);render._setup_lights(scene)
data=bpy.data.cameras.new('HeadSwapCamera');data.type='ORTHO';camera=bpy.data.objects.new('HeadSwapCamera',data);scene.collection.objects.link(camera);scene.camera=camera
center=Vector((0,.015,1.405))
for name,direction,scale_view in [('front',(0,-1,.01),.48),('oblique',(.7,-1,.03),.48),('side',(1,0,.01),.48),('back',(0,1,.01),.48),('full',(0,-1,.07),1.75)]:
    target=Vector((0,.025,.81)) if name=='full' else center;data.ortho_scale=scale_view
    camera.location=target+Vector(direction).normalized()*3;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(out/f'{name}.png');bpy.ops.render.render(write_still=True)
for name,values in [('blink',{'まばたき':1.}),('mouth_a',{'あ':1.}),('smile',{'笑い':1.,'にやり':.7})]:
    for key in body.data.shape_keys.key_blocks:key.value=values.get(key.name,0.)
    data.ortho_scale=.35;camera.location=center+Vector((0,-3,.02));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(out/f'expression_{name}.png');bpy.ops.render.render(write_still=True)
for key in body.data.shape_keys.key_blocks:key.value=0.
print('KEQING_HEAD_SWAP_COMPLETE',json.dumps({k:v for k,v in report.items() if k not in {'head_transform','neck_bridge'}},ensure_ascii=False),flush=True)
