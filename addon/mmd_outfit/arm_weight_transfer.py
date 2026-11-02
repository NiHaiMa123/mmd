"""Transfer the attached sleeve mass to target arm weights, keep cloth chains."""
from collections import defaultdict
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform


def apply(cloth,body,arm,components):
    source_names={g.index:g.name for g in cloth.vertex_groups};target_names={g.index:g.name for g in body.vertex_groups};body.data.calc_loop_triangles();points=[v.co.copy() for v in body.data.vertices]
    reports=[]
    for side in ('L','R'):
        def attached(name):return name.endswith('.'+side) and name.startswith(('腕','肩'))
        body_ids={v.index for v in body.data.vertices if sum(g.weight for g in v.groups if attached(target_names[g.group]))>.25}
        triangles=[t for t in body.data.loop_triangles if body.data.materials[t.material_index].mmd_material.name_j=='Body' and sum(i in body_ids for i in t.vertices)>=2]
        tree=BVHTree.FromPolygons(points,[tuple(t.vertices) for t in triangles],all_triangles=True);changed=0;max_distance=0.;max_influences=0
        ids={i for p in components if p['side']==side for i in p['vertices']}
        for i in ids:
            v=cloth.data.vertices[i];before={source_names[g.group]:g.weight for g in v.groups if source_names[g.group] in arm.data.bones and g.weight>1e-7};amount=sum(w for name,w in before.items() if attached(name))
            if amount<1e-5:continue
            hit,_,ti,distance=tree.find_nearest(v.co)
            if hit is None or distance>.13:continue
            triangle=triangles[ti];bary=barycentric_transform(hit,*(points[j] for j in triangle.vertices),Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))
            target=defaultdict(float)
            for bi,bw in zip(triangle.vertices,bary):
                for g in body.data.vertices[bi].groups:
                    name=target_names[g.group]
                    if name not in arm.data.bones:continue
                    if name.startswith(('ひじ','手捩')):name='腕.'+side
                    target[name]+=g.weight*max(0.,bw)
            total=sum(target.values())
            if not total:continue
            after={name:w for name,w in before.items() if not attached(name)}
            for name,w in target.items():after[name]=after.get(name,0.)+amount*w/total
            after=sorted(after.items(),key=lambda item:-item[1])[:4];total=sum(w for _,w in after)
            for name in before:cloth.vertex_groups[name].remove([i])
            for name,w in after:
                group=cloth.vertex_groups.get(name) or cloth.vertex_groups.new(name=name);group.add([i],w/total,'REPLACE')
            changed+=1;max_distance=max(max_distance,distance);max_influences=max(max_influences,len(after))
        reports.append({'side':side,'vertices':changed,'max_reference_distance_m':max_distance,'max_bone_influences':max_influences})
    return {'method':'target upper-arm barycentric weights; source dynamic mass retained','sides':reports}
