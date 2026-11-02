import sys,json,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
from mmd_hair_dynamics.dynamics import DynamicsSession
s=DynamicsSession(sys.argv[1]);print('INITIAL',s.solver.metrics(),flush=True)
if '--no-extra' in sys.argv:s.solver.margin_extra.zero_()
if '--no-material' in sys.argv:s.solver.dynamic_edges=[];s.solver.bend_groups=[]
for k in range(121):
 if k:
  if '--static' not in sys.argv:s._predict(s.dt)
  s._project(32)
  if '--static' not in sys.argv:s._velocity(s.dt)
 if k%5==0:
  x=s.solver.positions();e=s.edges;ref=s.solver.rest;l=np.linalg.norm(ref[e[:,0]]-ref[e[:,1]],axis=1);good=l>.0005;r=np.linalg.norm(x[e[:,0]]-x[e[:,1]],axis=1)/np.maximum(l,1e-20);worst=np.flatnonzero(good)[np.argsort(r[good])[-5:]]
  print(k,s.solver.metrics(),'WORST',[(int(i),e[i].tolist(),float(r[i]),float(l[i]),s.hard[e[i]].tolist()) for i in worst],flush=True)
  if r[good].max()>1.3:np.savez(Path(sys.argv[2]),positions=x,velocities=s.solver.v.numpy());break
