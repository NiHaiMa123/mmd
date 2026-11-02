import sys,json,argparse
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.hair_track import solve_hair_track
parser=argparse.ArgumentParser();parser.add_argument('--tag',default='continuation_track');parser.add_argument('--step',type=int,default=3);parser.add_argument('--keep-contacts',action='store_true');options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'hair_tests_v2'/options.tag;out.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(root/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);p=json.loads((root/'body_track/rig_profile.json').read_text('utf8'));p.update(hair_collision_targets=['torso','arm.L','arm.R','hand.L','hand.R','leg.L','leg.R'],hair_strain_scale_m=.03,hair_allow_arm_feedback=True,hair_extra_frames=[1,100,226,240,285,361,450],hair_keep_contacts=options.keep_contacts,hair_contact_constraint_limit=800 if options.keep_contacts else 300);mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']]
result=solve_hair_track(mesh,arm,p,out,step=options.step);(out/'rig_profile.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8');print('HAIR_CONTINUATION_RESULT',result['layer_max_error_m'],result['primary_bone_matrix_error'],flush=True);bpy.context.scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'HairContact_ContinuationCandidate.blend'),compress=True)
