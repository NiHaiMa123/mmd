"""Current character adapter for bounded conservative-clump arm feedback."""
import json,sys,argparse
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions
from animation_contact_tools.hair_bundle_profile import resolve_bundle
from animation_contact_tools.clump_detour import solve_clump_detour
p=argparse.ArgumentParser();p.add_argument('--first',type=int,default=240);p.add_argument('--last',type=int,default=252);p.add_argument('--tag',default='conservative_clump_best_refined');p.add_argument('--wrist-limit',type=float,default=5.);p.add_argument('--best-only',action='store_true');p.add_argument('--quick-wide',action='store_true');p.add_argument('--wide-best',action='store_true');p.add_argument('--wide-alternate',action='store_true');p.add_argument('--refine-wide',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029';source=base/'multi_bundle/left_arm_feedback_rig_roots/baked/Body_With_Attachment_Detour.blend';profile=json.loads((base/'multi_bundle/left_arm_feedback_rig_roots/profile.json').read_text('utf8'));config=json.loads((base/'multi_bundle/bundle_L_rig_roots.json').read_text('utf8'));initial=np.load(base/'multi_bundle/left_rig_root_native/initial_projection.npz');engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];profile['auxiliary_twist_bones']=[b.name for b in arm.pose.bones[profile['control_chains'][0][2]].parent_recursive if '捩' in b.name and not b.constraints];bundle=resolve_bundle(mesh,arm,regions(mesh,arm,profile),config);out=base/'surface_proxy_20261029'/a.tag;extra=dict(wrist_polish_limit_degrees=a.wrist_limit)
if a.best_only:extra.update(amplitudes=(.05,),directions=[[-1.,-1.,0.]],swivels=(-.35,))
else:extra['swivels']=(0.,-.35,.35)
if a.quick_wide:extra.update(amplitudes=(.1,.125),refinement_iterations=0)
if a.wide_best:extra.update(amplitudes=(.1,),directions=[[-1.,0.,1.]],swivels=(0.,),refinement_iterations=0,joint_limit_degrees=45.)
if a.wide_alternate:extra.update(amplitudes=(.1,),directions=[[-1.,-1.,1.]],swivels=(.35,),refinement_iterations=0,joint_limit_degrees=55.)
if a.refine_wide:extra['refinement_iterations']=24
r=solve_clump_detour(mesh,arm,profile,bundle,initial['coordinates'],out,a.first,a.last,ramp=3.,**extra);r['source']=str(source);r['rig_profile']=profile;r['bundle']=config;(out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');print('CLUMP_DETOUR_COMPLETE',json.dumps({k:v for k,v in r.items() if k not in ('samples','rig_profile','bundle')}),flush=True)
