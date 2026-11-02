"""Coherent placement of detached upper-arm garment components."""
from collections import Counter,defaultdict
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def fit(garment,body,arm,settings,apply_positions):
    def dominant(obj):
        names={g.index:g.name for g in obj.vertex_groups}
        return [max(((e.weight,names[e.group]) for e in v.groups if not names[e.group].startswith('mmd_')),default=(0,''))[1]
                for v in obj.data.vertices]
    dom=dominant(garment); bdom=dominant(body)
    original=[garment.matrix_world@v.co for v in garment.data.vertices]
    points=[p.copy() for p in original]
    parent=list(range(len(points))); positions={}
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]; i=parent[i]
        return i
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[b]=a
    for i,p in enumerate(original):
        key=tuple(round(c,6) for c in p)
        if key in positions: union(i,positions[key])
        else: positions[key]=i
    for face in garment.data.polygons:
        for i in face.vertices[1:]: union(face.vertices[0],i)
    components=defaultdict(list)
    for i in range(len(points)): components[find(i)].append(i)
    face_groups=defaultdict(list)
    for f in garment.data.polygons: face_groups[find(f.vertices[0])].append(f)
    body_points=[body.matrix_world@v.co for v in body.data.vertices]
    reports=[]
    for side in ('L','R'):
        a=arm.matrix_world@arm.data.bones['腕.'+side].head_local
        b=arm.matrix_world@arm.data.bones['ひじ.'+side].head_local
        axis=(b-a).normalized(); length=(b-a).length
        body_faces=[tuple(f.vertices) for f in body.data.polygons if body.data.materials[f.material_index].name in settings.get('skin_materials',['Body'])
                    and sum(bdom[i].endswith('.'+side) and bdom[i][:-2].startswith(('腕','ひじ','手捩')) for i in f.vertices)>=2]
        bvh=BVHTree.FromPolygons(body_points,body_faces)
        def gap(p):
            t=(p-a).dot(axis); center=a+axis*t; radial=p-center
            if radial.length<1e-6: return -.1
            direction=radial.normalized()
            hit,_,_,_=bvh.ray_cast(center+direction*.5,-direction,1.)
            return None if hit is None else radial.length-(hit-center).dot(direction)
        for root,ids in components.items():
            ratio=sum(dom[i].endswith('.'+side) and dom[i].startswith('腕') for i in ids)/len(ids)
            faces=face_groups[root]
            mats={garment.data.materials[f.material_index].name for f in faces}
            if ratio<.6 or len(ids)<12 or not mats.intersection(settings['materials']): continue
            coords=[original[i] for i in ids]
            ts=[(p-a).dot(axis) for p in coords]
            if min(ts)<-.02 or max(ts)>length+.08: continue
            anchor=a+axis*(sum(ts)/len(ts))
            samples=coords+[sum((original[i] for i in f.vertices),Vector())/len(f.vertices) for f in faces]
            def measure(scale,shift):
                values=[gap(anchor+(p-anchor)*scale+axis*shift) for p in samples]
                bad=[max(0.,settings.get('clearance',.004)-v) for v in values if v is not None]
                unknown=sum(v is None for v in values)
                return max(bad,default=0),sum(v*v for v in bad),unknown
            before=measure(1,0)
            choices=[]
            for si in range(11):
                scale=1+si*.05
                for ti in range(9):
                    shift=-ti*.005
                    new_min=min((anchor+(p-anchor)*scale+axis*shift-a).dot(axis) for p in coords)
                    if new_min<-.01: continue
                    measured=measure(scale,shift)
                    # Unknown ray support cannot be traded for zero violations.
                    score=measured[1]+max(0,measured[2]-before[2])*.001
                    shape_cost=(scale-1)**2*.0001+shift**2*.02
                    choices.append((score+shape_cost,scale,shift,measured))
            if not choices: continue
            _,scale,shift,after=min(choices)
            if after[1]>=before[1]-1e-10: scale,shift,after=1.,0.,before
            for i in ids: points[i]=anchor+(original[i]-anchor)*scale+axis*shift
            reports.append({'side':side,'vertices':len(ids),'faces':len(faces),'materials':sorted(mats),
                'upper_arm_ratio':ratio,'axial_bounds_m':[min(ts),max(ts)],'scale':scale,'axial_shift_m':shift,
                'before':{'max_shortfall_m':before[0],'squared_shortfall':before[1],'unsupported_samples':before[2]},
                'after':{'max_shortfall_m':after[0],'squared_shortfall':after[1],'unsupported_samples':after[2]},
                'max_displacement_m':max((points[i]-original[i]).length for i in ids)})
    inv=garment.matrix_world.inverted(); apply_positions(garment.data,[inv@p for p in points])
    return {'method':'detached_upper_arm_similarity','components':reports,
            'moved_vertices':sum((a-b).length>1e-7 for a,b in zip(points,original)),
            'scope':'component-wide uniform scale and translation preserve original shape proportions; motion still needs review'}
