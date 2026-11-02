"""Replace only prescribed body trajectories after a separately verified detour."""
import argparse,json,shutil,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--sample-step',type=float,default=.125);p.add_argument('--first',type=float);p.add_argument('--last',type=float);p.add_argument('--detour',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);src=Path(a.input);detour=Path(a.detour);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
if (out/'manifest.json').exists():raise ValueError('Use a new feedback export directory')
dr=json.loads((detour/'report.json').read_text('utf8'));check=json.loads((detour/'independent_validation.json').read_text('utf8'))
if check['status']!='CLUMP_DETOUR_SAMPLED_REOPEN_PASS':raise ValueError('Independently validated detour required')
manifest=json.loads((src/'manifest.json').read_text('utf8'));profile=dr['rig_profile']
with np.load(src/'trajectories.npz') as z:d={k:z[k] for k in z.files}
raw=Path(manifest['collider_conditioning']['source']) if 'collider_conditioning' in manifest else src
with np.load(raw/'trajectories.npz') as z:skin_ids=z['skin_ids'];faces=z['body_faces']
run=Path(manifest['source_run']);base=json.loads((run/'report.json').read_text('utf8'))
engine('import_export').ensure_mmd_tools();old_first,old_last=manifest['source_frames'];first=old_first if a.first is None else a.first;last=old_last if a.last is None else a.last
if not first<last or a.sample_step<=0:raise ValueError('Invalid export window')
frames=np.arange(first,last+.001,a.sample_step);old_heads=[]
bpy.ops.wm.open_mainfile(filepath=base['source'],load_ui=False,use_scripts=False);old_arm=bpy.data.objects[profile['armature']]
bpy.context.scene.frame_set(int(old_first),subframe=old_first%1);bpy.context.view_layer.update();volume_rest_anchor=np.array(old_arm.matrix_world@old_arm.pose.bones[dr['bundle']['anchor_bone']].matrix)
for frame in frames:
 bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();old_heads.append(np.array(old_arm.matrix_world@old_arm.pose.bones[dr['bundle']['anchor_bone']].matrix))
bpy.ops.wm.open_mainfile(filepath=dr['candidate'],load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];body=[];new_heads=[];peak=0.
for frame,old_head in zip(frames,old_heads):
 bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();body.append(coords(mesh)[skin_ids]);head=np.array(arm.matrix_world@arm.pose.bones[dr['bundle']['anchor_bone']].matrix);new_heads.append(head);peak=max(peak,float(np.max(np.abs(head-old_head))))
rest_volume=d['cloth'][0];deltas=np.asarray(new_heads)@np.linalg.inv(volume_rest_anchor);d['cloth']=np.einsum('fij,vj->fvi',deltas[:,:3,:3],rest_volume)+deltas[:,None,:3,3];manifest['sample_times_s']=((frames-first)/manifest['fps']).tolist();manifest['source_frames']=[float(first),float(last)]
if peak>2e-6:raise ValueError('Detour changed the head trajectory; reinitialize the hair volume')
d['body']=np.asarray(body);d['body_faces']=faces;d['skin_ids']=skin_ids;np.savez_compressed(out/'trajectories.npz',**d);shutil.copyfile(src/'volume_binding.npz',out/'volume_binding.npz');manifest.pop('collider_conditioning',None);manifest['source_blend']=dr['candidate'];manifest['feedback_body']=dict(source_detour=str(detour),sample_count=len(frames),head_trajectory_peak_error=peak,raw_skin_vertices=len(skin_ids),all_body_faces_preserved=True,requires_collider_conditioning=True);(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');print('PPF_FEEDBACK_BODY',json.dumps(manifest['feedback_body']),flush=True)
