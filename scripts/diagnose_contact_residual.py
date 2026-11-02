import sys,json,math
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame,coords
from animation_contact_tools.projector import FrameProjector
from animation_contact_tools.track import fcurves
from mathutils import Quaternion
engine('import_export').ensure_mmd_tools();out=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028/body_track'
bpy.ops.wm.open_mainfile(filepath=str(out/'BodyContact_Adaptive.blend'),load_ui=False,use_scripts=False)
p=json.loads((out/'rig_profile.json').read_text('utf8'));r=json.loads((out/'body_track_report.json').read_text('utf8'));arm=bpy.data.objects[p['armature']];mesh=bpy.data.objects[p['mesh']];parts=regions(mesh,arm,p)
bpy.context.scene.frame_set(361);bpy.context.view_layer.update();audit=audit_frame(mesh,arm,p,parts,hair=False,cap=2000)
print('RESIDUAL_PAIRS',json.dumps([row for row in audit['pairs'] if row['triangle_crossings']],ensure_ascii=False),flush=True)
ad=arm.animation_data;original=bpy.data.actions[r['original_action']];delta=bpy.data.actions[r['correction_action']]
lookup={(c.data_path,c.array_index):c for c in fcurves(delta)};seed=[]
solver=FrameProjector(mesh,arm,p,parts,p['control_chains'],limit_degrees=25)
for bone in solver.bones:
 q=Quaternion([lookup[bone.path_from_id('rotation_quaternion'),i].evaluate(361) for i in range(4)]);q.normalize();seed.extend(q.to_exponential_map())
ad.use_nla=False;ad.action=original;bpy.context.scene.frame_set(361);bpy.context.view_layer.update();solver.capture()
trials=[];rng=np.random.default_rng(37)
for i in range(9):
 initial=np.array(seed) if i==0 else np.zeros(solver.n) if i==1 else np.array(seed)+rng.normal(0,math.radians(5),solver.n)
 x,detail=solver.solve(initial=initial,preferred=seed,iterations=60)
 trials.append({'trial':i,'x':x.tolist(),**detail});print('RESIDUAL_TRIAL',i,detail['remaining_crossings'],detail['max_control_delta_deg'],detail['history'][-1:] ,flush=True)
 if detail['remaining_crossings']==0:break
(out/'residual_diagnosis.json').write_text(json.dumps({'audit':audit,'trials':trials},ensure_ascii=False,indent=2),encoding='utf8')
