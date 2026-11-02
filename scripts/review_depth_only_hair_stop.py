"""Read-only independent geometry reviews on an already stopped native cache."""
import argparse,json,runpy,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--run',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(__file__).resolve().parent;run=Path(a.run)
r=json.loads((run/'result.json').read_text('utf8'))
jobs=[('review_classic_full_hair_stop.py',['--run',str(run)]),
      ('audit_local_surface_native_stop.py',['--run',str(run)]),
      ('measure_full_hair_intrusion.py',['--source',r['blend'],'--out',str(run/'independent_intrusion'),'--frames','331,346,352'])]
for script,args in jobs:
 print('READ_ONLY_REVIEW_BEGIN',script,flush=True)
 sys.argv=[str(root/script),'--']+args
 runpy.run_path(str(root/script),run_name='__main__')
 print('READ_ONLY_REVIEW_DONE',script,flush=True)
