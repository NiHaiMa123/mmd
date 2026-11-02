"""Copy-only PMX cuff ring: bounded translating particles around an arm opening."""
import math
import bpy
from mathutils import Vector,Matrix,Euler
from experimental_sleeve_dynamics import smoothstep


def fit(cloth,arm,components,physics,*,start=.55,end=.95,segments=8):
    names={g.index:g.name for g in cloth.vertex_groups};plans=[]
    for side in ('L','R'):
        a=arm.data.bones['腕.'+side].head_local.copy();b=arm.data.bones['ひじ.'+side].head_local.copy()
        axis=(b-a).normalized();length=(b-a).length
        root=arm.data.bones['袖_0_1.'+side].head_local
        u=root-a-axis*(root-a).dot(axis);u.normalize();v=axis.cross(u).normalized()
        ids={i for row in components if row['side']==side for i in row['vertices']}
        samples=[[] for _ in range(segments)];weights=[];merged_mass=[];skipped=0
        for i in sorted(ids):
            p=cloth.data.vertices[i].co;radial=p-a-axis*(p-a).dot(axis)
            angle=math.atan2(radial.dot(v),radial.dot(u))%(2*math.pi)
            index=int(math.floor(angle/(2*math.pi)*segments+.5))%segments
            entries={names[e.group]:e.weight for e in cloth.data.vertices[i].groups if e.weight>1e-7 and not names[e.group].startswith('mmd_')}
            fraction=smoothstep(((p-a).dot(axis)/length-start)/(end-start))
            transferable={n:w for n,w in entries.items() if n.endswith('.'+side) and n.startswith('腕')}
            amount=sum(transferable.values())*fraction
            if amount<1e-6:continue
            after={n:w for n,w in entries.items() if n not in transferable}
            arm_weights={n:w*(1-fraction) for n,w in transferable.items() if w*(1-fraction)>1e-7}
            coordinate=angle/(2*math.pi)*segments;first=int(math.floor(coordinate));blend=coordinate-first
            node_weights={f'袖環{first%segments}.'+side:amount*(1-blend),
                          f'袖環{(first+1)%segments}.'+side:amount*blend}
            node_weights={n:w for n,w in node_weights.items() if w>1e-7}
            slots=4-len(after)-len(node_weights)
            if arm_weights and slots<1:
                skipped+=1;continue
            ranked=sorted(arm_weights.items(),key=lambda x:-x[1])
            if len(ranked)>slots:
                total=sum(arm_weights.values());retained=sum(w for n,w in ranked[:slots])
                merged_mass.append(total-retained)
                arm_weights={n:w*total/retained for n,w in ranked[:slots]}
            after.update(arm_weights);after.update(node_weights)
            total=sum(after.values());after={n:w/total for n,w in after.items()}
            weights.append((i,entries,after))
            if .7<(p-a).dot(axis)/length<1.2 and .008<radial.length<.12:samples[index].append(radial.length)
        if not all(samples):raise ValueError('Cuff ring has missing angular support')
        radii=[sorted(values)[int((len(values)-1)*.10)] for values in samples]
        heads=[a+axis*(length*.95)+(u*math.cos(i*2*math.pi/segments)+v*math.sin(i*2*math.pi/segments))*radii[i] for i in range(segments)]
        plans.append((side,axis,u,v,heads,radii,weights,merged_mass,skipped))
    bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    try:
        for side,axis,u,v,heads,radii,weights,merged_mass,skipped in plans:
            parent=arm.data.edit_bones['腕.'+side]
            for i,head in enumerate(heads):
                bone=arm.data.edit_bones.new(f'袖環{i}.'+side);bone.matrix=parent.matrix.copy()
                bone.head=head;bone.tail=head+axis*.03;bone.parent=parent;bone.use_connect=False
    finally:bpy.ops.object.mode_set(mode='OBJECT')
    core=physics._mmd_rigid_core();fn=core.FnRigidBody;rg,jg=physics._groups(list(bpy.data.objects))
    rigids=[o for o in bpy.data.objects if getattr(o,'mmd_type','')=='RIGID_BODY'];rows=[]
    for side,axis,u,v,heads,radii,weights,merged_mass,skipped in plans:
        for i,before,after in weights:
            for n in before:cloth.vertex_groups[n].remove([i])
            for n,w in after.items():
                group=cloth.vertex_groups.get(n) or cloth.vertex_groups.new(name=n);group.add([i],w,'REPLACE')
        anchor=next(r for r in rigids if r.mmd_rigid.bone=='腕.'+side and str(r.mmd_rigid.type)=='0')
        template=next(r for r in rigids if r.mmd_rigid.bone=='袖_0_1.'+side)
        mask=list(template.mmd_rigid.collision_group_mask);mask[anchor.mmd_rigid.collision_group_number]=False
        rotation=Matrix((u,v,axis)).transposed().to_euler('YXZ');bodies=[]
        for i,head in enumerate(heads):
            name=f'袖環{i}.'+side;pose=arm.pose.bones[name]
            pose.mmd_bone.name_j=('左' if side=='L' else '右')+f'袖環{i}'
            body=fn.new_rigid_body_object(bpy.context,rg)
            fn.setup_rigid_body_object(body,shape_type=core.shapeType('SPHERE'),location=arm.matrix_world@head,
                rotation=rotation,size=Vector((.012,0,0)),dynamics_type=1,
                collision_group_number=template.mmd_rigid.collision_group_number,collision_group_mask=mask,
                name=name,bone=name,mass=.02,angular_damping=.95,linear_damping=.9,friction=.2,bounce=0.)
            joint=fn.new_joint_object(bpy.context,jg,1.)
            fn.setup_joint_object(joint,arm.matrix_world@head,rotation,anchor,body,
                maximum_location=Vector((.08,.08,.05)),minimum_location=Vector((-.08,-.08,-.05)),
                maximum_rotation=Euler((0,0,0)),minimum_rotation=Euler((0,0,0)),
                spring_linear=Vector((5.,5.,15.)),spring_angular=Vector((0,0,0)),name=name+'_根')
            bodies.append(body)
        for i,body in enumerate(bodies):
            other=bodies[(i+1)%segments];joint=fn.new_joint_object(bpy.context,jg,1.)
            fn.setup_joint_object(joint,(body.location+other.location)*.5,rotation,body,other,
                maximum_location=Vector((.035,)*3),minimum_location=Vector((-.035,)*3),
                maximum_rotation=Euler((0,0,0)),minimum_rotation=Euler((0,0,0)),
                spring_linear=Vector((15.,)*3),spring_angular=Vector((0,0,0)),name=f'袖環連結{i}.'+side)
        rows.append({'side':side,'vertices':len(weights),'segments':segments,'radii_m':radii,'particle_radius_m':.012,
                     'angle_blend':'linear_two_nodes','skipped_weight_capacity':skipped,'merged_arm_weight_max':max(merged_mass,default=0.)})
    return {'method':'experimental_particle_cuff_ring','geometry_modified':False,'experimental':True,'sides':rows,
            'scope':'bounded PMX translating cuff particles; sleeve-only collision review required'}
