"""Blender bone playback of the audited native joint output, with real cloth.

Render two controlled numerical cases at native 960x1080 per half. This is a
backend demo, not the character or a finished MMD clothing result.
"""
import argparse,json,struct,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,Quaternion
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--render-all',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=Path(a.input).resolve()
comparison=json.loads((folder/'comparison_physics_output.json').read_text(encoding='utf-8'))
if comparison['status']!='PHYSICS_JOINT_OUTPUT_SAMPLED_PASS_LIVE_POSE_MISMATCH':raise RuntimeError('The exported numerical surfaces have not passed their audit')
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=960;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.display.shading.light='STUDIO';scene.display.shading.color_type='OBJECT';scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True;scene.display.shading.background_type='WORLD';scene.world=bpy.data.worlds.new('White studio');scene.world.color=(.65,.65,.65);scene.render.film_transparent=False;scene.render.fps=100;scene.frame_start=1
data={};objects={};cache_paths=[]
def create_mesh(name,co,faces,color):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(co.tolist(),[],faces.tolist());mesh.update();obj=bpy.data.objects.new(name,mesh);scene.collection.objects.link(obj);obj.color=color;return obj
def cache(obj,coords,name):
    path=folder/(name+'.pc2')
    with path.open('wb') as handle:handle.write(struct.pack('<12siiffi',b'POINTCACHE2\0',1,coords.shape[1],1.,1.,len(coords)));handle.write(np.asarray(coords,dtype='<f4').tobytes())
    mod=obj.modifiers.new('Actual simulated cloth','MESH_CACHE');mod.cache_format='PC2';mod.filepath=str(path);mod.frame_start=1;mod.time_mode='FRAME';mod.deform_mode='OVERWRITE';cache_paths.append((mod,path))
for mode in ('free','two_way'):
    with np.load(folder/mode/'joint_output.npz') as archive:data[mode]={k:archive[k] for k in archive.files}
    d=data[mode];armdata=bpy.data.armatures.new(mode+'_rig');rig=bpy.data.objects.new(mode+'_rig',armdata);scene.collection.objects.link(rig);bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT');bone=armdata.edit_bones.new('ProbeShoulder');bone.head=(0,0,.6);bone.tail=(.6,0,.6);bpy.ops.object.mode_set(mode='OBJECT');rig.select_set(False);rig.hide_render=True;rig.hide_set(True)
    body=create_mesh(mode+'_arm',d['arm'][0],d['arm_faces'],(.2,.48,.75,1));group=body.vertex_groups.new(name='ProbeShoulder');group.add(list(range(8)),1.,'REPLACE');mod=body.modifiers.new('Physical joint output','ARMATURE');mod.object=rig
    pose=rig.pose.bones['ProbeShoulder'];pose.rotation_mode='QUATERNION';axis=armdata.bones['ProbeShoulder'].matrix_local.to_3x3().inverted()@Vector((0,0,1))
    for f,angle in enumerate(d['output_q_rad'],1):pose.rotation_quaternion=Quaternion(axis,float(angle));pose.keyframe_insert(data_path='rotation_quaternion',frame=f)
    items=[body]
    for key in sorted(k for k in d if k.startswith('cloth_') and len(k.split('_'))==2):
        j=key.split('_')[-1];cloth=create_mesh(mode+'_cloth_'+j,d[key][0],d['cloth_faces_'+j],(.52,.27,.72,1) if j=='0' else (.2,.7,.53,1));cache(cloth,d[key],mode+'_cloth_'+j);items.append(cloth)
    objects[mode]=items
scene.frame_end=len(data['two_way']['output_q_rad'])
camera_data=bpy.data.cameras.new('Probe camera');camera=bpy.data.objects.new('Probe camera',camera_data);scene.collection.objects.link(camera);camera.location=(1.4,-1.9,1.4);target=Vector((.28,.22,.58));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=1.12;scene.camera=camera
def visibility(active):
    for mode,items in objects.items():
        for obj in items:obj.hide_render=mode!=active;obj.hide_set(mode!=active)
def verify():
    error=0.
    for frame in (1,scene.frame_end,45):
        scene.frame_set(frame);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
        for mode,items in objects.items():
            for index,obj in enumerate(items):
                evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();co=np.array([v.co[:] for v in mesh.vertices]);evaluated.to_mesh_clear();expected=data[mode]['output_arm' if index==0 else 'cloth_'+str(index-1)][frame-1];error=max(error,float(np.abs(co-expected).max()))
    if error>1e-6:raise RuntimeError(f'Blender bone/cache playback mismatch {error}')
    return error
for items in objects.values():
    for obj in items:obj.hide_set(False)
before=verify();visibility('two_way');scene.frame_set(70);blend=folder/'Backend_JointCloth_Probe.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
for mod,path in cache_paths:mod.filepath=bpy.path.relpath(str(path))
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
# Reopen the actual saved file and verify the armature and relative caches.
object_names={mode:[obj.name for obj in items] for mode,items in objects.items()}
bpy.ops.wm.open_mainfile(filepath=str(blend),load_ui=False,use_scripts=False)
objects={mode:[bpy.data.objects[name] for name in names] for mode,names in object_names.items()};scene=bpy.context.scene
for items in objects.values():
    for obj in items:obj.hide_set(False)
after=verify();frames=range(1,scene.frame_end+1) if a.render_all else (1,60,75,91)
for mode in ('free','two_way'):
    visibility(mode);directory=folder/'preview_frames'/mode;directory.mkdir(parents=True,exist_ok=True)
    for frame in frames:scene.frame_set(frame);scene.render.filepath=str(directory/f'{frame:04d}.png');bpy.ops.render.render(write_still=True)
visibility('two_way');scene.frame_set(70)
(folder/'blender_playback_qa.json').write_text(json.dumps({'bone_and_cloth_max_error_before_save_m':before,'bone_and_cloth_max_error_after_reload_m':after,'blender_fps':100,'physics_sample_time_span_s':float(data['two_way']['time_s'][-1]),'samples':scene.frame_end,'scope':'rotation-only single bone and two numerical cloth layers; not MMD character acceptance'},indent=2),encoding='utf-8')
print('BACKEND_BLENDER_PLAYBACK_VERIFIED',before,after,flush=True)
