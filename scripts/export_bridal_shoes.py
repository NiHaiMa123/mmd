"""Bake a portable MMD shoe material while keeping the native PBR Blend.

This runs on the fitted copy, never on the original external asset.
"""
import argparse,importlib,sys,json,math,shutil
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine,_static_validation
from mmd_outfit.jobs import read_json,write_json
p=argparse.ArgumentParser();p.add_argument('--fit',required=True);p.add_argument('--size',type=int,default=2048)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.fit).resolve();model=out/'mmd';model.mkdir(exist_ok=True)
def progress(stage,**extra):write_json(out/'export_status.json',{'stage':stage,**extra});print('BRIDAL_EXPORT',stage,flush=True)
ie,garment,render=[engine(n) for n in ('import_export','garment','extraction')]
package=ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(out/'work.blend'),load_ui=False,use_scripts=False)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');deps=bpy.context.evaluated_depsgraph_get()
originals=[o for o in bpy.data.objects if o.get('external_shoe')]
sources=sorted([o for o in originals if o.name.endswith('.L')],key=lambda o:o.name)
progress('assemble_bake_atlas')
def shader_attributes(tree,seen=None):
    seen=set() if seen is None else seen
    if tree in seen:return set()
    seen.add(tree);names=set()
    for node in tree.nodes:
        if node.type=='ATTRIBUTE':names.add(node.attribute_name)
        if node.type=='GROUP' and node.node_tree:names.update(shader_attributes(node.node_tree,seen))
    return names
needed=set().union(*(shader_attributes(m.node_tree) for obj in sources for m in obj.data.materials if m.use_nodes))
attribute_specs={}
for obj in sources:
    for name in needed:
        attribute=obj.data.attributes.get(name)
        if attribute:attribute_specs[name]=(attribute.data_type,attribute.domain)
missing=needed-attribute_specs.keys()
if missing:raise ValueError('Missing source shader attributes: '+repr(missing))
attribute_buffers={name:[] for name in attribute_specs}
vertices=[];faces=[];face_material=[];orig_uv=[];object_coords=[];generated=[];materials=[];normals=[];vertex_bindings=[]
for obj in sources:
    evaluated=obj.evaluated_get(deps);me=evaluated.to_mesh();offset=len(vertices)
    local=np.asarray([tuple(v.co) for v in me.vertices]);low=local.min(axis=0);span=np.maximum(local.max(axis=0)-low,1e-8)
    for name,(kind,domain) in attribute_specs.items():
        field,size={'FLOAT':('value',1),'INT':('value',1),'BOOLEAN':('value',1),'FLOAT_VECTOR':('vector',3),'FLOAT_COLOR':('color',4),'BYTE_COLOR':('color',4)}[kind]
        count={'POINT':len(me.vertices),'CORNER':len(me.loops),'FACE':len(me.polygons)}[domain]
        values=np.zeros(count*size,dtype=np.float32);attribute=me.attributes.get(name)
        if attribute:attribute.data.foreach_get(field,values)
        attribute_buffers[name].extend(values.tolist())
    vertices.extend([obj.matrix_world@v.co for v in me.vertices]);object_coords.extend(local.tolist());generated.extend(((local-low)/span).tolist())
    if len(me.vertices)!=len(obj.data.vertices):raise ValueError('Cannot preserve evaluated shoe skinning provenance')
    vertex_bindings.extend([[(obj.vertex_groups[g.group].name,g.weight) for g in v.groups] for v in obj.data.vertices])
    mapping=[]
    for material in me.materials:
        if material not in materials:materials.append(material)
        mapping.append(materials.index(material))
    uv=me.uv_layers.active
    normal_matrix=obj.matrix_world.to_3x3().inverted().transposed()
    for face in me.polygons:
        faces.append([i+offset for i in face.vertices]);face_material.append(mapping[face.material_index])
        orig_uv.extend([tuple(uv.data[i].uv) if uv else (0,0) for i in face.loop_indices])
        normals.extend([tuple((normal_matrix@me.corner_normals[i].vector).normalized()) for i in face.loop_indices])
    evaluated.to_mesh_clear()
me=bpy.data.meshes.new('BridalAtlasMesh');me.from_pydata(vertices,[],faces)
left=bpy.data.objects.new('BridalShoes.L',me);bpy.context.scene.collection.objects.link(left)
for material in materials:me.materials.append(material.copy())
for face,index in zip(me.polygons,face_material):face.material_index=index;face.use_smooth=True
uv=me.uv_layers.new(name='OriginalUV')
for loop,value in zip(uv.data,orig_uv):loop.uv=value
me.normals_split_custom_set(normals)
for name,values in [('BridalObject',object_coords),('BridalGenerated',generated)]:
    attr=me.attributes.new(name,'FLOAT_VECTOR','POINT');attr.data.foreach_set('vector',np.asarray(values,dtype=np.float32).reshape(-1))
