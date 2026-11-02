"""Isolated full-character head-turn/stop control; original actions untouched."""
import argparse,json,math,shutil,struct,sys,time
from pathlib import Path
import bpy,numpy as np
from mathutils import Quaternion
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);assert not (out/'setup.json').exists()
base=repo.parent/'work/headswap_xl_codex';source=base/'preview075_175_24fps_20261101/prepared';prepared=json.loads((source/'setup.json').read_text('utf8'))
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=prepared['blend'],load_ui=False,use_scripts=False)
s=bpy.context.scene;s.frame_set(1);s.frame_end=91;s.render.fps=30;s.render.fps_base=1.;bpy.context.view_layer.update()
actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();initial=coords(actor);head=arm.pose.bones['頭'];original=arm.animation_data.action;original.use_fake_user=True
arm.animation_data.action=original.copy();action=arm.animation_data.action;action.name='INERTIA_CONTROL_ONLY_转头急停_原正片动作保留';prefix=head.path_from_id()
for layer in action.layers:
 for strip in layer.strips:
  for bag in getattr(strip,'channelbags',[]):
   for fc in list(bag.fcurves):
    if fc.data_path.startswith(prefix):bag.fcurves.remove(fc)
head.rotation_mode='QUATERNION';base_rotation=head.rotation_quaternion.copy();head.scale=(1,1,1);head.location=(0,0,0)
keys=[(1,0,0),(16,25,15),(31,25,15),(46,0,0),(91,0,0)]
for frame,yaw,tilt in keys:
 head.rotation_quaternion=base_rotation@Quaternion((0,1,0),math.radians(yaw))@Quaternion((0,0,1),math.radians(tilt))
 head.keyframe_insert('rotation_quaternion',frame=frame,group='INERTIA_CONTROL_HEAD_ONLY')
for layer in action.layers:
 for strip in layer.strips:
  for bag in getattr(strip,'channelbags',[]):
   for fc in bag.fcurves:
    if fc.data_path.startswith(prefix):
     for key in fc.keyframe_points:key.interpolation='LINEAR'
s.frame_set(1);bpy.context.view_layer.update();assert np.max(np.abs(coords(actor)-initial))<5e-6,'Control initial pose differs'
data=out/'input_body_aware';data.mkdir(exist_ok=True);old=source/'input_body_aware'
for name in ['skin_ids.npy','body_faces.npy','real_body_faces.npy']:shutil.copy2(old/name,data/name)
skin=np.load(data/'skin_ids.npy');body=np.lib.format.open_memmap(data/'body.npy',mode='w+',dtype='<f4',shape=(721,len(skin),3));head_matrices=[];started=time.monotonic()
for k in range(721):
 f=1+k/8;s.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();body[k]=coords(actor)[skin]
 if k%8==0:head_matrices.append(np.array(arm.matrix_world@arm.pose.bones['頭'].matrix))
 if k%120==0:print('INERTIA_CONTROL_BODY',f,flush=True)
body.flush();np.save(data/'head_matrices.npy',np.array(head_matrices))
cache=out/'cache';cache.mkdir(exist_ok=True)
with (cache/'animated_body_collider.pc2').open('wb') as f:
 f.write(struct.pack('<12siiffi',b'POINTCACHE2\0',1,len(skin),1.,.25,361))
 for k in range(0,721,2):f.write(np.asarray(body[k],dtype='<f4').tobytes())
for ob in bpy.data.objects:
 for md in ob.modifiers:
  if md.type=='MESH_CACHE':
   src=Path(bpy.path.abspath(md.filepath));dst=cache/src.name
   if src.name!='animated_body_collider.pc2' and not dst.exists():shutil.copy2(src,dst)
   md.filepath=str(dst)
s.frame_set(1);s['InertiaControlOnly']=True;s['ProductionMotionEdited']=False;s['ShutdownForbidden']=True
blend=out/'完整角色_惯性对照专用动作_未模拟.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
prepared.update(blend=str(blend),source_prepared=prepared['blend'],expected_body_input=str(data),control_only=True,original_action_preserved=original.name,control_action=action.name,control_head_keys=keys,original_production_action_edited=False,frames_planned=[1,91],export_elapsed_s=time.monotonic()-started)
(out/'setup.json').write_text(json.dumps(prepared,ensure_ascii=False,indent=2),'utf8');print('INERTIA_CONTROL_PREPARED',json.dumps(dict(blend=str(blend),frames=[1,91]),ensure_ascii=False),flush=True)
