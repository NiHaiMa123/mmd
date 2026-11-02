import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
from mmd_hair_dynamics.dynamics import DynamicsSession
s=DynamicsSession(sys.argv[1]);z=np.load(sys.argv[2]);k=int(z['index']);s.index=k;s.solver.body_update(s.body[k]);s.solver.set_target(s.targets(k));s.solver.x.assign(z['positions']);s._enable_partitioned();print('PARTS',[(p['name'],p['meta']) for p in s.solver.partitioned.parts],flush=True);print('START',s.solver.metrics(),flush=True)
for j in range(16):
 s.solver.project(iterations=256,margin=.0005,lo=.905,hi=1.095,triangles=True,max_displacement=.25,material=False);m=s.solver.metrics();print(j,m,s.solver.body_crossings(),flush=True)
 if m['inside_vertices']==0 and s.solver.body_crossings()[0]==0 and m['min_edge_ratio']>=.8995 and m['max_edge_ratio']<=1.1005:break
