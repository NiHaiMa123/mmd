"""Localize actual arm/cloth triangle crossings, retaining alpha and context."""
import argparse
from collections import Counter
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Vector
from mathutils.geometry import barycentric_transform
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
parser=argparse.ArgumentParser()
parser.add_argument('--job',required=True); parser.add_argument('--out',required=True)
parser.add_argument('--frames',type=int,nargs='+',default=[1,61,226,256])
parser.add_argument('--no-render',action='store_true')
parser.add_argument('--physics',action='store_true',help='Continuously simulate from frame 1 before each sampled shot')
parser.add_argument('--sleeve-only',action='store_true',help='Diagnostic only: keep sleeve dynamics and body-follow colliders')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
out=Path(args.out).resolve()
job=Path(args.job).resolve(); request,result=read_json(job/'request.json'),read_json(job/'result.json')
profile=read_json(job/'profile_snapshot.json')
ie,qa,motion,dressing,render=[engine(n) for n in ('import_export','qa','motion','dressing','extraction')]
ie.clear_scene(); objects=ie.import_pmx(result['pmx']); mesh=ie.model_meshes(objects)[0]
arm=next(o for o in objects if o.type=='ARMATURE')
split=qa.split_faces(objects,profile['selected_materials'])
cloth_faces,visibility=engine('visibility').visible_garment_faces(mesh,split['garment_faces'])
garment_ids={i for fi in split['garment_faces'] for i in mesh.data.polygons[fi].vertices}
reference_edges=[(e.vertices[0],e.vertices[1],(mesh.data.vertices[e.vertices[0]].co-mesh.data.vertices[e.vertices[1]].co).length)
                 for e in mesh.data.edges if all(i in garment_ids for i in e.vertices)]
dominant=dressing.dominant_bones(mesh)
def arm_domain(name):
    return name.endswith(('.L','.R')) and name[:-2].startswith(('腕','ひじ','手首','手捩'))
body_faces=[fi for fi in split['skin_faces'] if sum(arm_domain(dominant[i]) for i in mesh.data.polygons[fi].vertices)>=2]
arm.select_set(True); bpy.context.view_layer.objects.active=arm
bpy.ops.mmd_tools.import_vmd(filepath=result.get('effective_motion') or request['motion'],scale=.08,rename_bones=True,log_level='ERROR')
scene=bpy.context.scene
physics_subset=None
if args.sleeve_only:
    if not args.physics:raise ValueError('--sleeve-only requires --physics')
    rigids={o for o in objects if getattr(o,'mmd_type','')=='RIGID_BODY'}
    kept={o for o in rigids if str(o.mmd_rigid.type)=='0' or o.mmd_rigid.bone.startswith(('袖_','袖口補助','袖環'))}
    joints=[o for o in objects if getattr(o,'mmd_type','')=='JOINT']
    removed_joints=[o for o in joints if o.rigid_body_constraint.object1 not in kept or o.rigid_body_constraint.object2 not in kept]
    physics_subset={'kept_rigids':len(kept),'removed_rigids':len(rigids-kept),'removed_joints':len(removed_joints),
                    'scope':'local sleeve diagnostic; other garment and hair physics omitted in this in-memory scene'}
    for obj in removed_joints+list(rigids-kept):bpy.data.objects.remove(obj,do_unlink=True)
setup=engine('physics_sim').setup_native(scene,arm,1,max(args.frames)) if args.physics else None
out.mkdir(parents=True,exist_ok=True)
if not args.no_render:
    render._setup_render(scene,1000,1000); render._setup_lights(scene)
    data=bpy.data.cameras.new('SleeveContactCamera'); data.type='ORTHO'
    camera=bpy.data.objects.new('SleeveContactCamera',data); scene.collection.objects.link(camera); scene.camera=camera
images={}
def opacity(me,fi,point):
    face=me.polygons[fi]; material=me.materials[face.material_index]
    node=material.node_tree.nodes.get('mmd_base_tex') if material.use_nodes else None
    if node is None or node.image is None or not me.uv_layers.active: return 1.
    image=node.image
    if image.name not in images:
        w,h=image.size; values=np.empty(w*h*4,dtype=np.float32); image.pixels.foreach_get(values)
        images[image.name]=values.reshape(h,w,4)[:,:,3]
    alpha=images[image.name]; h,w=alpha.shape
    uv=me.uv_layers.active
    mapped=barycentric_transform(point,*(me.vertices[i].co for i in face.vertices),
        *(Vector((*uv.data[i].uv,0)) for i in face.loop_indices))
    x,y=mapped.x*w-.5,mapped.y*h-.5; ix,iy=int(np.floor(x)),int(np.floor(y)); fx,fy=x-ix,y-iy
    return float(sum(alpha[(iy+dy)%h,(ix+dx)%w]*(fx if dx else 1-fx)*(fy if dy else 1-fy)
                     for dx in (0,1) for dy in (0,1)))

