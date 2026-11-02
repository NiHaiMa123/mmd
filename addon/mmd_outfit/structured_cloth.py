"""Shape-preserving mesh cloth with coherent anchors and absolute transfer.

Simulate one layer; mix simulation with an identically skinned rest reference.
An unskinned visual carrier follows that target. Its absolute positions replace
selected skinned vertices independently of their original attachment weights.
"""
import bpy,bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
from .service import engine
from .mesh_cloth import configure


def _field(tree,name,kind='FLOAT'):
    n=tree.nodes.new('GeometryNodeInputNamedAttribute');n.data_type=kind;n.inputs['Name'].default_value=name;return n.outputs['Attribute']


def _tree(name,with_input=False):
    t=bpy.data.node_groups.new(name,'GeometryNodeTree')
    if with_input:t.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    t.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    return t


def _info(tree,obj):
    n=tree.nodes.new('GeometryNodeObjectInfo');n.transform_space='RELATIVE';n.inputs['Object'].default_value=obj;return n.outputs['Geometry']


def _sample(tree,geo,index):
    p=tree.nodes.new('GeometryNodeInputPosition');s=tree.nodes.new('GeometryNodeSampleIndex');s.data_type='FLOAT_VECTOR';s.domain='POINT';tree.links.new(geo,s.inputs['Geometry']);tree.links.new(p.outputs[0],s.inputs['Value']);tree.links.new(index,s.inputs['Index']);return s.outputs['Value']


def _mix_position(tree,geo,target,factor,selection=None):
    n,l=tree.nodes,tree.links;p=n.new('GeometryNodeInputPosition');sub=n.new('ShaderNodeVectorMath');sub.operation='SUBTRACT';l.new(target,sub.inputs[0]);l.new(p.outputs[0],sub.inputs[1]);scale=n.new('ShaderNodeVectorMath');scale.operation='SCALE';l.new(sub.outputs[0],scale.inputs[0]);l.new(factor,scale.inputs['Scale']);move=n.new('GeometryNodeSetPosition');l.new(geo,move.inputs['Geometry']);l.new(scale.outputs[0],move.inputs['Offset'])
    if selection is not None:l.new(selection,move.inputs['Selection'])
    return move.outputs['Geometry']


def _bind_carrier(carrier,target,rest_mesh):
    rest_mesh.calc_loop_triangles();triangles=list(rest_mesh.loop_triangles);points=[v.co.copy() for v in rest_mesh.vertices];bvh=BVHTree.FromPolygons(points,[tuple(t.vertices) for t in triangles],all_triangles=True)
    mesh=carrier.data;indices=[mesh.attributes.new('OutfitBindI'+str(i),'INT','POINT') for i in range(3)];weights=[mesh.attributes.new('OutfitBindW'+str(i),'FLOAT','POINT') for i in range(3)];offset=mesh.attributes.new('OutfitBindNormalOffset','FLOAT','POINT')
    for v in mesh.vertices:
        _,_,ti,_=bvh.find_nearest(v.co);t=triangles[ti];a,b,c=(points[i] for i in t.vertices);normal=(b-a).cross(c-a).normalized();projected=v.co-normal*(v.co-a).dot(normal);w=barycentric_transform(projected,a,b,c,Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))
        for i in range(3):indices[i].data[v.index].value=t.vertices[i];weights[i].data[v.index].value=w[i]
        offset.data[v.index].value=(v.co-a).dot(normal)
    tree=_tree('Outfit_BarycentricClothCarrier',True);n,l=tree.nodes,tree.links;inp=n.new('NodeGroupInput');geo=_info(tree,target);samples=[_sample(tree,geo,_field(tree,'OutfitBindI'+str(i),'INT')) for i in range(3)];weighted=[]
    for i in range(3):
        scale=n.new('ShaderNodeVectorMath');scale.operation='SCALE';l.new(samples[i],scale.inputs[0]);l.new(_field(tree,'OutfitBindW'+str(i)),scale.inputs['Scale']);weighted.append(scale.outputs[0])
    total=weighted[0]
    for v in weighted[1:]:
        add=n.new('ShaderNodeVectorMath');add.operation='ADD';l.new(total,add.inputs[0]);l.new(v,add.inputs[1]);total=add.outputs[0]
    vectors=[]
    for i in (1,2):
        sub=n.new('ShaderNodeVectorMath');sub.operation='SUBTRACT';l.new(samples[i],sub.inputs[0]);l.new(samples[0],sub.inputs[1]);vectors.append(sub.outputs[0])
    cross=n.new('ShaderNodeVectorMath');cross.operation='CROSS_PRODUCT';l.new(vectors[0],cross.inputs[0]);l.new(vectors[1],cross.inputs[1]);normal=n.new('ShaderNodeVectorMath');normal.operation='NORMALIZE';l.new(cross.outputs[0],normal.inputs[0]);scale=n.new('ShaderNodeVectorMath');scale.operation='SCALE';l.new(normal.outputs[0],scale.inputs[0]);l.new(_field(tree,'OutfitBindNormalOffset'),scale.inputs['Scale']);add=n.new('ShaderNodeVectorMath');add.operation='ADD';l.new(total,add.inputs[0]);l.new(scale.outputs[0],add.inputs[1]);move=n.new('GeometryNodeSetPosition');l.new(inp.outputs['Geometry'],move.inputs['Geometry']);l.new(add.outputs[0],move.inputs['Position']);out=n.new('NodeGroupOutput');l.new(move.outputs['Geometry'],out.inputs['Geometry']);carrier.modifiers.new('Absolute barycentric cloth transfer','NODES').node_group=tree


