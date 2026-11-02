"""Actual face-interior witnesses produce usable nonvertex contact constraints."""
import json,sys
from pathlib import Path
import numpy as np,bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.projector import FrameProjector
co=np.array([[-.3,-.1,-.02],[.3,-.1,-.02],[0,.3,.02],[-.1,-.2,0],[.1,-.2,0],[0,.2,0]])
solver=FrameProjector.__new__(FrameProjector);solver.parts={'faces':{'arm.L':[(0,1,2)],'head':[(3,4,5)]}};solver.movable_prefixes=('arm','hand');solver.target_regions={'head'};solver.profile={'clearance_m':.001}
row=dict(pair=['arm.L','head'],classification='ordinary_collision',triangle_crossings=1,contained_samples=0,moving_vertices=[],target_vertices=[],witness_pairs=[([0,1,2],[3,4,5])])
cs=solver.constraints({'pairs':[row]},co)
assert len(cs)>=2,len(cs)
features=solver.features(co,cs)
assert np.max(np.abs(features))<1e-6
assert any(sum(w>1e-5 for w in c[1])>=2 for c in cs)
perturbed=co.copy();perturbed[:3,2]+=.002
change=np.einsum('ij,ij->i',solver.features(perturbed,cs)-features,np.array([c[-2] for c in cs]))
np.testing.assert_allclose(change,.002,atol=1e-7)
assert not solver.constraints({'pairs':[dict(row,witness_pairs=[])]},co)
result=dict(status='INTERIOR_INTERSECTION_BARYCENTRIC_CONTACT_DERIVATIVE_PASS',witness_constraints=len(cs),maximum_feature_error_m=float(np.max(np.abs(features))))
(ROOT/'outputs/interior_contact_contract.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
