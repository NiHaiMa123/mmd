import sys,json,argparse
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions
from animation_contact_tools.track import solve_track
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--profile',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.source).resolve()),load_ui=False,use_scripts=False)
profile=json.loads(Path(a.profile).read_text('utf8'));mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(mesh,arm,profile)
out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);report=solve_track(mesh,arm,profile,parts,out)
bpy.context.scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'BodyContact_Candidate.blend'),compress=True)
(out/'rig_profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf8');print('BODY_TRACK_COMPLETE',report['status'],report['result_crossings_sum'],flush=True)
