"""Replace only footwear on an existing outfit and restore the complete feet.

The external Blend remains read-only. All fitted results go to a new directory.
"""
import argparse,math,sys,json,importlib
from pathlib import Path
from collections import Counter
import bpy
import numpy as np
from mathutils import Matrix,Vector
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine,prepare_target
from mmd_outfit.jobs import read_json,write_json
from mmd_outfit.preserved_shoe import replace_mesh,exported_vertices,lift_model
from mmd_outfit.heeled_foot import HeelPose,deform_mesh,bind_shod_forefoot

p=argparse.ArgumentParser()
for n in ('job','asset','out'):p.add_argument('--'+n,required=True)
p.add_argument('--scale',type=float,default=.11);p.add_argument('--pitch',type=float,default=12.)
p.add_argument('--lift',type=float,default=.006);p.add_argument('--shoe-y',type=float,default=-.0485)
p.add_argument('--shoe-x',type=float,default=-.003);p.add_argument('--cuff-scale',type=float,default=1.10)
p.add_argument('--toe-forward',type=float,default=.012);p.add_argument('--toe-drop',type=float,default=.005)
p.add_argument('--heel-width',type=float,default=.90);p.add_argument('--heel-shift',type=float,default=.0015)
p.add_argument('--export',action='store_true')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);job=Path(a.job).resolve();asset=Path(a.asset).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
result,profile=[read_json(job/n) for n in ('result.json','profile_snapshot.json')]
ie,garment,dressing,render=[engine(n) for n in ('import_export','garment','dressing','extraction')]
ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=result['blend'],load_ui=False,use_scripts=False)
cloth=next(o for o in ie.model_meshes() if o.get('mmd_garment'))
body=next(o for o in ie.model_meshes() if not o.get('mmd_garment'))
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
bone_core=importlib.import_module(ie.ensure_mmd_tools()+'.core.bone').FnBone
bone_core.clean_additional_transformation(arm)
root=arm
while root.parent:root=root.parent
report={'input_job':str(job),'asset':str(asset),'settings':{'scale':a.scale,'pitch':a.pitch,'lift':a.lift,'shoe_y':a.shoe_y,'shoe_x':a.shoe_x,'cuff_scale':a.cuff_scale,'toe_forward':a.toe_forward,'toe_drop':a.toe_drop,'heel_width':a.heel_width,'heel_shift':a.heel_shift},'feet_retained':True}

# Remove the old rigid shoes by recorded source coordinates, never by height.
old_ids=set(exported_vertices(cloth,result['adaptations']['shoes']['reference_positions'],profile['shoe_fit']['materials']))
old_faces={f.index for f in cloth.data.polygons if all(i in old_ids for i in f.vertices)}
remaining,_=garment._copy_mesh_subset(cloth,[f.index for f in cloth.data.polygons if f.index not in old_faces],'OutfitWithoutOldShoes')
replace_mesh(cloth,remaining);report['removed_old_shoe_vertices']=len(old_ids);report['removed_old_shoe_faces']=len(old_faces)

# Reconstruct the target skin from its original input. Above the foot transition,
# retain exactly the current visible body faces, including opaque-glove coverage.
def signature(mesh,face):
    material=mesh.data.materials[face.material_index]
    return (material.mmd_material.name_j or material.name,
            tuple(sorted(tuple(round(c,5) for c in mesh.data.vertices[i].co) for i in face.vertices)))
current={signature(body,f) for f in body.data.polygons}
original=ie.import_pmx(profile['target']['path']);original_mesh=ie.model_meshes(original)[0]
excluded=[m.name for m in original_mesh.data.materials if (m.mmd_material.name_j or m.name) in profile['target_exclude_materials']]
prepare_target(original_mesh,excluded)
baseline_lift=profile['shoe_fit']['body_lift']
dressing.apply_positions(original_mesh.data,[v.co+Vector((0,0,baseline_lift)) for v in original_mesh.data.vertices])
ankles={s:arm.data.bones['足首.'+s].head_local.copy() for s in ('L','R')}
cut=max(p.z for p in ankles.values())+.07
keep=[];restored=[];matched=set()
for face in original_mesh.data.polygons:
    sig=signature(original_mesh,face)
    material=original_mesh.data.materials[face.material_index].name.split('.')[0]
    foot=material in {'Body','Nails'} and min(original_mesh.data.vertices[i].co.z for i in face.vertices)<cut
    if foot or sig in current:
        keep.append(face.index)
        if foot:restored.append(face.index)
        if sig in current:matched.add(sig)
