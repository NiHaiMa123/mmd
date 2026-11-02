"""Model-specific, measured radial skirt initialization against outer colliders.

Only the first simulation-proxy sample changes. Body and later motion samples
are preserved. Native validation is still required; this script never accepts
an outfit on the basis of vertex clearance alone.
"""
import sys,json,argparse
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.motion_contact import triangle_crosses
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--gap',type=float,default=.006);p.add_argument('--reach',type=float,default=.025);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);source=Path(a.input).resolve();out=source.parent/(source.name+'_skirt_envelope');out.mkdir(exist_ok=True)
with np.load(source/'trajectories.npz') as archive:data={k:archive[k] for k in archive.files}
cloth=data['cloth'][0].copy();faces=data['cloth_faces'];body=data['body'][0];body_faces=data['body_faces'];parent=list(range(len(cloth)))
def root(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
for f in faces:
    for i in f[1:]:parent[root(int(i))]=root(int(f[0]))
components=[np.array([i for i in range(len(cloth)) if root(i)==r]) for r in sorted({root(i) for i in range(len(cloth))})]
# This recipe requires two skirt islands spanning the character centre and
# two sleeves on the sides. Refuse a different model layout.
skirts=[ids for ids in components if cloth[ids,0].min()<-.05 and cloth[ids,0].max()>.05 and cloth[ids,2].max()<1.2]
if len(components)!=4 or len(skirts)!=2:raise ValueError('Expected this model\'s two skirt islands and two sleeves')
skirts.sort(key=lambda ids:float(cloth[ids,2].max()))
tree=BVHTree.FromPolygons(body.tolist(),body_faces.tolist(),all_triangles=True);centre=np.array([0.,.06]);hits=0;changes=[]
for layer,ids in enumerate(skirts):
    for i in ids:
        xy=cloth[i,:2]-centre;radius=float(np.linalg.norm(xy))
        if radius<1e-5:continue
        # A distant sleeve/ribbon is not an enclosing torso envelope. Restrict
        # this placement heuristic to a small neighbourhood; subsequent native
        # checks still include the WHOLE collision surface, without exemptions.
        direction=xy/radius;origin=Vector((*(centre+direction*(radius+a.reach)),float(cloth[i,2])))
        hit,normal,fi,distance=tree.ray_cast(origin,Vector((-direction[0],-direction[1],0)),radius+a.reach)
        if hit is None:continue
        hits+=1;outer=float(np.dot(np.array(hit)[:2]-centre,direction));new_radius=max(radius,outer+a.gap*(layer+1))
        cloth[i,:2]=centre+direction*new_radius;changes.append(new_radius-radius)
def crossings(co1,f1,co2,f2,self_test=False):
    b1=BVHTree.FromPolygons(co1.tolist(),f1.tolist(),all_triangles=True);b2=b1 if self_test else BVHTree.FromPolygons(co2.tolist(),f2.tolist(),all_triangles=True);count=0
    for ia,ib in b1.overlap(b2):
        if self_test and (ia>=ib or set(f1[ia])&set(f2[ib])):continue
        if triangle_crosses([Vector(v) for v in co1[f1[ia]]],[Vector(v) for v in co2[f2[ib]]]):count+=1
    return count
report=dict(status='INITIALIZATION_CANDIDATE_NOT_NATIVE_VALIDATED',radial_axis_xy_m=centre.tolist(),layer_clearance_m=a.gap,radial_search_reach_m=a.reach,ray_hits=hits,max_vertex_move_m=float(np.linalg.norm(cloth-data['cloth'][0],axis=1).max()),body_and_later_motion_samples_changed=False,cloth_collider_true_crossings=crossings(cloth,faces,body,body_faces),cloth_self_true_crossings=crossings(cloth,faces,cloth,faces,True))
rejected=bool(report['cloth_collider_true_crossings'] or report['cloth_self_true_crossings'])
if rejected:report['status']='REJECTED_INITIAL_INTERSECTIONS'
report['accepted_as_valid_solver_input']=False  # Even zero here needs native validation.
data['cloth'][0]=cloth;np.savez_compressed(out/('rejected_trajectories.npz' if rejected else 'trajectories.npz'),**data)
if rejected and (out/'trajectories.npz').is_file():(out/'trajectories.npz').unlink()
manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'));manifest['skirt_initialization']=report;(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');(out/'skirt_initialization.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('SKIRT_INITIALIZATION',json.dumps(report),flush=True)
