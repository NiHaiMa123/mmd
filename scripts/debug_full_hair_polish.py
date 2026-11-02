import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
from mmd_hair_dynamics.dynamics import DynamicsSession
s=DynamicsSession(sys.argv[1]);z=np.load(sys.argv[2]);index=int(z['index']);s.index=index;s.solver.body_update(s.body[index]);s.solver.set_target(s.targets(index));s.solver.x.assign(z['positions']);s.solver.v.assign(z['velocities']);print('BEFORE',s.solver.metrics(),flush=True)
for k in range(10):
 s.solver.project(iterations=128,margin=.0005,lo=.9,hi=1.1,triangles=True,max_displacement=.25,material=False);m=s.solver.metrics();print(k,m,flush=True)
 if m['min_edge_ratio']>=.8995 and m['max_edge_ratio']<=1.1005:break