unmatched=[f.index for f in body.data.polygons if signature(body,f) not in matched and min(body.data.vertices[i].co.z for i in f.vertices)>=cut]
if unmatched:raise ValueError('Cannot preserve current upper body faces: '+str(unmatched[:10]))
replacement,ids=garment._copy_mesh_subset(original_mesh,keep,'FullFootTargetSkin')
# Reuse current materials so morph/material references stay attached to this model.
old_materials={m.mmd_material.name_j or m.name:m for m in body.data.materials}
for i,m in enumerate(replacement.data.materials):replacement.data.materials[i]=old_materials.get(m.mmd_material.name_j or m.name,m)
replace_mesh(body,replacement)
for obj in original:
    if obj.name in bpy.data.objects:bpy.data.objects.remove(obj,do_unlink=True)
report['restored_original_foot_region_faces']=len(restored)
report['upper_body_faces_lost']=len(unmatched)
for obj in bpy.data.objects:
    if obj.get('outfit_backup'):obj.parent=None;obj.hide_set(True);obj.hide_render=True

# The socks follow the same new foot pose; their calf UV/morphs remain intact.
poses={s:HeelPose(ankles[s],a.pitch,-.043,baseline_lift+.032,a.toe_forward,a.toe_drop,a.heel_width,a.heel_shift) for s in ('L','R')}
report['body_pose']=deform_mesh(body,poses);report['cloth_pose']=deform_mesh(cloth,poses)
model_objects=[root,*root.children_recursive]
lift_model(model_objects,[body,cloth],arm,a.lift,dressing.apply_positions)
# Foot/toe landmarks move with the posed surface. Keep display axes unchanged.
bpy.context.view_layer.objects.active=arm;arm.hide_set(False);arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for bone in arm.data.edit_bones:
    if not bone.name.endswith(('.L','.R')) or bone.head.z>cut+a.lift:continue
    old=bone.head-Vector((0,0,a.lift));delta=poses[bone.name[-1]](old)-old
    bone.head+=delta;bone.tail+=delta
for side in ('L','R'):
    arm.data.edit_bones['足首.'+side].tail=arm.data.edit_bones['つま先.'+side].head
bpy.ops.object.mode_set(mode='OBJECT')
bone_core.apply_additional_transformation(arm)
bpy.context.view_layer.update()

# Extend the existing stockings over the newly restored full feet. The calf
# boundary comes from the same original target topology; no skin is removed.
sock_cut=cut+a.lift
sock_faces=[f for f in cloth.data.polygons if cloth.data.materials[f.material_index].name=='腿']
sock_material=cloth.data.materials[sock_faces[0].material_index]
sock_uv=cloth.data.uv_layers.active
cloth.data.calc_loop_triangles()
source_ids={f.index for f in sock_faces}
triangles=[t for t in cloth.data.loop_triangles if t.polygon_index in source_ids]
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
trees={}
for side,sign in [('L',1),('R',-1)]:
    tris=[t for t in triangles if sum(cloth.data.vertices[i].co.x for i in t.vertices)*sign>0]
    trees[side]=(BVHTree.FromPolygons([v.co for v in cloth.data.vertices],[t.vertices[:] for t in tris],all_triangles=True),
                 [(t.vertices[:],[Vector((*sock_uv.data[i].uv,0)) for i in t.loops]) for t in tris])
new_faces=[f.index for f in body.data.polygons if (body.data.materials[f.material_index].mmd_material.name_j or body.data.materials[f.material_index].name) in {'Body','Nails'}
           and min(body.data.vertices[i].co.z for i in f.vertices)<sock_cut]