def install(cloth,arm,body,parts,*,first=1,last=450):
    """parts: [{faces, attachment_bone, pin_start, pin_end, motion_min/max}]."""
    if any(m.name=='Structured cloth absolute positions' for m in cloth.modifiers):raise ValueError('Structured cloth already installed')
    if not parts:raise ValueError('Explicit cloth parts required')
    seen=set()
    for part in parts:
        if part['attachment_bone'] not in arm.data.bones:raise ValueError('Missing attachment bone: '+part['attachment_bone'])
        if part['pin_start']>=part['pin_end']:raise ValueError('Invalid attachment transition')
        if part['free_depth']<=0 or not 0<=part['motion_min']<=part['motion_max']<=1:raise ValueError('Invalid cloth motion range')
        if not part['faces'] or any(not 0<=fi<len(cloth.data.polygons) for fi in part['faces']):raise ValueError('Invalid source faces')
        vertices={i for fi in part['faces'] for i in cloth.data.polygons[fi].vertices}
        if vertices&seen:raise ValueError('Physical parts must have separate vertices')
        seen.update(vertices)
        if sum(cloth.data.vertices[i].co.z>=part['pin_end'] for i in vertices)<2:raise ValueError('Each part needs two fully fixed anchor vertices')
    faces=sorted({fi for part in parts for fi in part['faces']});ids=sorted({i for fi in faces for i in cloth.data.polygons[fi].vertices});mapping={i:k for k,i in enumerate(ids)}
    mesh=bpy.data.meshes.new('StructuredClothSimulation');mesh.from_pydata([cloth.data.vertices[i].co[:] for i in ids],[],[[mapping[i] for i in cloth.data.polygons[fi].vertices] for fi in faces]);mesh.update()
    proxy=bpy.data.objects.new('ClothSimulationSurface',mesh);bpy.context.scene.collection.objects.link(proxy);proxy.matrix_world=cloth.matrix_world.copy();proxy['outfit_backup']=True
    pin=proxy.vertex_groups.new(name='ClothPins');strength=mesh.attributes.new('OutfitClothMotion','FLOAT','POINT');classification={};report_parts=[]
    for part in parts:
        oldids={i for fi in part['faces'] for i in cloth.data.polygons[fi].vertices};group=proxy.vertex_groups.get(part['attachment_bone']) or proxy.vertex_groups.new(name=part['attachment_bone']);group.add([mapping[i] for i in oldids],1.,'REPLACE');pins=[]
        for i in oldids:
            z=cloth.data.vertices[i].co.z;t=max(0.,min(1.,(z-part['pin_start'])/(part['pin_end']-part['pin_start'])));w=t*t*(3-2*t)
            if w:pin.add([mapping[i]],w,'REPLACE')
            depth=max(0.,min(1.,(part['pin_start']-z)/part['free_depth']));strength.data[mapping[i]].value=part['motion_min']+(part['motion_max']-part['motion_min'])*depth
            pins.append(w);classification[i]=part['kind']
        report_parts.append({'kind':part['kind'],'attachment_bone':part['attachment_bone'],'vertices':len(oldids),'fully_pinned':sum(w>.999 for w in pins),'partially_pinned':sum(0<w<=.999 for w in pins),'motion_range':[part['motion_min'],part['motion_max']]})
    # Keep the simulation surface triangulated and free of degenerate edges.
    # The visible mesh and every character morph remain unchanged.
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.dissolve_degenerate(bm,dist=.00001,edges=list(bm.edges));bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.update()
    arm_mod=proxy.modifiers.new('Coherent attachment pose','ARMATURE');arm_mod.object=arm
    reference=bpy.data.objects.new('ClothKinematicReference',mesh.copy());bpy.context.scene.collection.objects.link(reference);reference.matrix_world=proxy.matrix_world.copy();reference['outfit_backup']=True
    for g in proxy.vertex_groups:reference.vertex_groups.new(name=g.name)
    for v in mesh.vertices:
        for g in v.groups:reference.vertex_groups[g.group].add([v.index],g.weight,'REPLACE')
    reference.modifiers.new('Attachment reference','ARMATURE').object=arm
    # The carrier receives absolute positions, with no armature of its own.
    target=bpy.data.objects.new('ClothShapePreservingTarget',mesh.copy());bpy.context.scene.collection.objects.link(target);target.matrix_world=cloth.matrix_world.copy();target['outfit_backup']=True
    t=_tree('Outfit_StructuredClothTarget');index=t.nodes.new('GeometryNodeInputIndex').outputs[0];geo=_info(t,reference);sample=_sample(t,_info(t,proxy),index);mixed=_mix_position(t,geo,sample,_field(t,'OutfitClothMotion'));out=t.nodes.new('NodeGroupOutput');t.links.new(mixed,out.inputs['Geometry']);target.modifiers.new('Controlled cloth displacement','NODES').node_group=t
    kd=KDTree(len(ids))
    for k,i in enumerate(ids):kd.insert(cloth.data.vertices[i].co,k)
    kd.balance();driven=set()
    for v in cloth.data.vertices:
        _,_,distance=kd.find(v.co);secondary=sum(g.weight for g in v.groups if cloth.vertex_groups[g.group].name.startswith(('袖_','スカート_')))
        if distance<.019 or secondary>.05:driven.add(v.index)
    # Include complete faces at the selection edge in the carrier, but write
    # back only the explicitly driven vertices; all topology stays unchanged.
    carrier_faces=[f.index for f in cloth.data.polygons if any(i in driven for i in f.vertices)]
    carrier,carrier_ids=engine('garment')._copy_mesh_subset(cloth,carrier_faces,'ClothUnskinnedVisualCarrier');carrier['outfit_backup']=True;carrier['mmd_garment']=False
    _bind_carrier(carrier,target,mesh)
    valid=cloth.data.attributes.new('OutfitStructuredClothSelection','BOOLEAN','POINT');indices=cloth.data.attributes.new('OutfitStructuredClothIndex','INT','POINT')
    carrier_map={old:new for new,old in enumerate(carrier_ids)}
    for i in driven:valid.data[i].value=True;indices.data[i].value=carrier_map[i]
    t=_tree('Outfit_AbsoluteClothPositions',True);inp=t.nodes.new('NodeGroupInput');index=_field(t,'OutfitStructuredClothIndex','INT');sample=_sample(t,_info(t,carrier),index);one=t.nodes.new('ShaderNodeValue');one.outputs[0].default_value=1.;mixed=_mix_position(t,inp.outputs['Geometry'],sample,one.outputs[0],_field(t,'OutfitStructuredClothSelection','BOOLEAN'));out=t.nodes.new('NodeGroupOutput');t.links.new(mixed,out.inputs['Geometry']);mod=cloth.modifiers.new('Structured cloth absolute positions','NODES');mod.node_group=t
    cloth.hide_set(False);cloth.select_set(True);bpy.context.view_layer.objects.active=cloth;bpy.ops.object.modifier_move_to_index(modifier=mod.name,index=next(i+1 for i,m in enumerate(cloth.modifiers) if m.type=='ARMATURE'))
    skin=bpy.data.objects.get('Outfit_SkinCollider')
    if skin is None:
        from .skin_collision import collider
        skin=collider(body)
    sim,solver=configure(proxy,pin.name,[skin],first=first,last=last)
    s=sim.settings;s.quality=12;s.tension_stiffness=110.;s.compression_stiffness=110.;s.shear_stiffness=65.;s.bending_stiffness=9.;s.air_damping=5.;s.bending_damping=8.;s.use_dynamic_mesh=True
    sim.collision_settings.collision_quality=6;sim.collision_settings.self_distance_min=.0015
    for o in (proxy,reference,target,carrier):o.hide_render=True;o.hide_set(True)
    cloth.data.update();cloth.update_tag(refresh={'DATA'})
    return proxy,sim,{'method':'coherent anchors; actual cloth blended with a skinned shape reference; absolute unskinned-carrier transfer','proxy_vertices':len(mesh.vertices),'proxy_faces':len(mesh.polygons),'driven_visual_vertices':len(driven),'parts':report_parts,**solver,'quality':s.quality,'bending_stiffness':s.bending_stiffness,'dynamic_rest_shape':s.use_dynamic_mesh,'double_skinning':False,'body_or_shoe_geometry_changed':False}
