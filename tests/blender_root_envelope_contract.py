"""Independent geometry/trajectory contracts for root-envelope feedback."""
import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.root_envelope_feedback import cubic_basis,capsule_features
from animation_contact_tools.arm_detour_planner import interpolate_waypoints
centres=[12,18,24];width=6.;values=np.array([cubic_basis(f,centres,width) for f in np.linspace(0,36,721)])
assert values.min()>=0 and values.sum(1).max()<=1+1e-12
assert np.max(np.abs(cubic_basis(-1,centres,width)))==0 and np.max(np.abs(cubic_basis(37,centres,width)))==0
for f in (0,36):
 eps=1e-3;derivative=(cubic_basis(f+eps,centres,width)-cubic_basis(f-eps,centres,width))/(2*eps);assert np.max(np.abs(derivative))<1e-6
guide=np.array([[0.,0,0],[0,0,1]]);radii=np.array([.1,.1]);points=np.array([[.2,0,.5],[0,.15,.5],[0,0,-.2]])
gap,n=capsule_features(points,guide,radii);np.testing.assert_allclose(gap,[.1,.05,.1],atol=1e-12);np.testing.assert_allclose(n,[[1,0,0],[0,1,0],[0,0,-1]],atol=1e-12)
shift=np.array([.3,-.5,1.2]);angle=.8;R=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1.]])
newgap,newn=capsule_features(points@R.T+shift,guide@R.T+shift,radii);np.testing.assert_allclose(newgap,gap,atol=1e-12);np.testing.assert_allclose(newn,n@R.T,atol=1e-12)
waypoints=[{'frame':t,'offset':[v,0,0],'swivel':0.} for t,v in [(0,0),(1,.03),(3,.05),(4,.04),(6,0)]]
for w in waypoints:np.testing.assert_allclose(interpolate_waypoints(waypoints,w['frame']),w['offset']+[w['swivel']],atol=1e-12)
sample=np.array([interpolate_waypoints(waypoints,t) for t in np.linspace(0,6,601)]);assert sample[:,0].min()>=0 and sample[:,0].max()<=.05+1e-12
out=ROOT/'outputs/root_envelope_contract';out.mkdir(parents=True,exist_ok=True);result={'status':'CUBIC_BASIS_BOUNDS_AND_CAPSULE_RIGID_INVARIANCE_PASS','mmd_required':False,'physical_hair_acceptance_proven':False};(out/'report.json').write_text(json.dumps(result),encoding='utf8');print('ROOT_ENVELOPE_CONTRACT',json.dumps(result),flush=True)
