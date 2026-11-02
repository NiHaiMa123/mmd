"""Deterministic, reversible foot-pose field for an external rigid high heel."""
import math
from mathutils import Matrix,Vector


def smooth(x):
    x=min(1.,max(0.,x));return x*x*(3-2*x)


class HeelPose:
    def __init__(self,ankle,angle_degrees,ball_y,ball_z,toe_forward=0.,toe_drop=0.,heel_width=1.,heel_shift=0.):
        self.ankle=Vector(ankle);self.rotation=Matrix.Rotation(math.radians(angle_degrees),3,'X')
        self.ball=Vector((self.ankle.x,ball_y,ball_z))
        self.toe_offset=Vector((0,-toe_forward,-toe_drop))
        self.heel_width=heel_width;self.heel_shift=heel_shift

    def __call__(self,point):
        p=Vector(point);a=self.ankle
        if abs(p.x-a.x)>.12 or abs(p.y-a.y)>.30 or p.z>=a.z+.065:return p
        # Toes remain approximately horizontal beyond the metatarsal hinge.
        heel=a+self.rotation@(p-a)
        toe=a+self.rotation@(self.ball-a)+(p-self.ball)+self.toe_offset
        toes=smooth((self.ball.y+.020-p.y)/.035)
        transformed=heel.lerp(toe,toes)
        # No displacement above the ankle-to-calf transition.
        strength=smooth((a.z+.065-p.z)/.065)
        result=p.lerp(transformed,strength)
        heel=smooth((p.y-(a.y-.010))/.040)*smooth((a.z+.005-p.z)/.035)
        result.x=a.x+(result.x-a.x)*(1-(1-self.heel_width)*heel)-(1 if a.x>0 else -1)*self.heel_shift*heel
        return result


def deform_mesh(obj,poses):
    def apply(p):return poses['L' if p.x>=0 else 'R'](p)
    before=[v.co.copy() for v in obj.data.vertices]
    active=[i for i,p in enumerate(before) if (apply(p)-p).length>1e-9]
    for i in active:obj.data.vertices[i].co=apply(before[i])
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:
            for i in active:key.data[i].co=apply(key.data[i].co)
    obj.data.update()
    return {'vertices':sum((v.co-p).length>1e-8 for v,p in zip(obj.data.vertices,before)),
            'max_displacement_m':max(((v.co-p).length for v,p in zip(obj.data.vertices,before)),default=0.),
            'deleted_vertices':0,'deleted_faces':0}


def bind_shod_forefoot(obj,arm):
    """Closed hard shoes constrain toe articulation, while retaining all skin."""
    names={g.index:g.name for g in obj.vertex_groups};changed=0
    for vertex in obj.data.vertices:
        side='L' if vertex.co.x>=0 else 'R';ankle=arm.data.bones['足首D.'+side].head_local
        if vertex.co.z>ankle.z+.01 or abs(vertex.co.x-ankle.x)>.12 or abs(vertex.co.y-ankle.y)>.30:continue
        target='足首D.'+side
        transfer=[(names[e.group],e.weight) for e in vertex.groups if names[e.group].endswith('.'+side)
                  and names[e.group].startswith('足') and names[e.group] not in (target,'足D.'+side)]
        if not transfer:continue
        amount=sum(w for n,w in transfer)+sum(e.weight for e in vertex.groups if names[e.group]==target)
        for name,w in transfer:obj.vertex_groups[name].remove([vertex.index])
        group=obj.vertex_groups.get(target) or obj.vertex_groups.new(name=target)
        group.add([vertex.index],amount,'REPLACE');changed+=1
    return {'changed_vertices':changed,'deleted_vertices':0,'deleted_faces':0,
            'scope':'toe articulation follows the ankle while wearing closed rigid shoes; calf blending and vertex morph data retained'}
