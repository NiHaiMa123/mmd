import sys,json,importlib
from pathlib import Path
import bpy,numpy as np
from mathutils import Quaternion
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame,coords
from animation_contact_tools.projector import FrameProjector
pkg=engine('import_export').ensure_mmd_tools();out=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028/body_track'
bpy.ops.wm.open_mainfile(filepath=str(out/'BodyContact_Candidate.blend'),load_ui=False,use_scripts=False)
profile=json.loads((out/'rig_profile.json').read_text('utf8'));report=json.loads((out/'body_track_report.json').read_text('utf8'));arm=bpy.data.objects[profile['armature']];mesh=bpy.data.objects[profile['mesh']];parts=regions(mesh,arm,profile);solver=FrameProjector(mesh,arm,profile,parts,profile['control_chains'])
ad=arm.animation_data;original=bpy.data.actions[report['original_action']]
rows=[]
for frame in [1,100,230,360,361,362]:
 bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();layer_coords=coords(mesh);layer=[b.rotation_quaternion.copy() for b in solver.bones+solver.wrists];layer_audit=audit_frame(mesh,arm,profile,parts,hair=False,cap=2000)
 ad.use_nla=False;ad.action=original;bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();solver.capture();solver.apply(np.array(report['bake'][frame-1]['offsets']));direct=coords(mesh);qa=[b.rotation_quaternion.copy() for b in solver.bones+solver.wrists]
 row={'frame':frame,'max_vertex_error_m':float(np.max(np.abs(layer_coords-direct))),'quat_angle_errors':[layer[i].rotation_difference(qa[i]).angle for i in range(len(qa))],
 'layer_pairs':[(p['pair'],p['triangle_crossings']) for p in layer_audit['pairs'] if p['triangle_crossings']]};print('LAYER_CHECK',json.dumps(row),flush=True);rows.append(row)
 ad.action=None;ad.use_nla=True
(out/'layer_comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
