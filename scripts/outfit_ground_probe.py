"""Ground a preserved-shoe result motion without altering its PMX."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.jobs import read_json,write_json
from mmd_outfit.service import engine
from mmd_outfit.motion_grounding import ground
parser=argparse.ArgumentParser();parser.add_argument('--job',required=True);parser.add_argument('--out',required=True);parser.add_argument('--lock-shoes',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);job=Path(args.job);out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
result,request,profile=[read_json(job/n) for n in ('result.json','request.json','profile_snapshot.json')]
import bpy
ie=engine('import_export');ie.ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=result['blend'])
cloth=next(o for o in ie.model_meshes() if o.get('mmd_garment'))
start,end=result['adaptations']['shoes']['attached_vertex_range']
reference=[list(cloth.data.vertices[i].co) for i in range(start,end)]
if args.lock_shoes:
    from mmd_outfit.preserved_shoe import lock_vertex_morphs
    report=lock_vertex_morphs(cloth,range(start,end));write_json(out/'shoe_morph_lock.json',report)
    ie.export_pmx(str(out/'model.pmx'));result['pmx']=str(out/'model.pmx')
ie.clear_scene();objects=ie.import_pmx(result['pmx'])
mesh=ie.model_meshes(objects)[0];arm=next(o for o in objects if o.type=='ARMATURE')
report=ground(mesh,arm,request['motion'],out/'grounded.vmd',profile['shoe_fit']['materials'],engine,reference_points=reference,notify=lambda s:print(s,flush=True))
write_json(out/'report.json',report)
print('GROUNDED',{k:v for k,v in report.items() if k!='per_frame'},flush=True)