for name,(kind,domain) in attribute_specs.items():
    attr=me.attributes.new(name,kind,domain)
    field={'FLOAT':'value','INT':'value','BOOLEAN':'value','FLOAT_VECTOR':'vector','FLOAT_COLOR':'color','BYTE_COLOR':'color'}[kind]
    attr.data.foreach_set(field,attribute_buffers[name])
atlas=me.uv_layers.new(name='BridalAtlas');me.uv_layers.active=atlas;atlas.active_render=True
for obj in bpy.context.selected_objects:obj.select_set(False)
left.select_set(True);bpy.context.view_layer.objects.active=left
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.003)
bpy.ops.object.mode_set(mode='OBJECT')
image=bpy.data.images.new('WhiteBridalAtlas',a.size,a.size,alpha=True);image.generated_color=(1,1,1,1)
shader_counts={}
def prepare_tree(tree):
    for node in list(tree.nodes):
        shader_counts[node.type]=shader_counts.get(node.type,0)+1
        if node.type=='GROUP' and node.node_tree:
            node.node_tree=node.node_tree.copy();prepare_tree(node.node_tree)
        if node.type=='TEX_COORD':
            for socket,attribute in [('Object','BridalObject'),('Generated','BridalGenerated')]:
                links=list(node.outputs[socket].links)
                if links:
                    replacement=tree.nodes.new('ShaderNodeAttribute');replacement.attribute_name=attribute
                    for link in links:tree.links.new(replacement.outputs['Vector'],link.to_socket)
            links=list(node.outputs['UV'].links)
            if links:
                replacement=tree.nodes.new('ShaderNodeUVMap');replacement.uv_map='OriginalUV'
                for link in links:tree.links.new(replacement.outputs['UV'],link.to_socket)
        if node.type=='TEX_IMAGE' and not node.inputs['Vector'].is_linked:
            uv_node=tree.nodes.new('ShaderNodeUVMap');uv_node.uv_map='OriginalUV';tree.links.new(uv_node.outputs['UV'],node.inputs['Vector'])
        if node.type=='BSDF_PRINCIPLED':
            replacement=tree.nodes.new('ShaderNodeEmission');color=node.inputs['Base Color']
            if color.is_linked:tree.links.new(color.links[0].from_socket,replacement.inputs['Color'])
            else:replacement.inputs['Color'].default_value=color.default_value
            # A mild normal-derived tone preserves procedural lace relief in a
            # diffuse-only PMX texture. Native PBR shading remains in work.blend.
            if node.inputs['Normal'].is_linked:
                dot=tree.nodes.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT';dot.inputs[1].default_value=(.2,-.25,.947)
                tree.links.new(node.inputs['Normal'].links[0].from_socket,dot.inputs[0])
                tone=tree.nodes.new('ShaderNodeMath');tone.operation='MULTIPLY_ADD';tone.inputs[1].default_value=.15;tone.inputs[2].default_value=.85
                tree.links.new(dot.outputs['Value'],tone.inputs[0])
                mix=tree.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1
                if color.is_linked:tree.links.new(color.links[0].from_socket,mix.inputs[1])
                else:mix.inputs[1].default_value=color.default_value
                tree.links.new(tone.outputs[0],mix.inputs[2]);tree.links.new(mix.outputs[0],replacement.inputs['Color'])
            for link in list(node.outputs[0].links):tree.links.new(replacement.outputs[0],link.to_socket)
for material in me.materials:
    prepare_tree(material.node_tree)
    if '珍珠' in material.name:
        pearl=material.node_tree.nodes.new('ShaderNodeEmission');pearl.inputs['Color'].default_value=(.94,.92,.89,1)
        for node in material.node_tree.nodes:
            if node.type=='OUTPUT_MATERIAL':material.node_tree.links.new(pearl.outputs[0],node.inputs['Surface'])
    texture=material.node_tree.nodes.new('ShaderNodeTexImage');texture.image=image;material.node_tree.nodes.active=texture
scene=bpy.context.scene
for obj in bpy.data.objects:
    if obj.type=='MESH':obj.hide_render=obj!=left
