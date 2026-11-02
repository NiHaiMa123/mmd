"""Opt-in PMX cuff particles. Experimental, not native MMD acceptance."""
import math
from collections import defaultdict
import bpy
from mathutils import Vector,Matrix,Euler


def smoothstep(x):
    x=min(1.,max(0.,x));return x*x*(3-2*x)


def components(cloth,materials=('新規','服+jinshu')):
    """Find complete sleeve layers through topology and their existing sleeve chain."""
    names={g.index:g.name for g in cloth.vertex_groups};rows=[]
    for material in materials:
        faces=[f for f in cloth.data.polygons if cloth.data.materials[f.material_index].name==material]
        parent={i:i for f in faces for i in f.vertices};positions={}
        def find(i):
            while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
            return i
        def union(i,j):
            i,j=find(i),find(j)
            if i!=j:parent[j]=i
        for i in parent:
            key=tuple(round(c,6) for c in cloth.data.vertices[i].co)
            if key in positions:union(i,positions[key])
            else:positions[key]=i
        for f in faces:
            for i in f.vertices[1:]:union(f.vertices[0],i)
        groups=defaultdict(list)
        for i in parent:groups[find(i)].append(i)
        for ids in groups.values():
            # Small sleeve-chain accessories are not the arm-opening surface.
            if len(ids)<200:continue
            used={names[e.group] for i in ids for e in cloth.data.vertices[i].groups if e.weight>1e-6 and not names[e.group].startswith('mmd_')}
            sides={n[-1] for n in used if n.startswith('袖_') and n.endswith(('.L','.R'))}
            if not sides:continue
            if len(sides)!=1 or not all(n.endswith('.'+next(iter(sides))) and n.startswith(('腕','袖_')) for n in used):
                raise ValueError('Sleeve component has mixed or unsupported bone domains')
            rows.append({'material':material,'side':next(iter(sides)),'vertices':ids})
    for side in ('L','R'):
        for material in materials:
            if sum(r['side']==side and r['material']==material for r in rows)!=1:
                raise ValueError('Expected one complete sleeve layer per material and side: '+repr([(r['material'],r['side'],len(r['vertices'])) for r in rows]))
    return rows


def _objects(arm):
    root=arm
    while root is not None and getattr(root,'mmd_type','')!='ROOT':root=root.parent
    if root is None:raise ValueError('Cuff physics requires a target MMD model root')
    return [root,*root.children_recursive]


def build(cloth,arm,physics):
    if any(b.name.startswith('袖環') for b in arm.data.bones):
        raise ValueError('Cuff particles already exist; rerun from original inputs')
    return fit(cloth,arm,components(cloth),physics)


def fit(cloth,arm,components,physics,*,start=.55,end=.95,segments=8):
    model_objects=_objects(arm)
    core=physics._mmd_rigid_core();fn=core.FnRigidBody;rg,jg=physics._groups(model_objects)
    rigids=[o for o in model_objects if getattr(o,'mmd_type','')=='RIGID_BODY']
    if rg is None or jg is None:raise ValueError('Target rigid and joint groups are required')
    for side in ('L','R'):
        for name in ('腕.'+side,'ひじ.'+side,'袖_0_1.'+side):
            if name not in arm.data.bones:raise ValueError('Missing cuff landmark: '+name)
        if any(f'袖環{i}.'+side in arm.data.bones for i in range(segments)):
            raise ValueError('Cuff particles already exist; rerun from original inputs')
        if not any(r.mmd_rigid.bone=='腕.'+side and str(r.mmd_rigid.type)=='0' for r in rigids):
            raise ValueError('Missing kinematic upper-arm collider')
        if not any(r.mmd_rigid.bone=='袖_0_1.'+side for r in rigids):
            raise ValueError('Missing original sleeve rigid')
    names={g.index:g.name for g in cloth.vertex_groups};plans=[]
    for side in ('L','R'):
        a=arm.data.bones['腕.'+side].head_local.copy();b=arm.data.bones['ひじ.'+side].head_local.copy()
        axis=(b-a).normalized();length=(b-a).length
        if length<1e-6:raise ValueError('Degenerate upper arm')
        root=arm.data.bones['袖_0_1.'+side].head_local
        u=root-a-axis*(root-a).dot(axis)
        if u.length<1e-6:raise ValueError('Sleeve chain cannot define cuff orientation')
        u.normalize();v=axis.cross(u).normalized()
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
            if slots<0 or (arm_weights and slots<1):
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
    rows=[]
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
    return {'method':'particle_ring','geometry_modified':False,'experimental':True,'sides':rows,
            'created_bones':[f'袖環{i}.'+side for side in ('L','R') for i in range(segments)],
            'added_rigids':segments*2,'added_joints':segments*4,
            'scope':'bounded PMX cuff particles; dynamic visual review and native MMD acceptance required'}


def validate(mesh,arm,objects,report):
    generated=set(report['created_bones']);groups={g.index:g.name for g in mesh.vertex_groups}
    counts={n:0 for n in generated};affected=set();failures=[]
    for v in mesh.data.vertices:
        for entry in v.groups:
            if groups[entry.group] in generated and entry.weight>1e-6:
                counts[groups[entry.group]]+=1;affected.add(v.index)
    for name in generated:
        if name not in arm.data.bones or counts[name]==0:failures.append('Missing or unweighted cuff bone: '+name)
        matches=[o for o in objects if getattr(o,'mmd_type','')=='RIGID_BODY' and o.mmd_rigid.bone==name]
        if len(matches)!=1 or str(matches[0].mmd_rigid.type)!='1':failures.append('Missing dynamic cuff rigid: '+name)
    return {'bones':len(generated),'weighted_vertices':len(affected),'vertices_by_bone':counts,'failures':failures}
