import argparse,sys,importlib,shutil
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import write_json
p=argparse.ArgumentParser();p.add_argument('--fit',required=True);p.add_argument('--repair-output');p.add_argument('--assert-neutral',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.fit).resolve()
ie,render=engine('import_export'),engine('extraction');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(out/'work.blend'),load_ui=False,use_scripts=False)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');body=next(o for o in ie.model_meshes() if not o.get('mmd_garment'))
if a.repair_output:
    original_out=out;out=Path(a.repair_output).resolve();out.mkdir(parents=True,exist_ok=True)
    core=importlib.import_module(ie.ensure_mmd_tools()+'.core.bone').FnBone
    core.clean_additional_transformation(arm)
    bpy.context.view_layer.objects.active=arm;arm.hide_set(False);arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    for side in ('L','R'):arm.data.edit_bones['足首.'+side].tail=arm.data.edit_bones['つま先.'+side].head
    bpy.ops.object.mode_set(mode='OBJECT')
    core.apply_additional_transformation(arm);bpy.context.view_layer.update()
    shutil.copyfile(original_out/'fit_report.json',out/'fit_report.json')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'work.blend'))
    scene=bpy.context.scene;render._setup_render(scene,1000,1000);render._setup_lights(scene)
    data=bpy.data.cameras.new('RepairedShoeCamera');data.type='ORTHO';data.ortho_scale=.43
    camera=bpy.data.objects.new('RepairedShoeCamera',data);scene.collection.objects.link(camera);scene.camera=camera;center=Vector((0,.01,.14))
    for name,direction in [('oblique',(1,-1,.3)),('side',(1,0,.08))]:
        camera.location=center+Vector(direction).normalized()*3;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
deps=bpy.context.evaluated_depsgraph_get();axis=arm.data.bones['足首D.L'].head_local.x
trees={};report={'axis_x':axis,'rays':[],'bones':{}}
for b in arm.pose.bones:
    if b.name in ('足首D.L','足先EX.L','足首.L','つま先.L'):
        report['bones'][b.name]={'rest':list(b.bone.head_local),'pose':list(b.matrix.translation),'basis':[list(row) for row in b.matrix_basis]}
for obj in [body,*[o for o in bpy.data.objects if o.get('external_shoe') and o.name.endswith('.L') and 'high heel shoe 3d model' in o.name and 'Merge' not in o.name]]:
    evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
    points=[obj.matrix_world@v.co for v in mesh.vertices]
    if obj==body:report['evaluated_body_max_delta']=max((v.co-w.co).length for v,w in zip(mesh.vertices,body.data.vertices))
    trees[obj.name]=BVHTree.FromPolygons(points,[f.vertices[:] for f in mesh.polygons])
    evaluated.to_mesh_clear()
for y in [i/1000 for i in range(-80,131,10)]:
    row={'y':y,'hits':{}}
    for name,tree in trees.items():
        pos=Vector((axis,y,.35));hits=[]
        for k in range(20):
            hit,normal,index,distance=tree.ray_cast(pos,Vector((0,0,-1)),.5)
            if hit is None or hit.z<-.02:break
            hits.append(round(hit.z,6));pos=hit-Vector((0,0,.00005))
        if hits:row['hits'][name]=hits
    report['rays'].append(row)
report['neutral_foot_head_error_m']=max((Vector(b['pose'])-Vector(b['rest'])).length for b in report['bones'].values())
write_json(out/'clearance_rays.json',report)
report['neutral_tolerance_m']=.0001
if a.assert_neutral:assert report['neutral_foot_head_error_m']<.0001,'Foot IK changes the intended rest pose by more than 0.1 mm'
print('RAY_CLEARANCE',report,flush=True)
copies=[]
for obj in [body,*[o for o in bpy.data.objects if o.get('external_shoe') and o.name.endswith('.L')]]:
    mesh=bpy.data.meshes.new_from_object(obj.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps)
    mesh.transform(obj.matrix_world)
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.bisect_plane(bm,geom=[*bm.verts,*bm.edges,*bm.faces],dist=1e-6,plane_co=Vector((axis,0,0)),plane_no=Vector((1,0,0)),clear_outer=True,clear_inner=False)
    bm.to_mesh(mesh);bm.free();copy=bpy.data.objects.new('Section_'+obj.name,mesh);bpy.context.scene.collection.objects.link(copy);copies.append(copy)
for obj in bpy.data.objects:
    if obj.type=='MESH':obj.hide_render=obj not in copies
scene=bpy.context.scene;render._setup_render(scene,1200,1000);render._setup_lights(scene)
data=bpy.data.cameras.new('ShoeSectionCamera');data.type='ORTHO';data.ortho_scale=.29
camera=bpy.data.objects.new('ShoeSectionCamera',data);scene.collection.objects.link(camera);scene.camera=camera
center=Vector((axis,.015,.12));camera.location=center+Vector((3,0,0));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=str(out/'cross_section.png');bpy.ops.render.render(write_still=True)
