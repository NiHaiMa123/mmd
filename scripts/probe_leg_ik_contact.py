import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame,coords
from animation_contact_tools.ik_projector import FootProjector
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'joint_diagnosis'
bpy.ops.wm.open_mainfile(filepath=str(root/'body_track/BodyContact_FinalCandidate.blend'),load_ui=False,use_scripts=False)
p=json.loads((root/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);rows=[]
for f in (220,240,361):
 bpy.context.scene.frame_set(f);bpy.context.view_layer.update();before=audit_frame(mesh,arm,p,parts,hair=False,cap=2000);co=coords(mesh);ids=parts['ids']['torso']+parts['ids']['head']
 solver=FootProjector(mesh,arm,p,parts,['左足ＩＫ','右足ＩＫ'],max_offset_m=.04);solver.capture();x,result=solver.solve(iterations=40);result.update(frame=f,before=sum(r['triangle_crossings'] for r in before['pairs'] if r['pair'][0].startswith('leg')),offsets=x.tolist(),primary_surface_max_error_m=float(np.max(np.abs(coords(mesh)[ids]-co[ids]))));rows.append(result);print('LEG_IK_PROBE',json.dumps(result),flush=True)
(out/'leg_ik_probes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
