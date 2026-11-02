"""Verify the exported hybrid's face, eye inheritance, morphs and neck texture."""
import argparse,sys,json,math,hashlib
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine,_static_validation
from mmd_outfit.jobs import read_json,write_json
p=argparse.ArgumentParser();p.add_argument('--fit',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.fit).resolve()
ie,render=engine('import_export'),engine('extraction');ie.clear_scene();objects=ie.import_pmx(str(out/'mmd/model.pmx'))
mesh=ie.model_meshes(objects)[0];arm=next(o for o in objects if o.type=='ARMATURE');root=ie.mmd_root(arm)
result={'pmx':str(out/'mmd/model.pmx'),'static_validation':_static_validation(objects),'accepted':False,'scope':'PMX face/eye follow, expression smoke checks and owned neck texture; no hair dynamics simulation'}
assert not result['static_validation']['failures']
source_names=[m['name'] for m in read_json(out/'source_head_morphs.json')]
assert all(mesh.data.shape_keys.key_blocks.get(n) is not None for n in source_names)
assert all(root.mmd_root.vertex_morphs.get(n) is not None for n in source_names)
result['source_facial_morph_names_present']=len(source_names)
for side in ('L','R'):assert arm.pose.bones['目.'+side].mmd_bone.additional_transform_bone=='両目'
neck=next(m for m in mesh.data.materials if m.mmd_material.name_j=='Keqing_NeckBlend');image=neck.node_tree.nodes['mmd_base_tex'].image
copied=Path(bpy.path.abspath(image.filepath));original=out/'textures/keqing_neck_skin.png'
assert hashlib.sha256(copied.read_bytes()).digest()==hashlib.sha256(original.read_bytes()).digest(),'Stale exported neck texture'
assert min(image.pixels[3::4])>.999
result['neck_texture']={'exported':str(copied),'source_owned':str(original),'hashes_identical':True,'alpha_opaque':True,'dimensions':list(image.size)}
render._setup_render(bpy.context.scene,1000,1000);render._setup_lights(bpy.context.scene)
data=bpy.data.cameras.new('ExportedHeadReview');data.type='ORTHO';data.ortho_scale=.43
camera=bpy.data.objects.new('ExportedHeadReview',data);bpy.context.scene.collection.objects.link(camera);bpy.context.scene.camera=camera
center=Vector((0,.015,1.41));camera.location=center+Vector((.7,-3,.02));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
for obj in bpy.data.objects:
    if obj.type=='MESH':obj.hide_render=obj!=mesh
head=arm.pose.bones['頭'];face_ids={i for f in mesh.data.polygons if mesh.data.materials[f.material_index].mmd_material.name_j=='面' for i in f.vertices}
eye_ids={i for f in mesh.data.polygons if mesh.data.materials[f.material_index].mmd_material.name_j=='目' for i in f.vertices}
checks=[]
for label,morphs,turn in [('neutral',{},0),('blink',{'まばたき':1.},0),('mouth_a',{'あ':1.},0),('head_turn',{},30)]:
    for key in mesh.data.shape_keys.key_blocks:key.value=morphs.get(key.name,0.)
    head.matrix_basis=Matrix.Identity(4)
    if turn:
        rotation=head.bone.matrix_local.to_3x3();head.rotation_mode='QUATERNION';head.rotation_quaternion=(rotation.inverted()@Matrix.Rotation(math.radians(turn),3,'Z')@rotation).to_quaternion()
    bpy.context.view_layer.update();evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());me=evaluated.to_mesh()
    delta=max((me.vertices[i].co-mesh.data.vertices[i].co).length for i in face_ids)
    row={'case':label,'max_face_movement_m':delta}
    if turn:
        motion=head.matrix@head.bone.matrix_local.inverted()
        error=max((me.vertices[i].co-motion@mesh.data.vertices[i].co).length for i in eye_ids)
        assert error<3e-6,'Exported eyes no longer follow the head';row['eye_follow_error_m']=error
    elif morphs:assert delta>.001,'Exported expression has no visible vertex effect'
    evaluated.to_mesh_clear();checks.append(row)
    bpy.context.scene.render.filepath=str(out/f'pmx_head_{label}.png');bpy.ops.render.render(write_still=True)
result['checks']=checks;write_json(out/'pmx_head_verification.json',result)
print('EXPORTED_HEAD_VERIFIED',json.dumps({k:v for k,v in result.items() if k!='static_validation'},ensure_ascii=False),flush=True)
