"""Bounded outward clearance around arm axes; no projection of loose fabric."""
import math
from collections import Counter
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mmd_outfit.deformation import RadialEnvelopeField


def fit(garment, body, arm, settings, apply_positions, subdivide=None):
    margin=settings.get('clearance',.004)
    cap=settings.get('max_displacement',.025)
    reach=settings.get('max_distance',.04)
    materials=set(settings['materials'])
    skin=set(settings.get('skin_materials',['Body']))
    def labels(obj):
        names={g.index:g.name for g in obj.vertex_groups}
        result=[]
        for vertex in obj.data.vertices:
            name=max(((e.weight,names[e.group]) for e in vertex.groups
                      if not names[e.group].startswith('mmd_')),default=(0,''))[1]
            if name.endswith(('.L','.R')) and name[:-2].startswith(('腕','ひじ','手捩')):
                result.append(('upper' if name.startswith('腕') else 'fore')+'_'+name[-1])
            else: result.append(None)
        return result
    body_labels=labels(body)
    body_points=[body.matrix_world@v.co for v in body.data.vertices]
    trees={}
    axes={}
    for side in ('L','R'):
        faces=[tuple(f.vertices) for f in body.data.polygons if body.data.materials[f.material_index].name in skin
               and sum(body_labels[i] is not None and body_labels[i].endswith(side) for i in f.vertices)>=2]
        if not faces: raise ValueError('Arm clearance has no target skin on '+side)
        trees[side]=BVHTree.FromPolygons(body_points,faces)
        for name,start,end in [('upper','腕','ひじ'),('fore','ひじ','手首')]:
            a=arm.matrix_world@arm.data.bones[start+'.'+side].head_local
            b=arm.matrix_world@arm.data.bones[end+'.'+side].head_local
            length=(b-a).length
            if length<1e-5: raise ValueError('Arm clearance requires nonzero bone segments')
            axis=(b-a)/length
            u=axis.cross(Vector((0,0,1)))
            if u.length<.01: u=axis.cross(Vector((1,0,0)))
            u.normalize(); v=axis.cross(u).normalized()
            axes[name+'_'+side]=(a,axis,length,u,v)

    def contact(point,key):
        if key is None: return None
        a,axis,length,u,v=axes[key]
        along=(point-a).dot(axis)
        # Keep the reconstructed gloves and their wrist overlap out of scope.
        if along<-.012 or along>(length-.025 if key.startswith('fore') else length+.012): return None
        anchor=a+axis*along; radial=point-anchor
        radius=radial.length
        if radius<1e-6 or radius>.20: return None
        direction=radial/radius
        hit,_,_,_=trees[key[-1]].ray_cast(anchor+direction*.5,-direction,1.)
        if hit is None: return None
        target=(hit-anchor).dot(direction)
        gap=radius-target
        if target<=0 or target>.15 or abs(gap)>reach: return None
        return math.atan2(direction.dot(v),direction.dot(u)),along,direction,gap

    subdivision=[]
    for level in range(settings.get('subdivide',0)):
        kinds=labels(garment); chosen=[]
        for face in garment.data.polygons:
            if garment.data.materials[face.material_index].name not in materials: continue
            keys={kinds[i] for i in face.vertices}
            if len(keys)!=1 or None in keys: continue
            key=next(iter(keys)); points=[garment.matrix_world@garment.data.vertices[i].co for i in face.vertices]
            if contact(sum(points,Vector())/len(points),key) is None: continue
            if any((a-b).length>settings.get('max_edge',.015) for a,b in zip(points,points[1:]+points[:1])):
                chosen.append(face.index)
        if chosen and subdivide is None: raise ValueError('Arm subdivision callback missing')
        subdivision.append({'faces':len(chosen),'added':subdivide(garment.data,chosen) if chosen else 0})

    kinds=labels(garment)
    selected={i for face in garment.data.polygons if garment.data.materials[face.material_index].name in materials
              for i in face.vertices if kinds[i] is not None}
    points=[garment.matrix_world@v.co for v in garment.data.vertices]
    original=[p.copy() for p in points]
    selected={i for i in selected if contact(points[i],kinds[i]) is not None}
    faces=[face for face in garment.data.polygons if all(i in selected for i in face.vertices)
           and len({kinds[i] for i in face.vertices})==1]
    def controls():
        required={i:0. for i in selected}
        vertex_bad=face_bad=unsupported=0
        minimum=None
        for i in selected:
            c=contact(points[i],kinds[i])
            if c is None: unsupported+=1; continue
            gap=c[3]; minimum=gap if minimum is None else min(minimum,gap)
            vertex_bad+=gap<margin-1e-5; required[i]=max(0.,margin-gap)
        for face in faces:
            ps=[points[i] for i in face.vertices]
            samples=[sum(ps,Vector())/len(ps)]+[(a+b)*.5 for a,b in zip(ps,ps[1:]+ps[:1])]
            amount=0.
            for p in samples:
                c=contact(p,kinds[face.vertices[0]])
                if c is not None: amount=max(amount,margin-c[3])
            face_bad+=amount>1e-5
            for i in face.vertices: required[i]=max(required[i],amount)
        return required,{'violating_vertices':vertex_bad,'violating_sampled_faces':face_bad,
                         'unavailable_vertices':unsupported,'min_vertex_gap_m':minimum}
    _,before=controls()
    capped=set()
    for iteration in range(settings.get('iterations',5)):
        amounts,measured=controls()
        if not measured['violating_vertices'] and not measured['violating_sampled_faces']: break
        for key in axes:
            ids=sorted(i for i in selected if kinds[i]==key)
            active=[(i,contact(points[i],key)) for i in ids]
            active=[(i,c) for i,c in active if c is not None]
            if not active: continue
            field=RadialEnvelopeField([c[0] for i,c in active],[c[1] for i,c in active],
                [amounts[i] for i,c in active],angular_radius=.35,height_radius=.025)
            values=field.evaluate([c[0] for i,c in active],[c[1] for i,c in active])
            for (i,c),amount in zip(active,values):
                wanted=points[i]+c[2]*float(amount)
                delta=wanted-original[i]
                if delta.length>cap:
                    wanted=original[i]+delta.normalized()*cap; capped.add(i)
                points[i]=wanted
    _,after=controls()
    inverse=garment.matrix_world.inverted()
    apply_positions(garment.data,[inverse@p for p in points])
    return {'method':'arm_axis_outward_envelope','settings':settings,'selected_vertices':len(selected),
            'regions':dict(Counter(kinds[i] for i in selected)),'sampled_faces':len(faces),
            'subdivision':subdivision,'before':before,'after':after,'capped_vertices':len(capped),
            'moved_vertices':sum((points[i]-original[i]).length>1e-7 for i in selected),
            'max_displacement_m':max(((points[i]-original[i]).length for i in selected),default=0),
            'scope':'rest-pose outward near-skin correction; loose unsupported cloth stays unchanged; motion needs review'}
