import sys,json,math
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame,coords
from animation_contact_tools.projector import FrameProjector
engine('import_export').ensure_mmd_tools();out=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028/body_track'
bpy.ops.wm.open_mainfile(filepath=str(out/'BodyContact_Candidate.blend'),load_ui=False,use_scripts=False)
profile=json.loads((out/'rig_profile.json').read_text('utf8'));report=json.loads((out/'body_track_report.json').read_text('utf8'));arm=bpy.data.objects[profile['armature']];mesh=bpy.data.objects[profile['mesh']];parts=regions(mesh,arm,profile);solver=FrameProjector(mesh,arm,profile,parts,profile['control_chains'])
ad=arm.animation_data;original=bpy.data.actions[report['original_action']];delta=bpy.data.actions[report['correction_action']];bones=[arm.pose.bones[n] for chain in profile['control_chains'] for n in chain];results=[]
for row in report['unresolved_frames']:
 frame=row['frame'];ad.use_nla=False;ad.action=original;bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();solver.capture();base=[b.rotation_quaternion.copy() for b in bones]
 x,detail=solver.solve(preferred=np.array(report['bake'][frame-1]['offsets']),iterations=35)
 qdelta=[]
 for b,q0 in zip(bones,base):
  q=q0.inverted()@b.rotation_quaternion
  if q.w<0:q.negate()
  qdelta.append(q)
 ad.action=delta
 for b,q in zip(bones,qdelta):b.rotation_quaternion=q;b.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=b.name)
 results.append({'frame':frame,'offsets':x.tolist(),**detail})
ad.action=None;ad.use_nla=True;remaining=[];half_fail=[]
for f in np.arange(1,450.001,.5):
 bpy.context.scene.frame_set(int(f),subframe=float(f%1));bpy.context.view_layer.update();audit=audit_frame(mesh,arm,profile,parts,hair=False,cap=2000)
 if audit['ordinary_crossings']:
  row={'frame':float(f),'crossings':audit['ordinary_crossings']};(remaining if f%1==0 else half_fail).append(row)
print('REFINEMENT_RESULT',results,'INTEGER_FAIL',remaining,'HALF_FAIL',half_fail,flush=True)
(out/'refinement.json').write_text(json.dumps({'refined':results,'remaining_integer_frames':remaining,'remaining_half_frames':half_fail,'sample_count':899,'not_ccd':True},ensure_ascii=False,indent=2),encoding='utf8')
bpy.context.scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'BodyContact_Refined.blend'),compress=True)
