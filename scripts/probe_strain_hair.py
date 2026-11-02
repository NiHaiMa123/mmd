import sys,json,time,argparse
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords,audit_frame
from animation_contact_tools.strain_hair import StrainHairProjector
parser=argparse.ArgumentParser();parser.add_argument('--frames',type=int,nargs='+',default=[1,240]);parser.add_argument('--scale',type=float,default=.03);parser.add_argument('--all-targets',action='store_true');parser.add_argument('--analytic',action='store_true');parser.add_argument('--tag',default='bone_strain');options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'hair_tests_v2'/options.tag;out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(root/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);p=json.loads((root/'body_track/rig_profile.json').read_text('utf8'));p['hair_strain_scale_m']=options.scale;p['hair_analytic_jacobian']=options.analytic
if not options.all_targets:p['hair_collision_targets']=['torso','arm.L','arm.R','hand.L','hand.R','leg.L','leg.R']
mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);solver=StrainHairProjector(mesh,arm,p,parts,limit_degrees=30,max_active=18);rows=[]
for frame in options.frames:
 # Hair controls have no imported VMD channels; explicitly reset the previous
 # experimental pose before taking the next source-frame reference.
 for bone in solver.bones:bone.rotation_quaternion=(1,0,0,0)
 bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();solver.capture();base=coords(mesh);skin=sorted(set(range(len(base)))-set(parts['ids']['hair_root']+parts['ids']['hair_mobile']));start=time.monotonic();x,result=solver.solve(iterations=60);co=coords(mesh);result.update(frame=frame,seconds=time.monotonic()-start,body_max_error_m=float(np.max(np.abs(co[skin]-base[skin]))));rows.append(result);np.savez_compressed(out/f'frame{frame:04}.npz',coordinates=co,offsets=x);print('STRAIN_HAIR_RESULT',json.dumps(result),flush=True);(out/'probe.json').write_text(json.dumps({'samples':rows,'accepted_as_full_hair_fix':False},ensure_ascii=False,indent=2),encoding='utf8')
(out/'rig_profile.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
