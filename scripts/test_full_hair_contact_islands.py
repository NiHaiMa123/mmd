exec(open(str(__import__('pathlib').Path(__file__).with_name('test_partitioned_full_hair_contact.py')),encoding='utf8').read().split('for j in range(16):')[0])
from mmd_hair_dynamics.contact_islands import ContactIslandProjector
projector=ContactIslandProjector(s.solver)
for j in range(12):
 print('ISLAND',j,projector.project(),flush=True);s.solver.project(iterations=512,margin=.0005,lo=.905,hi=1.095,triangles=True,max_displacement=.25,material=False);m=s.solver.metrics();print('AFTER',j,m,s.solver.body_crossings(),flush=True)
 if m['inside_vertices']==0 and s.solver.body_crossings()[0]==0 and m['min_edge_ratio']>=.8995 and m['max_edge_ratio']<=1.1005:break
