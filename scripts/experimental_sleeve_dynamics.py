"""Copy-only prototype: elbow-following cuff with a bounded PMX physics joint."""
import math
import bpy
from mathutils import Vector,Matrix,Euler


def smoothstep(x):
    x=min(1.,max(0.,x));return x*x*(3-2*x)


def fit(cloth,arm,components,physics,*,start=.55,end=.95,swing=.18,gain=.4,preserve_chain=True):
    originals=[v.co.copy() for v in cloth.data.vertices]
    names={g.index:g.name for g in cloth.vertex_groups}
    plans=[]
    for side in ('L','R'):
        ids={i for row in components if row['side']==side for i in row['vertices']}
        upper=arm.data.bones['腕.'+side];forearm=arm.data.bones['ひじ.'+side]
        axis=(forearm.head_local-upper.head_local).normalized();length=(forearm.head_local-upper.head_local).length
        weights=[]
        for i in sorted(ids):
            vertex=cloth.data.vertices[i]
            entries={names[e.group]:e.weight for e in vertex.groups if e.weight>1e-7 and not names[e.group].startswith('mmd_')}
            fraction=gain*smoothstep(((vertex.co-upper.head_local).dot(axis)/length-start)/(end-start))
            transferable={n:w for n,w in entries.items() if n.endswith('.'+side) and n.startswith('腕')}
            amount=sum(transferable.values())*fraction
            if amount<1e-6:continue
            after={n:w*(1-fraction) if n in transferable else w for n,w in entries.items()}
            after={n:w for n,w in after.items() if w>1e-7}
            after['袖口補助.'+side]=amount
            ranked=sorted(after.items(),key=lambda x:-x[1]);dropped=sum(w for n,w in ranked[4:])
            if dropped>1e-4:raise ValueError('Cuff transfer would discard significant PMX weights')
            after=dict(ranked[:4]);total=sum(after.values());after={n:w/total for n,w in after.items()}
            weights.append((i,entries,after))
        if not weights:raise ValueError('No cuff vertices selected')
        name='袖口補助.'+side
        if name in arm.data.bones:raise ValueError('Cuff helper already exists')
        plans.append((side,name,weights))
    bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    try:
        for side,name,weights in plans:
            parent=arm.data.edit_bones['ひじ.'+side];bone=arm.data.edit_bones.new(name)
            bone.matrix=parent.matrix.copy();bone.length=parent.length;bone.parent=parent;bone.use_connect=False
            if not preserve_chain:arm.data.edit_bones['袖_0_1.'+side].parent=bone
    finally:bpy.ops.object.mode_set(mode='OBJECT')
    rows=[]
    core=physics._mmd_rigid_core();fn=core.FnRigidBody
    rg,jg=physics._groups(list(bpy.data.objects))
    rigids=[o for o in bpy.data.objects if getattr(o,'mmd_type','')=='RIGID_BODY']
    for side,name,weights in plans:
        pose=arm.pose.bones[name];pose.mmd_bone.name_j=('左' if side=='L' else '右')+'袖口補助'
        pose.mmd_bone.name_e='cuff_assist_'+side
        for i,before,after in weights:
            for n in before:cloth.vertex_groups[n].remove([i])
            for n,w in after.items():
                group=cloth.vertex_groups.get(n) or cloth.vertex_groups.new(name=n);group.add([i],w,'REPLACE')
        forearm=next(r for r in rigids if r.mmd_rigid.bone=='ひじ.'+side and str(r.mmd_rigid.type)=='0')
        sleeve=next(r for r in rigids if r.mmd_rigid.bone=='袖_0_1.'+side)
        head=arm.matrix_world@arm.data.bones[name].head_local
        axis=(arm.matrix_world@arm.data.bones['ひじ.'+side].head_local-arm.matrix_world@arm.data.bones['腕.'+side].head_local).normalized()
        root=arm.matrix_world@arm.data.bones['袖_0_1.'+side].head_local
        radial=root-head-axis*(root-head).dot(axis);radial.normalize();tangent=radial.cross(axis).normalized()
        rotation=Matrix((tangent,radial,axis)).transposed().to_euler('YXZ')
        mask=list(sleeve.mmd_rigid.collision_group_mask);mask[forearm.mmd_rigid.collision_group_number]=False
        body=fn.new_rigid_body_object(bpy.context,rg)
        fn.setup_rigid_body_object(body,shape_type=core.shapeType('BOX'),location=head-axis*.015+radial*.075,rotation=rotation,
            size=Vector((.05,.006,.045)),dynamics_type=2,collision_group_number=sleeve.mmd_rigid.collision_group_number,
            collision_group_mask=mask,name=('左' if side=='L' else '右')+'袖口補助',bone=name,
            mass=.05,angular_damping=.9,linear_damping=.5,friction=.3,bounce=0.)
        joint=fn.new_joint_object(bpy.context,jg,1.)
        fn.setup_joint_object(joint,head,rotation,forearm,body,
            maximum_location=Vector((.0005,)*3),minimum_location=Vector((-.0005,)*3),
            maximum_rotation=Euler((swing,)*3),minimum_rotation=Euler((-swing,)*3),
            spring_angular=Vector((2.,)*3),spring_linear=Vector((100.,)*3),name=name)
        reconnected=[]
        for obj in ([] if preserve_chain else list(bpy.data.objects)):
            if getattr(obj,'mmd_type','')!='JOINT' or obj is joint:continue
            constraint=obj.rigid_body_constraint
            if sleeve not in (constraint.object1,constraint.object2):continue
            other=constraint.object2 if constraint.object1 is sleeve else constraint.object1
            if other is None or not other.mmd_rigid.bone.startswith('腕'):continue
            if constraint.object1 is other:constraint.object1=body
            else:constraint.object2=body
            reconnected.append(obj.name)
        rows.append({'side':side,'bone':name,'vertices':len(weights),'forearm_parent':forearm.mmd_rigid.bone,
                     'transferred_weight_min':min(after[name] for i,before,after in weights),
                     'transferred_weight_max':max(after[name] for i,before,after in weights),
                     'reconnected_chain_joints':reconnected,'rigid':body.name,'joint':joint.name,
                     'joint_swing_radians':swing,'arm_length_fraction':[start,end],'max_gain':gain,'preserve_chain':preserve_chain})
    assert max((v.co-p).length for v,p in zip(cloth.data.vertices,originals))==0
    return {'method':'experimental_elbow_cuff_physics','sides':rows,'geometry_modified':False,
            'experimental':True,'scope':'copy-only PMX bone/weight/rigid/joint prototype; requires dynamic review'}
