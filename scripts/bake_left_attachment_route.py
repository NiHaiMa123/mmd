import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions
from animation_contact_tools.arm_route_bake import bake_arm_route
parser=argparse.ArgumentParser();parser.add_argument('--route-dir',default='left_arm_feedback_refined');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029/multi_bundle';directory=root/args.route_dir;source=json.loads((directory/'source.json').read_text('utf8'))['source'];profile=json.loads((directory/'profile.json').read_text('utf8'));envelope=json.loads((directory/'envelope.json').read_text('utf8'));initial=np.load(root/'left_native/initial_projection.npz');envelope.setdefault('attachment_points',initial['coordinates'][initial['pinned']].tolist());(directory/'envelope.json').write_text(json.dumps(envelope,ensure_ascii=False,indent=2),encoding='utf8');route=json.loads((directory/'planned_route.json').read_text('utf8'))['waypoints'];engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=source,load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];result=bake_arm_route(mesh,arm,profile,regions(mesh,arm,profile),route,envelope,directory/'baked');(directory/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('LEFT_ARM_BAKED',json.dumps({k:v for k,v in result.items() if k!='samples'}),flush=True)
