"""Local outer-surface clearance using vertex and triangle interior samples."""
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def relax_outside(obj,body,ids,margin=.002,iterations=18):
    body.data.calc_loop_triangles();body_points=[v.co.copy() for v in body.data.vertices]
    triangles=[tuple(t.vertices) for t in body.data.loop_triangles if body.data.materials[t.material_index].mmd_material.name_j=='Body']
    tree=BVHTree.FromPolygons(body_points,triangles,all_triangles=True)
    original=[v.co.copy() for v in obj.data.vertices];points=[p.copy() for p in original];ids=set(ids)
    obj.data.calc_loop_triangles();faces=[tuple(t.vertices) for t in obj.data.loop_triangles if all(i in ids for i in t.vertices)]
    # Coincident base/metal layers must receive exactly the same displacement.
    groups={}
    for i in ids:groups.setdefault(tuple(round(c,6) for c in original[i]),[]).append(i)
    representatives={i:row[0] for row in groups.values() for i in row};last=0
    for iteration in range(iterations):
        moves={i:Vector() for i in ids};counts={i:0 for i in ids};last=0
        def push(p,affected):
            nonlocal last
            hit,n,_,distance=tree.find_nearest(p)
            if hit is None or distance>.075:return
            short=margin-(p-hit).dot(n)
            if short<.00003:return
            last+=1
            d=n*min(short+.0001,.02)
            for i in affected:moves[i]+=d;counts[i]+=1
        for i in ids:push(points[i],(i,))
        for tri in faces:
            a,b,c=(points[i] for i in tri)
            push((a+b+c)/3,tri)
            for k,j in ((0,1),(1,2),(2,0)):push((points[tri[k]]+points[tri[j]])*.5,(tri[k],tri[j]))
        for row in groups.values():
            total=sum((moves[i] for i in row),Vector());count=sum(counts[i] for i in row)
            if count:
                d=total/count
                for i in row:points[i]+=d
        if not last:break
    deltas=[p-q for p,q in zip(points,original)]
    for v,p in zip(obj.data.vertices,points):v.co=p
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:
            for i in ids:key.data[i].co+=deltas[i]
    return {'iterations':iteration+1,'unresolved_samples':last,'max_move_m':max((d.length for d in deltas),default=0.),'moved_vertices':sum(d.length>1e-7 for d in deltas)}


def shorten_cap(cloth,arm,components):
    ids={i for p in components for i in p['vertices']};names={g.index:g.name for g in cloth.vertex_groups};deltas={}
    for i in ids:
        vertex=cloth.data.vertices[i];side='L' if vertex.co.x>0 else 'R'
        attached=sum(g.weight for g in vertex.groups if names[g.group].startswith('腕') and names[g.group].endswith('.'+side))
        a=arm.data.bones['腕.'+side].head_local;b=arm.data.bones['ひじ.'+side].head_local;axis=(b-a).normalized();length=(b-a).length;t=(vertex.co-a).dot(axis)
        amount=max(0.,t-length*.5)*.32*attached
        if amount>0:deltas[i]=-axis*amount
    for i,d in deltas.items():cloth.data.vertices[i].co+=d
    if cloth.data.shape_keys:
        for key in cloth.data.shape_keys.key_blocks:
            for i,d in deltas.items():key.data[i].co+=d
    return {'method':'shorten upper-arm cap before elbow crease','vertices':len(deltas),'max_move_m':max((d.length for d in deltas.values()),default=0.)}
