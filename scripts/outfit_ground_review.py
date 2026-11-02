"""Independently re-import the generated VMD and verify every shoe frame."""
import argparse
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.jobs import read_json,write_json
from mmd_outfit.service import engine
from mmd_outfit.motion_grounding import split_vmd,bone_name
parser=argparse.ArgumentParser();parser.add_argument('--job',required=True);parser.add_argument('--grounded',required=True);parser.add_argument('--out',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);job=Path(args.job);grounded=Path(args.grounded);out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
result,profile=read_json(job/'result.json'),read_json(job/'profile_snapshot.json')
report_path=grounded/'report.json' if (grounded/'report.json').exists() else grounded/'motion/grounding_report.json'
model_path=grounded/'model.pmx' if (grounded/'model.pmx').exists() else grounded/'model/model.pmx'
report=read_json(report_path);ie,render=engine('import_export'),engine('extraction')
ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=result['blend'])
cloth=next(o for o in ie.model_meshes() if o.get('mmd_garment'))
start,end=result['adaptations']['shoes']['attached_vertex_range']
reference=[cloth.data.vertices[i].co.copy() for i in range(start,end)]
tree=KDTree(len(reference))
for i,p in enumerate(reference):tree.insert(p,i)
tree.balance()
source=Path(report['source']).read_bytes();output=Path(report['motion']).read_bytes()
h,a,t=split_vmd(source);hh,b,tt=split_vmd(output)
assert h==hh and t==tt and [r for r in a if bone_name(r)!='全ての親']==[r for r in b if bone_name(r)!='全ての親']
worst=min(report['per_frame'],key=lambda row:min(row['before'].values()))['vmd_frame']+1
shots=sorted({1,256,worst})
checks=[];images=[]
for phase,path in [('before',report['source']),('after',report['motion'])]:
    ie.clear_scene();objects=ie.import_pmx(str(model_path))
    mesh=ie.model_meshes(objects)[0];arm=next(o for o in objects if o.type=='ARMATURE')
    matching={v.index for v in mesh.data.vertices if tree.find(v.co)[2]<1e-5}
    ids=sorted({i for face in mesh.data.polygons if mesh.data.materials[face.material_index].name in profile['shoe_fit']['materials']
                and all(i in matching for i in face.vertices) for i in face.vertices})
    assert len(ids)==len(reference)
    sides={s:[i for i in ids if mesh.data.vertices[i].co.x*(1 if s=='L' else -1)>0] for s in ('L','R')}
    local={}
    for side,values in sides.items():
        transform=arm.data.bones['足首D.'+side].matrix_local.inverted()@mesh.matrix_world
        local[side]=np.asarray([tuple(transform@mesh.data.vertices[i].co) for i in values])
    scene=bpy.context.scene;scene.frame_set(1)
    arm.select_set(True);bpy.context.view_layer.objects.active=arm
    bpy.ops.mmd_tools.import_vmd(filepath=path,scale=.08,rename_bones=True,margin=0,log_level='ERROR')
    hidden=[(o,o.hide_viewport) for o in bpy.data.objects if o.type=='MESH']
    rows=[]
    for o,previous in hidden:o.hide_viewport=True
    frames=range(1,report['frames']+1) if phase=='after' else shots
    for frame in frames:
        scene.frame_set(frame);bpy.context.view_layer.update()
        evaluated=arm.evaluated_get(bpy.context.evaluated_depsgraph_get());row={'frame':frame,'sides':{}}
        for side,points in local.items():
            matrix=np.asarray(arm.matrix_world@evaluated.pose.bones['足首D.'+side].matrix)
            row['sides'][side]=float((points@matrix[:3,:3].T+matrix[:3,3])[:,2].min())
        rows.append(row)
        if frame%1000==0:print('GROUND_REVIEW',phase,frame,flush=True)
    for o,previous in hidden:o.hide_viewport=previous
    mesh_checks=[]
    render._setup_render(scene,900,700);render._setup_lights(scene)
    bpy.ops.mesh.primitive_plane_add(size=30,location=(0,0,0));plane=bpy.context.object;plane.name='GroundReviewFloor'
    material=bpy.data.materials.new('GroundReviewFloor');material.diffuse_color=(.16,.18,.22,1);plane.data.materials.append(material)
    camera_data=bpy.data.cameras.new('GroundReviewCamera');camera_data.type='ORTHO'
    camera=bpy.data.objects.new('GroundReviewCamera',camera_data);scene.collection.objects.link(camera);scene.camera=camera
    for frame in shots:
        scene.frame_set(frame);bpy.context.view_layer.update()
        current=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());me=current.to_mesh()
        minima={s:min(me.vertices[i].co.z for i in values) for s,values in sides.items()}
        current.to_mesh_clear();mesh_checks.append({'frame':frame,'sides':minima})
        center=sum((arm.matrix_world@arm.pose.bones['足首D.'+s].head for s in ('L','R')),Vector())*.5
        center.z=.065;camera_data.ortho_scale=.48
        camera.location=center+Vector((1,-1,.35)).normalized()*3
        camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(out/f'{phase}_{frame}.png');bpy.ops.render.render(write_still=True);images.append(scene.render.filepath)
    checks.append({'phase':phase,'frames':len(rows),'minimum_m':min(min(r['sides'].values()) for r in rows),
                   'mesh_samples':mesh_checks,'per_frame':rows})
after=checks[-1]
assert after['minimum_m']>=report['clearance_m']-1e-5,after['minimum_m']
assert min(min(r['sides'].values()) for r in after['mesh_samples'])>=report['clearance_m']-1e-5
result={'source_root_only_change_verified':True,'worst_original_blender_frame':worst,'checks':checks,'images':images,
        'scope':'full-frame Blender armature verification plus real mesh samples; native MMD dynamics not accepted'}
write_json(out/'report.json',result)
print('GROUND_REVIEW_OK',after['frames'],after['minimum_m'],flush=True)
