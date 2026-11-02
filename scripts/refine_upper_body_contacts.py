import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame,DEFAULT_PAIRS
from animation_contact_tools.adaptive import refine_layer
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'body_track'
bpy.ops.wm.open_mainfile(filepath=str(out/'BodyContact_FinalCandidate.blend'),load_ui=False,use_scripts=False)
p=json.loads((out/'rig_profile.json').read_text('utf8'));r=json.loads((out/'body_track_report.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p)
p['preserve_wrist_orientation']=False;p['rotation_limit_degrees']=30;p['local_restart_count']=3;p['pairs']=[pair for pair in DEFAULT_PAIRS if pair[0].startswith(('arm','hand'))]
result=refine_layer(mesh,arm,p,parts,bpy.data.actions[r['original_action']],bpy.data.actions[r['correction_action']],step=.25,passes=3,limit_degrees=30)
(out/'upper_body_refinement.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('UPPER_BODY_RESULT',result['status'],result['remaining'],flush=True)
p['pairs']=DEFAULT_PAIRS;(out/'rig_profile.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8');bpy.context.scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'BodyContact_UpperBodyCandidate.blend'),compress=True)
leg=[]
for b in arm.pose.bones:
 if any(s in b.name for s in ('足','ひざ','つま先')):leg.append({'name':b.name,'parent':b.parent.name if b.parent else None,'constraints':[{'type':c.type,'name':c.name,'influence':c.influence} for c in b.constraints],'weighted_vertices':sum(1 for v in mesh.data.vertices if any(g.group==mesh.vertex_groups[b.name].index and g.weight>.1 for g in v.groups)) if b.name in mesh.vertex_groups else 0})
(root/'joint_diagnosis/leg_controls.json').write_text(json.dumps(leg,ensure_ascii=False,indent=2),encoding='utf8')