sock,original_ids=garment._copy_mesh_subset(body,new_faces,'FullFootStockings')
sock.data.materials.clear();sock.data.materials.append(sock_material)
for f in sock.data.polygons:f.material_index=0
uv=sock.data.uv_layers.active
for loop in sock.data.loops:
    point=sock.data.vertices[loop.vertex_index].co
    tree,tris=trees['L' if point.x>=0 else 'R'];hit,normal,index,distance=tree.find_nearest(point)
    indices,coords=tris[index]
    mapped=barycentric_transform(hit,*(cloth.data.vertices[i].co for i in indices),*coords)
    uv.data[loop.index].uv=mapped.xy
from mmd_outfit.skin_patch import seam_safe_offsets
deltas,seams=seam_safe_offsets(body,new_faces,.0015)
dressing.apply_positions(sock.data,[v.co+d for v,d in zip(sock.data.vertices,deltas)])
remove={f.index for f in sock_faces if min(cloth.data.vertices[i].co.z for i in f.vertices)<sock_cut}
retained,_=garment._copy_mesh_subset(cloth,[f.index for f in cloth.data.polygons if f.index not in remove],'OutfitStockingTransition')
replace_mesh(cloth,retained)
for obj in bpy.context.selected_objects:obj.select_set(False)
cloth.select_set(True);sock.select_set(True);bpy.context.view_layer.objects.active=cloth;bpy.ops.object.join()
report['stocking_extension']={'foot_faces':len(new_faces),'replaced_lower_faces':len(remove),'skin_faces_removed':0,'margin_m':.0015,'seams':seams}
report['shod_foot_binding']={obj.name:bind_shod_forefoot(obj,arm) for obj in (body,cloth)}

# Append the source assembly in one transaction, then freeze evaluated geometry.
before=set(bpy.data.objects)
with bpy.data.libraries.load(str(asset),link=False) as (source,dest):dest.objects=list(source.objects)
asset_objects=[o for o in dest.objects if o is not None]
asset_collection=bpy.data.collections.new('ImportedShoeReference');bpy.context.scene.collection.children.link(asset_collection)
for obj in asset_objects:
    if obj.name not in bpy.context.scene.objects:asset_collection.objects.link(obj)
group=next(o for o in asset_objects if o.name=='_GROUP_grp')
sources=[o for o in group.children_recursive if o.type in {'MESH','CURVE'} and not o.name.startswith('Stitch Type')]
# Geometry-node pearl/stitch instances must become actual mesh for PMX export.
realize=bpy.data.node_groups.new('ShoeRealizeInstances','GeometryNodeTree')
realize.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');realize.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
i=realize.nodes.new('NodeGroupInput');r=realize.nodes.new('GeometryNodeRealizeInstances');o=realize.nodes.new('NodeGroupOutput')
realize.links.new(i.outputs['Geometry'],r.inputs['Geometry']);realize.links.new(r.outputs['Geometry'],o.inputs['Geometry'])
for obj in sources:
    modifier=obj.modifiers.new('Realize Export Geometry','NODES');modifier.node_group=realize
bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
frozen=[];original_positions={};original_matrices={}
for source in sources:
    evaluated=source.evaluated_get(deps)
    mesh=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=deps)
    if not len(mesh.vertices):continue
    obj=bpy.data.objects.new('Bridal_'+source.name,mesh);bpy.context.scene.collection.objects.link(obj)
    matrix=source.matrix_world.copy()
    original_positions[obj.name]=[matrix@v.co for v in mesh.vertices]
    original_matrices[obj.name]=matrix;frozen.append(obj)
