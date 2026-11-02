"""Render head proportions with fixed cameras, crop, lighting and neck origin."""
import argparse,sys,json
from pathlib import Path
import bpy
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
ie,render=engine('import_export'),engine('extraction');ie.ensure_mmd_tools()
profile=read_json(ROOT/'outputs/outfit_v09_final/20261024T114717Z_79592d70af/profile_snapshot.json')
reference=read_json(ROOT/'outputs/keqing_head/inspection/inventory.json')
target_neck=Vector(next(b['head'] for b in reference['target']['bones'] if b['name']=='首'))
rows=[('daniya_before',ROOT/'outputs/white_bridal_shoes/checked/Daniya_WhiteBridal_FitChecked.blend',False),
      ('keqing_previous',ROOT/'outputs/keqing_head/final/work.blend',False),
      ('keqing_corrected',Path(a.candidate).resolve(),False),('keqing_original',Path(profile['source']['path']),True)]
report={'camera':{'type':'ORTHO','portrait_scale_m':.58,'portrait_center':[0,.04,1.40],'full_scale_m':1.82,'same_camera_and_lighting':True},'models':{}}
for label,path,source in rows:
    if source:
        ie.clear_scene();objects=ie.import_pmx(str(path));arm=next(o for o in objects if o.type=='ARMATURE');root=ie.mmd_root(arm)
        translation=target_neck-arm.matrix_world@arm.data.bones['首'].head_local
        root.matrix_world=Matrix.Translation(translation)@root.matrix_world;bpy.context.view_layer.update()
    else:
        bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False);arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
    meshes=ie.model_meshes();body=next((o for o in meshes if not o.get('mmd_garment')),meshes[0])
    face_name='face1' if label=='daniya_before' else '面'
    face_ids={i for f in body.data.polygons if (body.data.materials[f.material_index].mmd_material.name_j or body.data.materials[f.material_index].name)==face_name for i in f.vertices}
    points=[body.matrix_world@body.data.vertices[i].co for i in face_ids]
    neck=arm.data.bones['首'];head=arm.data.bones['頭'];neck_base=arm.matrix_world@neck.head_local
    chin=min(p.z for p in points);face_width=max(p.x for p in points)-min(p.x for p in points)
    report['models'][label]={'path':str(path),'face_width_m':face_width,'chin_z_m':chin,'chin_above_neck_root_m':chin-neck_base.z,
                             'neck_bone_length_m':(arm.matrix_world@neck.tail_local-neck_base).length,
                             'head_pivot_z_m':(arm.matrix_world@head.head_local).z,'reference_translation_only':source}
    for obj in bpy.data.objects:
        if obj.type=='MESH':obj.hide_render=obj not in meshes
    scene=bpy.context.scene;render._setup_render(scene,1000,1000);render._setup_lights(scene)
    data=bpy.data.cameras.new('HeadProportionCompare');data.type='ORTHO'
    camera=bpy.data.objects.new('HeadProportionCompare',data);scene.collection.objects.link(camera);scene.camera=camera
    for name,direction in [('front',(0,-1,0)),('side',(1,0,0)),('full',(0,-1,0))]:
        center=Vector((0,.04,.82 if name=='full' else 1.40));data.ortho_scale=1.82 if name=='full' else .58
        camera.location=center+Vector(direction)*3;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(out/f'{label}_{name}.png');bpy.ops.render.render(write_still=True)
    print('HEAD_PROPORTION',label,json.dumps(report['models'][label]),flush=True);write_json(out/'measurements.json',report)
print('HEAD_PROPORTIONS_COMPARED',flush=True)
