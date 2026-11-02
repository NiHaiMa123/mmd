"""Read-only rig diagnosis: static cheek-lock shape and collider clearances."""
import bpy,sys,json,numpy as np
from pathlib import Path
from mathutils import Vector
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();base=repo.parent/'work/headswap_xl_codex';out=base/'short_sidehair_20261101/rest_probe';out.mkdir(exist_ok=True)
src=base/'normal_preview15_20261101/完整角色_现有最佳流程_15秒预览.blend'
bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
s=bpy.context.scene;arm=bpy.data.objects['东雪莲x达妮娅_骨架'];targets={f'Sidehair{i}.{side}' for i in range(1,8) for side in ['L','R']}
arm.animation_data.action=arm.animation_data.action.copy();action=arm.animation_data.action
for layer in action.layers:
 for strip in layer.strips:
  for bag in getattr(strip,'channelbags',[]):
   for fc in list(bag.fcurves):
    if any(fc.data_path.startswith('pose.bones['+json.dumps(n)+']') for n in targets):bag.fcurves.remove(fc)
for n in targets:
 b=arm.pose.bones[n];b.location=(0,0,0);b.rotation_quaternion=(1,0,0,0);b.scale=(1,1,1)
 for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(data_path=prop,frame=1,group=n)
rows=[]
for f in [1,151,331,450]:
 s.frame_set(f);bpy.context.view_layer.update()
 for n in sorted(targets):
  b=arm.pose.bones[n];p=arm.matrix_world@b.tail;hits=[]
  for ob in bpy.data.collections['Jiggle_Physics_Colliders'].objects:
   if ob.type!='EMPTY':continue
   mat=ob.matrix_world;v=mat.inverted()@p;radius=(mat.inverted().to_3x3()@((p-mat.translation).normalized()*.006)).length
   if v.length<1+radius:hits.append(dict(collider=ob.name,normalized_distance=v.length,expanded_limit=1+radius,center=list(mat.translation),scale=list(mat.to_scale())))
  rows.append(dict(frame=f,bone=n,tail=list(p),rest_tail=list(b.bone.tail_local),hits=hits))
(out/'report.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
s.cycles.device='GPU';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.image_settings.file_format='PNG';s.render.resolution_percentage=100;s.render.use_sequencer=False
s.frame_set(450);s.render.filepath=str(out/'rest_locks_f0450.png');bpy.ops.render.render(write_still=True)
print('REST_PROBE_COMPLETE',flush=True)