def crossings(a,b):
    result=[]
    for first,second in ((a,b),(b,a)):
        u,v=second[1]-second[0],second[2]-second[0]
        normal=u.cross(v)
        if normal.length<1e-12: continue
        normal.normalize()
        signed=[(p-second[0]).dot(normal) for p in first]
        if min(signed)>-1e-7 or max(signed)<1e-7: continue
        for i,j in ((0,1),(1,2),(2,0)):
            if signed[i]*signed[j]>=0: continue
            point=first[i].lerp(first[j],signed[i]/(signed[i]-signed[j]))
            d=point-second[0]
            uu,uv,vv,du,dv=u.dot(u),u.dot(v),v.dot(v),d.dot(u),d.dot(v)
            den=uu*vv-uv*uv
            if abs(den)<1e-20: continue
            s,t=(du*vv-dv*uv)/den,(dv*uu-du*uv)/den
            if s>=-1e-6 and t>=-1e-6 and s+t<=1+1e-6 and not any((point-p).length<1e-6 for p in result):
                result.append(point)
    return result

reports=[];helper_tracks=[];last_helper_local={}
helper_names=[b.name for b in arm.data.bones if b.name.startswith(('袖口補助','袖環'))]
for frame in (range(1,max(args.frames)+1) if args.physics else args.frames):
    scene.frame_set(frame); bpy.context.view_layer.update()
    if helper_names:
        evaluated_arm=arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
        row={'frame':frame,'max_local_step_m':0.,'max_from_parent_rest_m':0.}
        for name in helper_names:
            pose=evaluated_arm.pose.bones[name];parent=pose.parent
            local=parent.matrix.inverted()@pose.matrix.translation
            rest=parent.bone.matrix_local.inverted()@pose.bone.head_local
            row['max_from_parent_rest_m']=max(row['max_from_parent_rest_m'],(local-rest).length)
            if name in last_helper_local:row['max_local_step_m']=max(row['max_local_step_m'],(local-last_helper_local[name]).length)
            last_helper_local[name]=local.copy()
        helper_tracks.append(row)
    if frame not in args.frames:continue
    me,owner=qa._evaluated_mesh(mesh)
    bvh=motion._bvh_from(me,body_faces); cvh=motion._bvh_from(me,cloth_faces)
    pairs=bvh.overlap(cvh); rows=[]
    for bi,ci in pairs:
        bf,cf=body_faces[bi],cloth_faces[ci]
        points=crossings([me.vertices[i].co for i in me.polygons[bf].vertices],
                         [me.vertices[i].co for i in me.polygons[cf].vertices])
        if len(points)<2 or max((a-b).length for a in points for b in points)<1e-6: continue
        center=sum(points,Vector())/len(points); alpha=opacity(me,cf,center)
        if alpha<.01: continue
        body_bones=Counter(dominant[i] for i in me.polygons[bf].vertices)
        cloth_bones=Counter(dominant[i] for i in me.polygons[cf].vertices)
        rows.append({'body_face':bf,'cloth_face':cf,'body_bones':dict(body_bones),'cloth_bones':dict(cloth_bones),
            'cloth_material':me.materials[me.polygons[cf].material_index].name,
            'alpha_at_center':alpha,'points':[list(p) for p in points],'center':list(center)})
    report={'frame':frame,'candidate_pairs':len(pairs),'crossing_pairs':len(rows),
            'by_material':dict(Counter(row['cloth_material'] for row in rows)),'crossings':rows,
            'deformation':qa._edge_stretch(reference_edges,me.vertices)}
    reports.append(report)
    owner.to_mesh_clear()
    if args.no_render: continue
    orientation=(arm.matrix_world@arm.pose.bones['上半身2'].matrix@arm.data.bones['上半身2'].matrix_local.inverted()).to_3x3()
    for side in ('L','R'):
        elbow=arm.matrix_world@arm.pose.bones['ひじ.'+side].head
        wrist=arm.matrix_world@arm.pose.bones['手首.'+side].head
        center=elbow.lerp(wrist,.5)
        data.ortho_scale=max(.30,(elbow-wrist).length*1.7)
        for name,direction in (('front',(0,-1,.2)),('side',((1 if side=='L' else -1),-.6,.2))):
            camera.location=center+(orientation@Vector(direction)).normalized()*3
            camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
            scene.render.filepath=str(out/f'{frame}_{side}_{name}.png'); bpy.ops.render.render(write_still=True)
write_json(out/'report.json',{'visibility':visibility,'motion':reports,'physics':args.physics,'setup':setup,'physics_subset':physics_subset,
    'helper_tracks':helper_tracks,
    'scope':'non-coplanar triangle crossing segments with sampled base alpha; not a visibility/penetration-depth proof'})
print('SLEEVE_CROSSINGS',[(r['frame'],r['crossing_pairs'],r['by_material']) for r in reports],flush=True)
if args.physics:
    # Free the Bullet world before Blender tears down individual model objects.
    # Otherwise its shutdown order can release a body before its constraints.
    constraints=[o for o in bpy.data.objects if o.rigid_body_constraint is not None]
    bpy.data.batch_remove(ids=constraints)
    bpy.context.view_layer.update()
    bpy.ops.rigidbody.world_remove()
    print('PHYSICS_DIAGNOSTIC_WORLD_REMOVED',flush=True)
