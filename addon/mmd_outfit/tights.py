"""Complete pantyhose from target skin, including pelvis and an outer gusset.

The underlying body is never removed. Exact fitted ankle/foot coordinates can
be supplied as overrides. Target weights and relative vertex morphs survive.
"""
from collections import defaultdict
import math
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
from mathutils.geometry import barycentric_transform as bary


def rebuild(body, old_cloth, copy_subset, *, waist=1.065, margin=.0018,
            foot_overrides=None, foot_records=None, material=None):
    foot_overrides=foot_overrides or {}
    foot_records=foot_records or {}
    source_faces=[f for f in old_cloth.data.polygons if old_cloth.data.materials[f.material_index].mmd_material.name_j=='腿']
    old_cloth.data.calc_loop_triangles();allowed={f.index for f in source_faces}
    triangles=[t for t in old_cloth.data.loop_triangles if t.polygon_index in allowed]
    points=[v.co.copy() for v in old_cloth.data.vertices];uv_src=old_cloth.data.uv_layers.active
    tree=BVHTree.FromPolygons(points,[tuple(t.vertices) for t in triangles],all_triangles=True)
    original=[v.co.copy() for v in body.data.vertices]
    faces=[f for f in body.data.polygons if body.data.materials[f.material_index].mmd_material.name_j in {'Body','Nails'}
           and f.center.z<waist and abs(f.center.x)<.205]
    bm=bmesh.new();source_id=bm.verts.layers.int.new('target_vertex')
    used=sorted({i for f in faces for i in f.vertices});vs={}
    for i in used:
        v=bm.verts.new(original[i]);v[source_id]=i;vs[i]=v
    for f in faces:bm.faces.new([vs[i] for i in f.vertices])
    print('TIGHTS_FOOT_PROVENANCE initial',len(set(vs)&set(foot_overrides)),flush=True)
    # Internal anatomical surfaces are not a garment. Bridge their outer rim.
    remove=[]
    for f in bm.faces:
        c=f.calc_center_median()
        if abs(c.x)<.032 and -.048<c.y<.071 and .856<c.z<.936:remove.append(f)
    bmesh.ops.delete(bm,geom=remove,context='FACES')
    print('TIGHTS_FOOT_PROVENANCE cut',sum(v[source_id] in foot_overrides for v in bm.verts),flush=True)
    # Fitted feet may deliberately have coincident skin vertices with distinct
    # sock offsets at nails/UV seams. Welding them would undo shoe clearance.
    bmesh.ops.remove_doubles(bm,verts=[v for v in bm.verts if v[source_id] not in foot_overrides],dist=1e-6)
    print('TIGHTS_FOOT_PROVENANCE weld',sum(v[source_id] in foot_overrides for v in bm.verts),flush=True)
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    gusset=bm.faces.layers.int.new('gusset')
    rim=[e for e in bm.edges if e.is_boundary and all(.84<v.co.z<.96 and abs(v.co.x)<.05 and -.06<v.co.y<.085 for v in e.verts)]
    filled=bmesh.ops.holes_fill(bm,edges=rim,sides=0).get('faces',[])
    for f in filled:f[gusset]=1
    if filled:
        edges={e for f in filled for e in f.edges if e.calc_length()>.007}
        bmesh.ops.subdivide_edges(bm,edges=list(edges),cuts=5,use_grid_fill=True)
    bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update();bm.verts.index_update();bm.faces.index_update()
    body.data.calc_loop_triangles();body_tri=[t for t in body.data.loop_triangles if body.data.materials[t.material_index].mmd_material.name_j=='Body']
    body_tree=BVHTree.FromPolygons(original,[tuple(t.vertices) for t in body_tri],all_triangles=True)
    bindings=[];normals=[v.normal.copy() for v in bm.verts]
    for v in bm.verts:
        candidate=v[source_id]
        i=candidate if 0<=candidate<len(original) and (original[candidate]-v.co).length<1e-7 else None
        if i is not None:bindings.append([(i,1.)]);continue
        hit,_,ti,_=body_tree.find_nearest(v.co);tri=body_tri[ti]
        weights=bary(hit,*(original[j] for j in tri.vertices),Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))
        weights=[max(0.,w) for w in weights];total=sum(weights)
        bindings.append([(j,w/total) for j,w in zip(tri.vertices,weights) if w>1e-7])
    print('TIGHTS_FOOT_PROVENANCE final',sum(len(b)==1 and b[0][0] in foot_overrides for b in bindings),flush=True)
    fs=[[v.index for v in f.verts] for f in bm.faces];fill_ids={i for f in bm.faces if f[gusset] for i in [v.index for v in f.verts]}
    gusset_faces=[f.index for f in bm.faces if f[gusset]]
    positions=[];deltas=[]
    for k,(binding,n,v) in enumerate(zip(bindings,normals,bm.verts)):
        i=binding[0][0] if len(binding)==1 else None
        base=sum((original[j]*w for j,w in binding),Vector())
        delta=n*margin
        if k in fill_ids:delta=n*.003
        desired=v.co+delta
        # Fabric bridges the narrow buttock cleft rather than entering it.
        if desired.y>.055 and abs(desired.x)<.022 and .885<desired.z<1.015:
            hits=[body_tree.ray_cast(Vector((x,.5,desired.z)),Vector((0,-1,0)),1.)[0] for x in (-.023,.023)]
            ys=[h.y for h in hits if h]
            if ys:desired.y=max(desired.y,max(ys)+margin)
        if i in foot_overrides:desired=Vector(foot_overrides[i])
        deltas.append(desired-base);positions.append(desired)
    mesh=bpy.data.meshes.new('TargetPantyhose');mesh.from_pydata(positions,[],fs);mesh.update();bm.free()
    gusset_attr=mesh.attributes.new('OutfitGussetFaces','BOOLEAN','FACE')
    for i in gusset_faces:gusset_attr.data[i].value=True
    obj=bpy.data.objects.new('Stockings',mesh);bpy.context.scene.collection.objects.link(obj);obj.matrix_world=body.matrix_world.copy()
    for group in body.vertex_groups:obj.vertex_groups.new(name=group.name)
    for record in foot_records.values():
        for name,w in record['weights']:
            if name not in obj.vertex_groups:obj.vertex_groups.new(name=name)
    for k,binding in enumerate(bindings):
        if len(binding)==1 and binding[0][0] in foot_records:
            for name,w in foot_records[binding[0][0]]['weights']:obj.vertex_groups[name].add([k],w,'REPLACE')
            continue
        weights=defaultdict(float)
        for i,w in binding:
            for g in body.data.vertices[i].groups:weights[g.group]+=g.weight*w
        # MMD edge/order bookkeeping groups are not deforming bone influences.
        # Never let them consume the four PMX skinning slots.
        if len(binding)==1:
            entries=list(weights.items())
        else:
            aux=[(g,w) for g,w in weights.items() if body.vertex_groups[g].name.startswith('mmd_')]
            deform=[(g,w) for g,w in weights.items() if not body.vertex_groups[g].name.startswith('mmd_')]
            total=sum(w for _,w in deform);top=sorted(deform,key=lambda item:-item[1])[:4];retained=sum(w for _,w in top)
            entries=aux+[(g,w*total/retained) for g,w in top] if retained else aux
        for g,w in entries:
            if w>1e-7:obj.vertex_groups[g].add([k],w,'REPLACE')
    if body.data.shape_keys:
        for source in body.data.shape_keys.key_blocks:
            key=obj.shape_key_add(name=source.name,from_mix=False);key.slider_min=source.slider_min;key.slider_max=source.slider_max
            for p,binding,d in zip(key.data,bindings,deltas):
                record=foot_records.get(binding[0][0]) if len(binding)==1 else None
                p.co=record['keys'].get(source.name,record['co']) if record else sum((source.data[i].co*w for i,w in binding),Vector())+d
            key.value=0.
        for src,dst in zip(body.data.shape_keys.key_blocks,obj.data.shape_keys.key_blocks):dst.relative_key=obj.data.shape_keys.key_blocks[src.relative_key.name]
    material=material or next(m for m in old_cloth.data.materials if m.mmd_material.name_j=='腿')
    mesh.materials.append(material);uv=mesh.uv_layers.new(name='StockingDesignUV')
    design=mesh.attributes.new('tights_design_area','FLOAT','POINT')
    for v,d in zip(mesh.vertices,design.data):
        p=v.co;d.value=max(0.,min(1.,(.88-p.z)/.03))*max(0.,min(1.,(p.z-.22)/.04)) if p.x>.035 else 0.
    for f in mesh.polygons:
        f.use_smooth=True
        for li in f.loop_indices:
            i=mesh.loops[li].vertex_index;point=positions[i];hit,normal,ti,distance=tree.find_nearest(point);t=triangles[ti]
            coords=[Vector((*uv_src.data[j].uv,0)) for j in t.loops]
            uv.data[li].uv=barycentric_transform(hit,*(points[j] for j in t.vertices),*coords).xy
    # PMX often has authored normals. Re-triangulation must not replace those
    # with alternating diagonal highlights on otherwise smooth nylon.
    source_normals=[Vector() for _ in body.data.vertices]
    for loop,normal in zip(body.data.loops,body.data.corner_normals):source_normals[loop.vertex_index]+=normal.vector
    source_normals=[n.normalized() for n in source_normals]
    authored=[]
    for loop,normal in zip(mesh.loops,mesh.corner_normals):
        i=loop.vertex_index
        authored.append(sum((source_normals[j]*w for j,w in bindings[i]),Vector()).normalized() if positions[i].z<.82 else normal.vector.copy())
    mesh.normals_split_custom_set(authored)
    obj['mmd_garment']=True;obj['target_skin_surface']=True
    obj.parent=body.parent
    for mod in body.modifiers:
        if mod.type=='ARMATURE':new=obj.modifiers.new(mod.name,'ARMATURE');new.object=mod.object;new.use_deform_preserve_volume=mod.use_deform_preserve_volume
    names={g.index:g.name for g in old_cloth.vertex_groups}
    def leg_vertex(v):
        weights=[(g.weight,names[g.group]) for g in v.groups if not names[g.group].startswith('mmd_')]
        name=max(weights,default=(0,''))[1]
        return name.startswith(('足','ひざ','つま先')) and not name.startswith(('足IK','足ＩＫ'))
    leg_ids={v.index for v in old_cloth.data.vertices if leg_vertex(v)}
    # The source has a second metallic/alpha layer over its stockings. Keeping
    # that old layer would leave source-shaped triangles around the new legs.
    overlays={f.index for f in old_cloth.data.polygons if f.index not in allowed and all(i in leg_ids for i in f.vertices)}
    retained,_=copy_subset(old_cloth,[f.index for f in old_cloth.data.polygons if f.index not in allowed|overlays],'RetainedOutfit')
    from .preserved_shoe import replace_mesh
    replace_mesh(old_cloth,retained)
    return obj,{'vertices':len(bindings),'faces':len(fs),'removed_stocking_faces':len(allowed),'removed_old_leg_overlay_faces':len(overlays),'target_vertices':bindings,'foot_overrides':len(foot_overrides),'gusset_boundary_vertices':len(fill_ids),'body_removed_faces':0,'margin_m':margin,'waist_m':waist}


