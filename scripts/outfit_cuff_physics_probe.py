"""Create a reviewable cuff-physics copy from an existing 0.8 transfer."""
import argparse,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'));sys.path.insert(0,str(ROOT/'scripts'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
from experimental_sleeve_dynamics import fit
p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--out',required=True)
p.add_argument('--start',type=float,default=.55);p.add_argument('--end',type=float,default=.95)
p.add_argument('--gain',type=float,default=.4)
p.add_argument('--ring',action='store_true')
p.add_argument('--production',action='store_true')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);job=Path(a.job).resolve();out=Path(a.out).resolve();(out/'model').mkdir(parents=True,exist_ok=True)
result,request,profile=[read_json(job/n) for n in ('result.json','request.json','profile_snapshot.json')]
ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=result['blend'])
cloth=next(o for o in ie.model_meshes() if o.get('mmd_garment'));arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
if a.production:
    from mmd_outfit.cuff_physics import build
    report=build(cloth,arm,engine('physics'))
elif a.ring:
    from experimental_cuff_ring import fit as ring_fit
    report=ring_fit(cloth,arm,read_json(ROOT/'outputs/outfit_v08_arm_inventory.json')['components'],engine('physics'),start=a.start,end=a.end)
else:
    report=fit(cloth,arm,read_json(ROOT/'outputs/outfit_v08_arm_inventory.json')['components'],engine('physics'),start=a.start,end=a.end,gain=a.gain)
bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'model/work.blend'));ie.export_pmx(str(out/'model/model.pmx'))
result.update(blend=str(out/'model/work.blend'),pmx=str(out/'model/model.pmx'),job_dir=str(out),accepted=False,state='EXPERIMENTAL')
result.setdefault('adaptations',{})['cuff_physics']=report
for name,value in [('result.json',result),('request.json',request),('profile_snapshot.json',profile),('cuff_physics.json',report)]:write_json(out/name,value)
write_json(out/'model/manifest.json',read_json(job/'model/manifest.json'))
print('CUFF_PHYSICS_PROBE',report,flush=True)
