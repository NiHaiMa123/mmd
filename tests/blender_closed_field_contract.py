"""Closed-union sign queries survive reversed normals and overlapping solids."""
import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.closed_collider_field import ClosedColliderField
bpy.ops.wm.read_factory_settings(use_empty=True);vertices=[];faces=[]
for center in [(0,0,0),(.8,0,0)]:
 bpy.ops.mesh.primitive_cube_add(size=2,location=center);o=bpy.context.object;offset=len(vertices);vertices.extend([tuple(o.matrix_world@v.co) for v in o.data.vertices]);faces.extend([tuple(offset+i for i in reversed(p.vertices)) for p in o.data.polygons])
field=ClosedColliderField(vertices,faces);points=np.array([[3.,0,0],[0,0,0],[.4,.2,0],[-1.1,0,0],[0,0,2.]]);d,n=field(points)
assert (d<0).tolist()==[False,True,True,False,False],d
np.testing.assert_allclose(np.linalg.norm(n,axis=1),1.,atol=1e-6)
d2,_=field(points+np.array([.00001,0,0]));assert (d2<0).tolist()==(d<0).tolist();assert field.sign_reuses==len(points)
from mathutils.bvhtree import BVHTree
class RepeatingNearHit:
 def __init__(self,tree):self.tree=tree;self.last=None;self.repeats=0
 def ray_cast(self,origin,direction,distance):
  if self.last is not None and (origin-self.last[0]).length<6e-6:
   self.repeats+=1;return self.last[0],self.last[1],self.last[2],0.
  result=self.tree.ray_cast(origin,direction,distance)
  if result[0] is not None:self.last=result
  return result
progress=ClosedColliderField(vertices,faces);wrappers=[]
for component in progress.components:
 wrapper=RepeatingNearHit(BVHTree.FromPolygons(vertices,component['faces']));component['tree']=wrapper;wrappers.append(wrapper)
dp,_=progress(points);assert (dp<0).tolist()==(d<0).tolist(),dp
assert sum(w.repeats for w in wrappers)>0
out=ROOT/'outputs/closed_field_contract';out.mkdir(parents=True,exist_ok=True);r={'status':'REVERSED_NORMALS_OVERLAPPING_SOLIDS_SIGN_CACHE_AND_RAY_PROGRESS_PASS','components':len(field.components),'sign_cache_reuses':field.sign_reuses,'repeated_hit_recoveries':sum(w.repeats for w in wrappers)};(out/'report.json').write_text(json.dumps(r),encoding='utf8');print('CLOSED_FIELD_CONTRACT',json.dumps(r),flush=True)
