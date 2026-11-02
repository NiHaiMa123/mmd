import sys,json,argparse
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions
from animation_contact_tools.root_envelope_feedback import solve_root_feedback
parser=argparse.ArgumentParser();parser.add_argument('--tag',default='arm_head_outward_phase');options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=base/'hair_arm_feedback_20261028'/options.tag;out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(base/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);profile=json.loads((base/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(mesh,arm,profile)
pairs=[]
for a,b in profile['pairs']:
 if a in ('arm.R','hand.R'):pairs.append([a,b])
 elif b in ('arm.R','hand.R'):pairs.append([b,a])
profile.update(pairs=pairs,control_chains=[profile['control_chains'][1]],clearance_m=.004)
envelope=json.loads((base/'hair_arm_feedback_20261028/root_contact_diagnosis.json').read_text('utf8'));envelope.update(root_segments=3,moving_regions=['arm.R','hand.R'])
import numpy as np
bpy.context.scene.frame_set(216);bpy.context.view_layer.update();normal=next(r for r in json.loads((base/'hair_arm_feedback_20261028/detour_directions.json').read_text('utf8')) if r['frame']==216)['head_outward'];rotation=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix)[:3,:3];envelope['avoidance_normal_anchor_local']=(np.linalg.inv(rotation)@np.asarray(normal)).tolist();envelope['avoidance_normal_source']='nearest head surface to hair root at approach'
(out/'root_envelope.json').write_text(json.dumps(envelope,ensure_ascii=False,indent=2),encoding='utf8')
result=solve_root_feedback(mesh,arm,profile,parts,envelope,out)
(out/'rig_profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf8');bpy.context.scene.frame_set(218);bpy.ops.wm.save_as_mainfile(filepath=str(out/'Body_With_HairRootFeedback.blend'),compress=True);print('ROOT_FEEDBACK_COMPLETE',result['max_evaluated_control_degrees'],min(r['min_root_gap_m'] for r in result['samples']),flush=True)
