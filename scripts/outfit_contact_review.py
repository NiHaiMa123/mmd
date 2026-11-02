"""Compare texture-aware contacts with raw geometry on the same motion frames."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json

parser=argparse.ArgumentParser()
parser.add_argument('--job',required=True)
parser.add_argument('--out',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
job=Path(args.job).resolve()
result,request=read_json(job/'result.json'),read_json(job/'request.json')
profile=read_json(job/'profile_snapshot.json')
ie,qa=engine('import_export'),engine('qa')
ie.clear_scene()
objects=ie.import_pmx(result['pmx'])
report=qa.motion_check(objects,result.get('effective_motion') or request['motion'],profile['selected_materials'])
out=Path(args.out).resolve()
out.mkdir(parents=True,exist_ok=True)
write_json(out/'report.json',report)
print('CONTACT_REVIEW', {k:report.get(k) for k in ('max_ratio','pierced_by_region','visibility_filter')},flush=True)
