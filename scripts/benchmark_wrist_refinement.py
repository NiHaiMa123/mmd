import sys,json,time
from pathlib import Path
import bpy,numpy as np
from mathutils import Quaternion
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions
from animation_contact_tools.projector import FrameProjector
from animation_contact_tools.track import fcurves
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'body_track'
bpy.ops.wm.open_mainfile(filepath=str(out/'BodyContact_FinalCandidate.blend'),load_ui=False,use_scripts=False)
p=json.loads((out/'rig_profile.json').read_text('utf8'));p['preserve_wrist_orientation']=False;p['pairs']=[pair for pair in p['pairs'] if pair[0].startswith(('arm','hand'))];mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);solver=FrameProjector(mesh,arm,p,parts,p['control_chains'],limit_degrees=30);delta=bpy.data.actions['OrdinaryContact_Delta'];lookup={(c.data_path,c.array_index):c for c in fcurves(delta)};original=bpy.data.actions['シニカルナイトプラン_bone'];ad=arm.animation_data
for f in (1,180,240):
 seed=[]
 for b in solver.bones:
  path=b.path_from_id('rotation_quaternion');q=Quaternion([lookup[path,i].evaluate(f) for i in range(4)]);q.normalize();seed.extend(q.to_exponential_map())
 ad.use_nla=False;ad.action=original;bpy.context.scene.frame_set(f);bpy.context.view_layer.update();solver.capture();start=time.monotonic();x,result=solver.solve(initial=seed,preferred=seed,iterations=35)
 print('WRIST_BENCH',f,time.monotonic()-start,result,flush=True)
