exec(open(str(__import__('pathlib').Path(__file__).with_name('debug_full_hair_preroll.py')),encoding='utf8').read().split('for k in range(121):')[0])
import warp as wp
from mmd_hair_dynamics.gpu_surface import edge_constraints
z=np.load(sys.argv[2]);s.solver.x.assign(z['positions']);s.solver.v.zero_();print('FAILED',s.solver.metrics(),flush=True)
for k in range(5):
 for repeat in range(100):
  for e,l in s.solver.edge_groups:wp.launch(edge_constraints,len(l),inputs=[s.solver.x,s.solver.mass,e,l,.9,1.1,1.0],device=s.solver.device)
 print('EDGES_ONLY',k,s.solver.metrics(),flush=True)
s.solver.project(iterations=1024,margin=.0005,lo=.9,hi=1.1,triangles=True,max_displacement=.25);print('ALL',s.solver.metrics(),flush=True)