left.hide_set(False);scene.render.engine='CYCLES';scene.cycles.samples=1
scene.render.bake.margin=4;scene.render.bake.use_clear=False
progress('bake_material',shader_counts=shader_counts)
bpy.ops.object.bake(type='EMIT')
pixels=np.empty(a.size*a.size*4,dtype=np.float32);image.pixels.foreach_get(pixels);pixels=pixels.reshape(-1,4)
unpainted=pixels[:,3]<.5;pixels[unpainted]=(1,1,1,1);image.pixels.foreach_set(pixels.reshape(-1));image.update()
texture_path=model/'white_bridal_atlas.png';image.filepath_raw=str(texture_path);image.file_format='PNG';image.save()
progress('convert_mmd_material')
material=bpy.data.materials.new('WhiteBridal');material.use_nodes=True
material.mmd_material.name_j='WhiteBridal';material.mmd_material.diffuse_color=(1,1,1);material.mmd_material.ambient_color=(.5,.5,.5)
material.mmd_material.specular_color=(.15,.15,.15);material.mmd_material.shininess=30.;material.mmd_material.alpha=1.;material.mmd_material.enabled_toon_edge=False
material.mmd_material.is_double_sided=True
fn=importlib.import_module(package+'.core.material').FnMaterial(material);fn.create_texture(str(texture_path));fn.update_diffuse_color()
uv_values=[tuple(loop.uv) for loop in me.uv_layers['BridalAtlas'].data]
for layer in list(me.uv_layers):
    if layer.name!='BridalAtlas':me.uv_layers.remove(layer)
me.materials.clear();me.materials.append(material)
for face in me.polygons:face.material_index=0
# Build a mirrored copy with reversed winding and corresponding UV loops.
rmesh=bpy.data.meshes.new('BridalAtlasMesh.R')
rmesh.from_pydata([(-v.co.x,v.co.y,v.co.z) for v in me.vertices],[],[list(reversed(f.vertices[:])) for f in me.polygons])
rmesh.materials.append(material);ruv=rmesh.uv_layers.new(name='BridalAtlas')
for lf,rf in zip(me.polygons,rmesh.polygons):
    rf.use_smooth=True
    for li,ri in zip(reversed(lf.loop_indices[:]),rf.loop_indices):ruv.data[ri].uv=uv_values[li]
right=bpy.data.objects.new('BridalShoes.R',rmesh);bpy.context.scene.collection.objects.link(right)
for obj,side in [(left,'L'),(right,'R')]:
    obj.parent=arm
    binding_groups={}
    for i,weights in enumerate(vertex_bindings):
        for name,weight in weights:
            if side=='R' and name.endswith('.L'):name=name[:-2]+'.R'
            binding_groups.setdefault((name,weight),[]).append(i)
    for (name,weight),indices in binding_groups.items():
        (obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)).add(indices,weight,'REPLACE')
    modifier=obj.modifiers.new('Armature','ARMATURE');modifier.object=arm;obj['mmd_garment']=True
for obj in originals:bpy.data.objects.remove(obj,do_unlink=True)
meshes=ie.model_meshes();split_reports={obj.name:garment.split_uv_vertices(obj) for obj in meshes}
for obj in meshes:obj.hide_render=False
progress('export_pmx')
for root in ie.model_roots():root.hide_set(False);root.hide_viewport=False
ie.export_pmx(str(model/'model.pmx'))
# The shared exporter intentionally skips existing copied textures. Our atlas
# is regenerated, so synchronize its owned export copies explicitly.
atlas_copies=[]
for copied in model.rglob(texture_path.name):
    if copied.resolve()!=texture_path.resolve():shutil.copyfile(texture_path,copied);atlas_copies.append(str(copied))
# A head transplant can own a new neck texture in this output directory too.
# Refresh generated copies only; artist source textures outside out stay read-only.
generated_copies=[]
for image_data in bpy.data.images:
    if not image_data.filepath:continue
    owned=Path(bpy.path.abspath(image_data.filepath)).resolve()
    if not owned.is_relative_to(out) or not owned.is_file():continue
    for copied in model.rglob(owned.name):
        if copied.resolve()==owned:continue
        shutil.copyfile(owned,copied);generated_copies.append({'source':str(owned),'copy':str(copied)})
bpy.ops.wm.save_as_mainfile(filepath=str(model/'mmd_work.blend'))
progress('roundtrip_check')
ie.clear_scene();objects=ie.import_pmx(str(model/'model.pmx'));validation=_static_validation(objects)
write_json(out/'mmd_validation.json',validation)
if validation['failures']:raise ValueError(validation['failures'])
report={'pmx':str(model/'model.pmx'),'native_blend':str(out/'work.blend'),'mmd_blend':str(model/'mmd_work.blend'),
    'texture':str(texture_path),'atlas_size':a.size,'split_uv':split_reports,'validation':validation,
    'preserved_shader_attributes':{name:list(spec) for name,spec in attribute_specs.items()},
    'atlas_export_copies':atlas_copies,'unpainted_atlas_pixels_filled':int(unpainted.sum()),
    'shoe_vertex_bindings_preserved':True,
    'generated_texture_copies':generated_copies,
    'material_scope':'PMX uses a baked diffuse approximation; native Blend retains procedural PBR materials'}
write_json(out/'export_report.json',report)
progress('complete',pmx=report['pmx'])