def material(gold_image):
    mat=bpy.data.materials.new('Keqing_SheerBlack_Tights');mat.use_nodes=True;mat.diffuse_color=(.032,.023,.022,1)
    mat.mmd_material.name_j='腿';mat.mmd_material.diffuse_color=(.17,.135,.13);mat.mmd_material.alpha=1;mat.mmd_material.is_double_sided=True
    n=mat.node_tree.nodes;l=mat.node_tree.links;n.clear();out=n.new('ShaderNodeOutputMaterial');bs=n.new('ShaderNodeBsdfPrincipled');l.new(bs.outputs['BSDF'],out.inputs['Surface'])
    facing=n.new('ShaderNodeLayerWeight');facing.inputs['Blend'].default_value=.3
    ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.08;ramp.color_ramp.elements[0].color=(.004,.003,.004,1);ramp.color_ramp.elements[1].position=.85;ramp.color_ramp.elements[1].color=(.030,.020,.019,1)
    # Layer Weight Facing is zero head-on, one at grazing incidence.
    ramp.color_ramp.elements[0].color=(.030,.020,.019,1);ramp.color_ramp.elements[1].color=(.003,.0025,.0035,1)
    l.new(facing.outputs['Facing'],ramp.inputs['Fac'])
    mask=n.new('ShaderNodeTexImage');mask.name='StockingGoldMask';mask.image=gold_image
    area=n.new('ShaderNodeAttribute');area.attribute_name='tights_design_area';fac=n.new('ShaderNodeMath');fac.operation='MULTIPLY';l.new(mask.outputs[0],fac.inputs[0]);l.new(area.outputs['Fac'],fac.inputs[1])
    mix=n.new('ShaderNodeMixRGB');mix.blend_type='MIX';mix.inputs[2].default_value=(.46,.26,.055,1);l.new(fac.outputs[0],mix.inputs[0]);l.new(ramp.outputs['Color'],mix.inputs[1]);l.new(mix.outputs[0],bs.inputs['Base Color'])
    ramp.color_ramp.elements[0].color=(.022,.014,.013,1)
    bs.inputs['Roughness'].default_value=.48;bs.inputs['Specular IOR Level'].default_value=.22;bs.inputs['Anisotropic'].default_value=.35;bs.inputs['Sheen Weight'].default_value=.10;bs.inputs['Sheen Roughness'].default_value=.55
    metal=n.new('ShaderNodeMath');metal.operation='MULTIPLY';metal.inputs[1].default_value=.6;l.new(fac.outputs[0],metal.inputs[0]);l.new(metal.outputs[0],bs.inputs['Metallic'])
    # Shader noise avoids subpixel banding and moire from periodic weave lines.
    tex=n.new('ShaderNodeTexCoord');noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=1800;noise.inputs['Detail'].default_value=1.;l.new(tex.outputs['Object'],noise.inputs['Vector'])
    bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.035;bump.inputs['Distance'].default_value=.000006;l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],bs.inputs['Normal'])
    geometry=n.new('ShaderNodeNewGeometry');tangent=n.new('ShaderNodeVectorMath');tangent.operation='CROSS_PRODUCT';tangent.inputs[1].default_value=(0,0,1);l.new(geometry.outputs['Normal'],tangent.inputs[0]);l.new(tangent.outputs[0],bs.inputs['Tangent'])
    mat['method']='view-dependent charcoal nylon, microfibres and isolated original gold motif';return mat
