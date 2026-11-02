"""Search bounded rigid hand translations for a legal contact seed.

Keeps source rotations/finger shapes. This is a discrete initialization search,
not CCD, motion solving, or automatic proof of gesture preservation.
"""
import argparse,json,sys,time
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.motion_contact import triangle_crosses,inside_votes
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--frames',nargs='+',type=int,default=[310,325,340]);p.add_argument('--rays',type=int,default=96);p.add_argument('--direction-guide');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=Path(a.input).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
with np.load(folder/'source_hands.npz') as z:d={k:z[k] for k in z.files}
guide=None
if a.direction_guide:
    with np.load(Path(a.direction_guide)/'hand_seeds.npz') as z:guide={k:z[k] for k in z.files}
    guide_local=np.array([d['wrist_matrices'][list(d['frames']).index(f),0,:3,:3].T@v for f,v in zip(guide['frames'],guide['relative_translation'])])
rows={};start=time.perf_counter();displacements=[];results=[]
for frame in a.frames:
    index=list(d['frames']).index(frame);co=d['visible_hand_vertices'][index];left=co[d['ids_L']];right=co[d['ids_R']];remap_l={int(v):i for i,v in enumerate(d['ids_L'])};remap_r={int(v):i for i,v in enumerate(d['ids_R'])};fl=np.array([[remap_l[int(v)] for v in f] for f in d['faces_L']]);fr=np.array([[remap_r[int(v)] for v in f] for f in d['faces_R']]);tree_l=BVHTree.FromPolygons(left.tolist(),fl.tolist(),all_triangles=True)
    def collision(delta,full=False):
        r=right-delta;tree_r=BVHTree.FromPolygons(r.tolist(),fr.tolist(),all_triangles=True);crossings=0
        for i,j in tree_l.overlap(tree_r):
            if triangle_crosses([Vector(v) for v in left[fl[i]]],[Vector(v) for v in r[fr[j]]]):
                crossings+=1
                if not full:return True
        return crossings if full else False
    # Fibonacci sphere plus source wrist axes; deterministic, evenly spread.
    directions=[]
    for i in range(a.rays):
        z=1-2*(i+.5)/a.rays;theta=np.pi*(3-np.sqrt(5))*i;directions.append([np.sqrt(1-z*z)*np.cos(theta),np.sqrt(1-z*z)*np.sin(theta),z])
    for matrix in d['wrist_matrices'][index]:
        for axis in matrix[:3,:3].T:directions.extend((axis,-axis))
    # Preserve the wrist ordering along its original separation vector.
    separation=d['wrist_matrices'][index,0,:3,3]-d['wrist_matrices'][index,1,:3,3]
    directions=[np.asarray(v)/np.linalg.norm(v) for v in directions if np.dot(v,separation)>-.001]
    if guide is not None:
        local=np.array([np.interp(frame,guide['frames'],guide_local[:,i]) for i in range(3)]);direction=d['wrist_matrices'][index,0,:3,:3]@local;directions=[direction/np.linalg.norm(direction)]
    best=None;attempts=0
    for direction in directions:
        bound=min(.08,best[0] if best else .08);previous=0.;found=None
        for distance in np.arange(.004,bound+.004,.004):
            if distance>bound+.00001:break
            attempts+=1
            if not collision(direction*distance):found=distance;break
            previous=distance
        if found is None:continue
        lo,hi=previous,found
        for _ in range(9):
            mid=(lo+hi)*.5
            if collision(direction*mid):lo=mid
            else:hi=mid
        # A small additional opening avoids accepting a zero-thickness touch.
        candidate=hi+.0015
        if collision(direction*candidate):continue
        if best is None or candidate<best[0]:best=(candidate,direction)
    if best is None:
        (out/'seed_report.json').write_text(json.dumps({'status':'CONTACT_SEED_SEARCH_FAILED','failed_frame':frame,'completed_frames':rows,'actual_rig_applied':False,'gesture_accepted':False,'error':'No bounded seed on the proposed direction; interpolation between legal keyposes may cross an obstacle'},indent=2),encoding='utf-8')
        raise RuntimeError(f'No bounded source-orientation contact seed at frame {frame}')
    delta=best[0]*best[1];l=left+delta*.5;r=right-delta*.5;tl=BVHTree.FromPolygons(l.tolist(),fl.tolist(),all_triangles=True);tr=BVHTree.FromPolygons(r.tolist(),fr.tolist(),all_triangles=True)
    # Independent sparse containment diagnostic, never used to hide pairs.
    contained=0
    for mesh,tree in ((l,tr),(r,tl)):
        for v in mesh[::max(1,len(mesh)//80)]:
            q,n,i,dist=tree.find_nearest(Vector(v))
            if dist>.0001 and inside_votes(tree,Vector(v)):contained+=1
    closest=(float('inf'),None,None)
    for s,tree,reverse in ((l,tr,False),(r,tl,True)):
        for v in s:
            q,n,i,dist=tree.find_nearest(Vector(v))
            if q is not None and dist<closest[0]:closest=(float(dist),list(q) if reverse else v.tolist(),v.tolist() if reverse else list(q))
    final=co.copy();final[d['ids_L']]+=delta*.5;final[d['ids_R']]-=delta*.5;results.append(final);displacements.append(delta)
    row={'status':'LEGAL_SEED_REQUIRES_RIG_AND_GESTURE_REVIEW' if contained==0 else 'SEED_CONTAINMENT_REJECTED','relative_translation_m':delta.tolist(),'per_hand_translation_m':float(np.linalg.norm(delta)*.5),'rotation_change_rad':0.,'source_hand_crossings':int(collision(np.zeros(3),True)),'seed_hand_crossings':int(collision(delta,True)),'sparse_containment_samples':contained,'nearest_vertex_surface_gap_m':closest[0],'contact_points':closest[1:],'collision_queries':attempts}
    rows[str(frame)]=row;print('HAND_SEED',frame,json.dumps(row),flush=True)
np.savez_compressed(out/'hand_seeds.npz',frames=np.array(a.frames),relative_translation=np.array(displacements),hand_vertices=np.array(results),source_frames=d['frames'],source_vertices=d['visible_hand_vertices'],ids_L=d['ids_L'],ids_R=d['ids_R'],faces_L=d['faces_L'],faces_R=d['faces_R'])
report={'status':'STATIC_HAND_SEEDS_ONLY_NOT_MOTION_ACCEPTANCE','seconds':time.perf_counter()-start,'frames':rows,'preserves_source_finger_channels':True,'changes_mesh_coordinates_in_source':False,'continuous_collision_detection':False,'actual_rig_applied':False,'gesture_accepted':False};(out/'seed_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