minimum=min(p.z for points in original_positions.values() for p in points)
source_center=-.035
shoe_report=[];shoes=[]
for side,sign in [('L',1),('R',-1)]:
    anchor=arm.data.bones['足首D.'+side].head_local
    transform=Matrix.Translation(Vector((anchor.x+sign*a.shoe_x-sign*source_center*a.scale,a.shoe_y,-minimum*a.scale+.0005)))@Matrix.Diagonal((sign*a.scale,a.scale,a.scale,1))
    for source in frozen:
        obj=source if side=='L' else bpy.data.objects.new(source.name.removesuffix('.L')+'.R',source.data.copy())
        if side=='R':bpy.context.scene.collection.objects.link(obj)
        else:obj.name+='.'+side
        # Right meshes copy the still-canonical coordinates retained separately.
        points=original_positions[source.name.removesuffix('.L')]
        obj.vertex_groups.clear();obj.vertex_groups.new(name='足首D.'+side).add(list(range(len(obj.data.vertices))),1.,'REPLACE')
        obj.parent=arm;obj.matrix_world=transform@original_matrices[source.name.removesuffix('.L')]
        canonical=source.name.removesuffix('.L').removeprefix('Bridal_')
        if canonical in {'Cube','Cylinder','Plane','Sphere','BézierCircle'}:
            pivot=transform@Vector((-.02,.91,-.36))
            obj.matrix_world=Matrix.Translation(pivot)@Matrix.Scale(a.cuff_scale,4)@Matrix.Translation(-pivot)@obj.matrix_world
            obj['cuff_resize']=a.cuff_scale
        modifier=obj.modifiers.new('MMD Armature','ARMATURE');modifier.object=arm
        obj['mmd_garment']=True;obj['external_shoe']=True;shoes.append(obj)
    shoe_report.append({'side':side,'matrix':[list(row) for row in transform]})
for obj in asset_objects:
    if obj.name in bpy.data.objects:bpy.data.objects.remove(obj,do_unlink=True)
report['shoes']=shoe_report;report['shoe_vertices']=sum(len(obj.data.vertices) for obj in shoes)
write_json(out/'fit_report.json',report)
scene=bpy.context.scene;scene.frame_set(1)
render._setup_render(scene,1000,1000);render._setup_lights(scene)
camera_data=bpy.data.cameras.new('BridalFitCamera');camera_data.type='ORTHO';camera_data.ortho_scale=.43
camera=bpy.data.objects.new('BridalFitCamera',camera_data);scene.collection.objects.link(camera);scene.camera=camera
center=Vector((0,.01,.13+a.lift))
for name,direction in [('front',(0,-1,.1)),('side',(1,0,.08)),('oblique',(1,-1,.3)),('back',(0,1,.15))]:
    camera.location=center+Vector(direction).normalized()*3;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
for obj in shoes:obj.hide_render=True
cloth.hide_render=True
for name,direction in [('feet_side',(1,0,.1)),('feet_oblique',(1,-1,.3))]:
    camera.location=center+Vector(direction).normalized()*3;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
for obj in shoes:obj.hide_render=False
cloth.hide_render=False
bpy.context.view_layer.objects.active=body
for obj in bpy.context.selected_objects:obj.select_set(False)
body.select_set(True)
scene.camera=camera
# A useful material-preview viewport when opened interactively.
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.overlay.show_overlays=False
            area.spaces.active.show_gizmo=False
            area.spaces.active.shading.type='MATERIAL'
            area.spaces.active.region_3d.view_distance=.6
            area.spaces.active.region_3d.view_location=center
            area.spaces.active.region_3d.view_rotation=camera.rotation_euler.to_quaternion()
display_meshes={body,cloth,*shoes}
for obj in bpy.context.scene.objects:
    obj.hide_set(obj not in display_meshes)
    if getattr(obj,'mmd_type','')=='ROOT':
        for name in ('show_armature','show_rigid_bodies','show_joints','show_temporary_objects'):
            if hasattr(obj.mmd_root,name):setattr(obj.mmd_root,name,False)
# Migrated rigid objects can have eye states inconsistent with the root flags.
for obj in bpy.context.scene.objects:
    if obj not in display_meshes:obj.hide_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'work.blend'))
if a.export:ie.export_pmx(str(out/'model.pmx'),[root,body,cloth,*shoes])
print('BRIDAL_SHOE_FIT',report,flush=True)
