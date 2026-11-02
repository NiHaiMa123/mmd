"""Run the Blender Bullet proxy continuously, never claim native MMD parity."""
import argparse
from pathlib import Path
import sys
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
parser=argparse.ArgumentParser()
parser.add_argument('--job',required=True)
parser.add_argument('--last-frame',type=int,default=121)
parser.add_argument('--out', help='Separate diagnostic output directory')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
job=Path(args.job).resolve()
result,request=read_json(job/'result.json'),read_json(job/'request.json')
profile=read_json(job/'profile_snapshot.json')
manifest=read_json(job/'model/manifest.json')
ie,qa,render=[engine(n) for n in ('import_export','qa','extraction')]
out=Path(args.out).resolve() if args.out else job/'physics_review'
out.mkdir(exist_ok=True)
ie.clear_scene()
objects=ie.import_pmx(result['pmx'])
groups=list(manifest['physics']['outfit_groups'].values())
report=qa.physics_motion_check(objects,result.get('effective_motion') or request['motion'],profile['selected_materials'],
                              first_frame=1,last_frame=args.last_frame,outfit_groups=groups)
report['scope']='Blender Bullet proxy, not native MMD dynamics acceptance'
write_json(out/'report.json',report)
print('PHYSICS_REVIEW', {k:report.get(k) for k in ('max_ratio','garment_motion','no_motion','proxy_in_leg_total')},flush=True)
render.render_objects(ie.model_meshes(objects),out,width=700,height=900,prefix='physics_last')
