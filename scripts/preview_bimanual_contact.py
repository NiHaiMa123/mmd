"""Audited six-bone native contact playback in Blender, including reload QA."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,Quaternion
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--render-all',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=Path(a.input).resolve()
audit=json.loads((folder/'comparison.json').read_text(encoding='utf-8'))
if audit['status']!='BIMANUAL_CONTACT_CONTROLLED_PROXY_PASS':raise RuntimeError('Contact comparison must pass first')
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=960;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.display.shading.light='STUDIO';scene.display.shading.color_type='OBJECT';scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True;scene.display.shading.background_type='WORLD';scene.world=bpy.data.worlds.new('White studio');scene.world.color=(.8,.8,.8);scene.render.fps=100;scene.frame_start=1
data={};items={};names={}
def mesh(name,co,faces,color):
    m=bpy.data.meshes.new(name);m.from_pydata(co.tolist(),[],faces.tolist());m.update();o=bpy.data.objects.new(name,m);scene.collection.objects.link(o);o.color=color;return o
for mode in ('free','contact'):
    with np.load(folder/mode/'trajectory.npz') as z:d={k:z[k] for k in z.files}
    data[mode]=d;ad=bpy.data.armatures.new(mode+'_six_joint_rig');rig=bpy.data.objects.new(mode+'_six_joint_rig',ad);scene.collection.objects.link(rig);bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT');bones=[]
    for i,name in enumerate(d['names']):
        t=d['transforms'][0,i];b=ad.edit_bones.new(str(name));b.head=Vector(t[:3,3]);b.tail=b.head+Vector(t[:3,0])*(.08 if i%3==2 else .25)
        if d['parents'][i]>=0:b.parent=bones[d['parents'][i]]
        bones.append(b)
    bpy.ops.object.mode_set(mode='OBJECT');rig.select_set(False);rig.hide_render=True;rig.hide_set(True);objects=[]
    for i,name in enumerate(d['names']):
        name=str(name);obj=mesh(mode+'_'+name,d[f'body_{i}'][0],d[f'faces_{i}'],(.85,.32,.14,1) if i%3==2 else (.2,.48,.75,1) if i<3 else (.23,.68,.49,1));vg=obj.vertex_groups.new(name=name);vg.add(list(range(len(obj.data.vertices))),1.,'REPLACE');mod=obj.modifiers.new('Native joint rotations','ARMATURE');mod.object=rig;objects.append(obj)
        pose=rig.pose.bones[name];pose.rotation_mode='QUATERNION';axis=ad.bones[name].matrix_local.to_3x3().inverted()@Vector((0,0,1))
        for f,q in enumerate(d['q'][:,i],1):pose.rotation_quaternion=Quaternion(axis,float(q));pose.keyframe_insert(data_path='rotation_quaternion',frame=f)
    objects.append(mesh(mode+'_fixed_torso',d['root'],d['root_faces'],(.38,.4,.46,1)));items[mode]=objects;names[mode]=[o.name for o in objects]
scene.frame_end=len(data['contact']['q']);camera_data=bpy.data.cameras.new('Contact review');camera=bpy.data.objects.new('Contact review',camera_data);scene.collection.objects.link(camera);camera.location=(0,-.05,2.7);camera.rotation_euler=(Vector((0,-.05,.7))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=1.;scene.camera=camera
def visibility(mode):
    for key,objects in items.items():
        for o in objects:o.hide_render=key!=mode;o.hide_set(key!=mode)
def verify():
    error=0.
    for f in (1,51,101,scene.frame_end):
        scene.frame_set(f);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
        for mode,objects in items.items():
            for i,obj in enumerate(objects[:6]):
                evaluated=obj.evaluated_get(deps);m=evaluated.to_mesh();co=np.array([v.co[:] for v in m.vertices]);evaluated.to_mesh_clear();error=max(error,float(np.linalg.norm(co-data[mode][f'body_{i}'][f-1],axis=-1).max()))
    if error>2e-6:raise RuntimeError(f'Bone playback mismatch: {error}')
    return error
before=verify();visibility('contact');scene.frame_set(scene.frame_end);blend=folder/'Bimanual_Contact_Probe.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.wm.open_mainfile(filepath=str(blend),load_ui=False,use_scripts=False);scene=bpy.context.scene;items={mode:[bpy.data.objects[name] for name in ns] for mode,ns in names.items()}
for objects in items.values():
    for obj in objects:obj.hide_set(False)
after=verify()
for mode in ('free','contact'):
    visibility(mode);directory=folder/'preview_frames'/mode;directory.mkdir(parents=True,exist_ok=True)
    for f in range(1,scene.frame_end+1) if a.render_all else (1,76,151):scene.frame_set(f);scene.render.filepath=str(directory/f'{f:04d}.png');bpy.ops.render.render(write_still=True)
visibility('contact');scene.frame_set(scene.frame_end)
report={'scope':'Six-bone declared persistent contact fixture, not actual character/fingers','frames':scene.frame_end,'physics_fps':100,'simulation_seconds':float(data['contact']['time_s'][-1]),'max_blender_bone_error_before_save_m':before,'max_blender_bone_error_after_reload_m':after,'rendered_all':a.render_all}
(folder/'blender_playback_qa.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('BIMANUAL_BLENDER_PLAYBACK',json.dumps(report),flush=True)
