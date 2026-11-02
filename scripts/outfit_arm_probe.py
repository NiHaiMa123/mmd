"""Try the arm envelope on a saved fitted copy before changing a preset."""
import argparse
from pathlib import Path
import sys
import bpy
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'addon'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
from experimental_arm_envelope import fit
parser=argparse.ArgumentParser(); parser.add_argument('--job',required=True); parser.add_argument('--out',required=True)
parser.add_argument('--component',action='store_true')
parser.add_argument('--tailoring',action='store_true')
parser.add_argument('--radial-scale',type=float,default=1.7)
parser.add_argument('--axial-scale',type=float,default=.78)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]); job=Path(args.job); out=Path(args.out).resolve(); out.mkdir(parents=True,exist_ok=True)
result,request,profile=[read_json(job/n) for n in ('result.json','request.json','profile_snapshot.json')]
ie,dressing,garment=[engine(n) for n in ('import_export','dressing','garment')]
ie.ensure_mmd_tools(); bpy.ops.wm.open_mainfile(filepath=result['blend'])
meshes=ie.model_meshes(); cloth=next(o for o in meshes if o.get('mmd_garment')); body=next(o for o in meshes if o is not cloth)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
settings={'materials':['新規','服','服+jinshu'],'skin_materials':['Body'],'clearance':.004,
          'max_distance':.04,'max_displacement':.025,'iterations':6,'subdivide':1,'max_edge':.015}
if args.tailoring:
    from experimental_sleeve_tailoring import fit as tailor
    report=tailor(cloth,arm,read_json(ROOT/'outputs/outfit_v08_arm_inventory.json')['components'],dressing.apply_positions,
                  radial_scale=args.radial_scale,axial_scale=args.axial_scale)
elif args.component:
    from experimental_arm_cuffs import fit as component_fit
    report=component_fit(cloth,body,arm,settings,dressing.apply_positions)
else:
    report=fit(cloth,body,arm,settings,dressing.apply_positions, dressing.subdivide_triangles)
write_json(out/'arm_clearance.json',report)
blend=out/'work.blend'; pmx=out/'model.pmx'
bpy.ops.wm.save_as_mainfile(filepath=str(blend)); ie.export_pmx(str(pmx))
result.update(blend=str(blend),pmx=str(pmx)); result.setdefault('adaptations',{})['arm_clearance']=report
write_json(out/'result.json',result);write_json(out/'request.json',request);write_json(out/'profile_snapshot.json',profile)
print('ARM_PROBE',report,flush=True)
