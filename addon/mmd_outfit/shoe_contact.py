"""Fit a complete foot inside an explicitly selected, inward-facing shoe lining.

The hard shoe stays rigid. Body/stocking correspondence is supplied by the
caller; seam duplicates share one displacement, including every shape key.
Open edges do not act as an artificial closed shoe cap.
"""
from collections import defaultdict
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def inward_surface(obj, select):
    mesh=obj.data;mesh.calc_loop_triangles()
    points=[obj.matrix_world@v.co for v in mesh.vertices];triangles=[]
    mirrored=obj.matrix_world.determinant()<0
    for t in mesh.loop_triangles:
        ids=list(t.vertices)
        if mirrored:ids.reverse()
        p=[points[i] for i in ids];normal=(p[1]-p[0]).cross(p[2]-p[0]).normalized()
        if select(mesh.materials[t.material_index].name,normal,sum(p,Vector())/3):triangles.append(ids)
    if not triangles:raise ValueError('No inward contact faces on '+obj.name)
    return BVHTree.FromPolygons(points,triangles,all_triangles=True)


def fit_layers(body,cloth,mapping,surfaces,margin=.0012,passes=32,toe_forward=.015):
    groups=defaultdict(list)
    for bi,ci in mapping:groups[tuple(round(c,6) for c in body.data.vertices[bi].co)].append((bi,ci))
    nodes=list(groups.values());lookup={bi:k for k,pairs in enumerate(nodes) for bi,ci in pairs}
    original=np.array([body.data.vertices[pairs[0][0]].co[:] for pairs in nodes],dtype=np.float64)
    offsets=np.array([(cloth.data.vertices[pairs[0][1]].co-body.data.vertices[pairs[0][0]].co)[:] for pairs in nodes])
    neighbors=set()
    for edge in body.data.edges:
        i,j=(lookup.get(k) for k in edge.vertices)
        if i is not None and j is not None and i!=j:neighbors.update(((i,j),(j,i)))
    edge=np.array(sorted(neighbors),dtype=np.int32);degree=np.bincount(edge[:,0],minlength=len(nodes)).clip(1)
    seed=np.zeros_like(original)
    def smooth(x):return np.clip(x,0,1)**2*(3-2*np.clip(x,0,1))
    seed[:,1]=-toe_forward*smooth((-.005-original[:,1])/.04)*smooth((.09-original[:,2])/.03)
    delta=seed.copy();active=original[:,2]<.19
    history=[]
    for iteration in range(passes):
        # Diffuse the displacement, rather than the anatomical surface itself.
        for k in range(8):
            mean=np.zeros_like(delta);np.add.at(mean,edge[:,0],(delta-seed)[edge[:,1]])
            delta=.40*delta+.598*(mean/degree[:,None]+seed)+.002*seed
            delta[~active]=0
        constraints=0;worst=0.
        for idx in np.flatnonzero(active):
            side='L' if original[idx,0]>0 else 'R'
            for tree in surfaces[side]:
                # Both layers are constrained; the stocking normally dominates.
                for offset,clearance in ((offsets[idx],margin),(np.zeros(3),margin)):
                    q=Vector(original[idx]+delta[idx]+offset)
                    hit,normal,face,distance=tree.find_nearest(q)
                    if hit is None or distance>.035:continue
                    signed=(q-hit).dot(normal)
                    tangent=((q-hit)-normal*signed).length
                    if tangent>.001:continue  # open rim, not an interior plane
                    depth=clearance-signed
                    if depth<=0:continue
                    if depth>.035:raise ValueError('Contact displacement exceeds 35 mm')
                    delta[idx]+=np.array(normal)*depth;constraints+=1;worst=max(worst,depth)
        if iteration%4==0 or iteration==passes-1:
            row={'pass':iteration,'active_constraints':constraints,'max_step_m':worst}
            history.append(row);print('SHOE_CONTACT_PASS',row,flush=True)
    max_move=float(np.linalg.norm(delta,axis=1).max())
    if max_move>.045:raise ValueError('Foot fitting exceeds displacement budget: '+str(max_move))
    for k,pairs in enumerate(nodes):
        move=Vector(delta[k])
        for bi,ci in pairs:
            for obj,i in ((body,bi),(cloth,ci)):
                obj.data.vertices[i].co+=move
                if obj.data.shape_keys:
                    for key in obj.data.shape_keys.key_blocks:key.data[i].co+=move
    body.data.update();cloth.data.update()
    return {'unique_positions':len(nodes),'mapped_layer_vertices':len(mapping),'max_displacement_m':max_move,
            'deleted_vertices':0,'deleted_faces':0,'history':history,'margin_m':margin,
            'same_displacement_for_skin_and_stocking':True,'toe_forward_m':toe_forward}
