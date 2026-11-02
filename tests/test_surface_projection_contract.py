"""Finite-width sampled contact and hard roots, independent of Blender/MMD."""
import importlib.util,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('surface_projection',ROOT/'addon/animation_contact_tools/surface_contact_projection.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
n=7;rest=np.array([(i*.01,j*.01,0.) for j in range(n) for i in range(n)]);triangles=[]
for j in range(n-1):
 for i in range(n-1):
  a=j*n+i;triangles.extend([(a,a+1,a+n),(a+1,a+n+1,a+n)])
triangles=np.asarray(triangles);edges=np.asarray(sorted({tuple(sorted((int(a),int(b)))) for t in triangles for a,b in zip(t,np.roll(t,1))}));pinned=np.arange(len(rest))<n;target=rest.copy();target[:,2]=-.003;target[pinned,2]=.008
def plane(x):return x[:,2],np.tile([0.,0.,1.],(len(x),1))
result,report=module.project_surface(target,rest,edges,triangles,pinned,plane,margin=.003,strain_limit=.05,iterations=240,target_strength=.001)
assert result[:,2].min()>=.003-1e-5,report
assert report['min_edge_ratio']>=.949 and report['max_edge_ratio']<=1.051,report
np.testing.assert_array_equal(result[pinned],target[pinned]);assert report['max_correction_m']<=.06
groups=module.edge_colours(edges)
assert sum(len(g) for g in groups)==len(edges)
assert all(len(set(edges[g].ravel()))==2*len(g) for g in groups)
rotated=rest.copy();rotated[:,:2]=.06-rest[:,:2];rotated[:,2]=.02;prior=rest.copy();prior[:,2]=.02
def free_space(x):return np.ones(len(x)),np.tile([0.,0.,1.],(len(x),1))
continuous,temporal=module.project_surface(rotated,rest,edges,triangles,np.zeros(len(rest),dtype=bool),free_space,previous_positions=prior,max_displacement=.2,iterations=240,target_strength=.001)
assert temporal['min_temporal_edge_projection_ratio']>.895,temporal
mid=(continuous+prior)/2;ratio=np.linalg.norm(mid[edges[:,0]]-mid[edges[:,1]],axis=1)/np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1);assert ratio.min()>.92,(ratio.min(),temporal)
out=ROOT/'outputs/surface_projection_contract';out.mkdir(parents=True,exist_ok=True);report.update(status='PLANE_CONTACT_EDGE_BOUNDS_ROOT_PINS_AND_TEMPORAL_CONTINUITY_PASS',mmd_required=False,temporal_min_edge_projection_ratio=temporal['min_temporal_edge_projection_ratio'],temporal_midpoint_min_edge_ratio=float(ratio.min()));(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
