"""Character adapter; all optimization is in the reusable spline module."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions
from animation_contact_tools.hair_bundle_profile import resolve_bundle
from animation_contact_tools.spline_clump_feedback import solve_spline_clump
from animation_contact_tools.root_envelope_feedback import cubic_basis
p=argparse.ArgumentParser();p.add_argument('--tag',default='spline_clump_feedback');p.add_argument('--first',type=int,default=238);p.add_argument('--last',type=int,default=252);p.add_argument('--ramp',type=float,default=5.);p.add_argument('--warm-progress');p.add_argument('--iterations',type=int,default=36);p.add_argument('--verify-step',type=float,default=.0625);a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []);base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029';source=base/'multi_bundle/left_arm_feedback_rig_roots/baked/Body_With_Attachment_Detour.blend';profile=json.loads((base/'multi_bundle/left_arm_feedback_rig_roots/profile.json').read_text('utf8'));config=json.loads((base/'multi_bundle/bundle_L_rig_roots.json').read_text('utf8'));initial=np.load(base/'multi_bundle/left_rig_root_native/initial_projection.npz');engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];profile['auxiliary_twist_bones']=[b.name for b in arm.pose.bones[profile['control_chains'][0][2]].parent_recursive if '捩' in b.name and not b.constraints];bundle=resolve_bundle(mesh,arm,regions(mesh,arm,profile),config);out=base/'surface_proxy_20261029'/a.tag;warm=None
if a.warm_progress:
 checkpoint=json.loads(Path(a.warm_progress).read_text('utf8'));old=np.asarray(checkpoint['coefficients']);warm=old.copy() if old.shape[1]==8 else np.zeros((len(old),8))
 if old.shape[1]==5:warm[:,:4]=old[:,:4];warm[:,6]=old[:,4]
 old_scale=np.asarray(checkpoint.get('parameter_scale',[.02,.02,.02,.2,.25,.25,.3,.3]));warm=warm*old_scale/np.array([.05,.05,.05,.2,.25,.25,.3,.3])
 old_centres=np.asarray(checkpoint.get('centres',np.linspace(a.first+1,a.last-1,len(old))));new_centres=np.linspace(a.first+1,a.last-1,len(old));old_width=checkpoint.get('basis_width',1.25);new_width=float(np.median(np.diff(new_centres)));times=np.linspace(a.first,a.last,225);old_basis=np.array([cubic_basis(t,old_centres,old_width) for t in times]);new_basis=np.array([cubic_basis(t,new_centres,new_width) for t in times]);warm=np.clip(np.linalg.lstsq(new_basis,old_basis@warm,rcond=None)[0],-2,2)
r=solve_spline_clump(mesh,arm,profile,bundle,initial['coordinates'],out,a.first,a.last,np.array([-1.,-1.,1.])*.1/np.sqrt(3),ramp=a.ramp,initial_coefficients=warm,iterations=a.iterations,verification_step=a.verify_step);r['rig_profile']=profile;r['bundle']=config;(out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');print('SPLINE_CLUMP_COMPLETE',json.dumps({k:v for k,v in r.items() if k not in ('samples','history','coefficients','rig_profile','bundle')}),flush=True)
