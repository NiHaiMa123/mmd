import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame
from animation_contact_tools.adaptive import refine_layer
engine('import_export').ensure_mmd_tools();out=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028/body_track'
bpy.ops.wm.open_mainfile(filepath=str(out/'BodyContact_Adaptive.blend'),load_ui=False,use_scripts=False)
p=json.loads((out/'rig_profile.json').read_text('utf8'));r=json.loads((out/'body_track_report.json').read_text('utf8'));arm=bpy.data.objects[p['armature']];mesh=bpy.data.objects[p['mesh']];parts=regions(mesh,arm,p)
p['rotation_limit_degrees']=30;p['local_restart_count']=6;p['verification_step']=.25
result=refine_layer(mesh,arm,p,parts,bpy.data.actions[r['original_action']],bpy.data.actions[r['correction_action']],first=357,last=368,step=.125,passes=4,limit_degrees=30)
(out/'local_final_refinement.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('LOCAL_RESULT',result['status'],result['remaining'],flush=True)
remaining=[]
for f in np.arange(1,450.001,.25):
 bpy.context.scene.frame_set(int(f),subframe=float(f%1));bpy.context.view_layer.update();a=audit_frame(mesh,arm,p,parts,hair=False,cap=2000)
 if a['ordinary_crossings'] or a['ordinary_contained_samples']:remaining.append({'frame':float(f),'crossings':a['ordinary_crossings'],'contained':a['ordinary_contained_samples']})
full={'status':'QUARTER_FRAME_BODY_PASS' if not remaining else 'BODY_UNRESOLVED','samples':1797,'remaining':remaining,'not_ccd':True,'rotation_limit_degrees':30}
(out/'final_body_audit.json').write_text(json.dumps(full,ensure_ascii=False,indent=2),encoding='utf8');(out/'rig_profile.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8');print('FULL_RESULT',full,flush=True)
bpy.context.scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'BodyContact_FinalCandidate.blend'),compress=True)
