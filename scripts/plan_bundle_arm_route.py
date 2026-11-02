import sys,json
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions
from animation_contact_tools.arm_detour_planner import plan_arm_detour
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=base/'hair_arm_feedback_20261028/planned_route';out.mkdir(exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(base/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);p=json.loads((base/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);pairs=[]
for a,b in p['pairs']:
 if a in ('arm.R','hand.R'):pairs.append([a,b])
 elif b in ('arm.R','hand.R'):pairs.append([b,a])
p.update(pairs=pairs,control_chains=[p['control_chains'][1]])
env=json.loads((base/'hair_arm_feedback_20261028/root_contact_diagnosis.json').read_text('utf8'));env.update(moving_regions=['arm.R','hand.R'],hand_region='hand.R');result=plan_arm_detour(mesh,arm,p,parts,env,list(range(212,229)),out);print('ARM_ROUTE_PLANNED',[(r['frame'],r['offset']) for r in result['waypoints']],flush=True)
