"""Locate real model seam gaps and per-material motion contacts, with closeups."""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json, write_json

parser = argparse.ArgumentParser()
parser.add_argument('--job', required=True)
parser.add_argument('--out')
parser.add_argument('--no-render', action='store_true')
parser.add_argument('--frames', type=int, nargs='+', default=[1,226,256])
parser.add_argument('--torso-only', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
job = Path(args.job).resolve()
result, request = read_json(job/'result.json'), read_json(job/'request.json')
profile = read_json(job/'profile_snapshot.json')
out = Path(args.out).resolve() if args.out else job/'region_review'
out.mkdir(exist_ok=True)
ie, qa, motion, dressing, render = [engine(n) for n in ('import_export','qa','motion','dressing','extraction')]
bpy.ops.wm.open_mainfile(filepath=result['blend'])
meshes = ie.model_meshes(list(bpy.data.objects))
body = next(o for o in meshes if not o.get('mmd_garment'))
cloth = next(o for o in meshes if o.get('mmd_garment'))
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
axis = (arm.data.bones['中指１.L'].head_local-arm.data.bones['手首.L'].head_local).normalized()
wrist = arm.data.bones['手首.L'].head_local
positions = defaultdict(list)
for v in body.data.vertices:
    if (v.co-wrist).dot(axis) < -.025 or (v.co-wrist).length > .15:
        continue
    positions[tuple(round(c,6) for c in v.co)].append(v)
seams = []
for key, vertices in positions.items():
    if len(vertices) < 2:
        continue
    spread = max((a.normal-b.normal).length for a in vertices for b in vertices)*.0015
    if spread > .00005:
        seams.append({'position':key,'duplicates':len(vertices),'offset_gap_m':spread,
                      'normals':[list(v.normal) for v in vertices]})
seams.sort(key=lambda x:-x['offset_gap_m'])
write_json(out/'seams.json',{'left_hand_split_positions':len(positions),'offset_seams':len(seams),'largest':seams[:30]})
ie.clear_scene()
objects = ie.import_pmx(result['pmx'])
mesh = ie.model_meshes(objects)[0]
arm = next(o for o in objects if o.type == 'ARMATURE')
split = qa.split_faces(objects,profile['selected_materials'])
region = [qa.body_region(n) for n in dressing.dominant_bones(mesh)]
dominant = dressing.dominant_bones(mesh)
vertex_mats = defaultdict(set)
for f in mesh.data.polygons:
    for i in f.vertices:
        vertex_mats[i].add(mesh.data.materials[f.material_index].name)
me, ev = qa._evaluated_mesh(mesh)
probe = qa._ContactProbe(mesh,split['garment_faces'],me,me,split['skin_faces'],region,1)
signs = probe.reference
ev.to_mesh_clear()
for obj in bpy.context.selected_objects:
    obj.select_set(False)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
motion_path=result.get('effective_motion') or request['motion']
bpy.ops.mmd_tools.import_vmd(filepath=motion_path,scale=.08,rename_bones=True,log_level='ERROR')
scene = bpy.context.scene
render._setup_render(scene,1000,1000)
render._setup_lights(scene)
data = bpy.data.cameras.new('RegionReview')
data.type='ORTHO'
camera=bpy.data.objects.new('RegionReview',data)
scene.collection.objects.link(camera)
scene.camera=camera
reports=[]
for frame in args.frames:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    me,ev=qa._evaluated_mesh(mesh)
    bvh=motion._bvh_from(me,probe.faces)
    count,checked,hits=probe.sample(me,me,split['skin_faces'],1,frame,region)
    rows=[]
    for i in hits:
        loc,normal,index,dist=bvh.find_nearest(me.vertices[i].co)
        cloth_face=mesh.data.polygons[probe.faces[index]]
        rows.append({'vertex':i,'skin_materials':sorted(vertex_mats[i]),'bone':dominant[i],
                     'region':region[i],'cloth_material':mesh.data.materials[cloth_face.material_index].name,
                     'distance_m':dist,'position':list(me.vertices[i].co)})
    reports.append({'frame':frame,'pierced':count,'checked':checked,'materials':dict(Counter('/'.join(r['skin_materials']) for r in rows)),
                    'regions':dict(Counter(r['region'] for r in rows)),'hits':rows})
    ev.to_mesh_clear()
    if args.no_render:
        continue
    torso=arm.pose.bones['上半身2']
    orientation=(arm.matrix_world@torso.matrix@torso.bone.matrix_local.inverted()).to_3x3()
    def shot(name,center,size,direction):
        # Dance turns must not swap a requested front closeup for the hair.
        camera.location=center+(orientation@Vector(direction)).normalized()*3
        camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        data.ortho_scale=size
        scene.render.filepath=str(out/f'{frame}_{name}.png')
        bpy.ops.render.render(write_still=True)
    for side in (() if args.torso_only else ('L','R')):
        def digit(name):
            return name.endswith('.'+side) and name[:-2].startswith(('手首','親指','人指','中指','薬指','小指'))
        allowed={i for i,n in enumerate(dominant) if digit(n)}
        current,owner=qa._evaluated_mesh_copy(mesh)
        points=[current.vertices[i].co.copy() for i in allowed]
        center=Vector(tuple((min(p[a] for p in points)+max(p[a] for p in points))*.5 for a in range(3)))
        shot('hand_'+side,center,.20,(0,-1,.1))
        shot('hand_'+side+'_back',center,.20,(0,1,.1))
        bm=bmesh.new()
        bm.from_mesh(current)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if not all(v.index in allowed for v in f.verts)],context='FACES')
        bm.to_mesh(current)
        bm.free()
        isolated=bpy.data.objects.new('IsolatedHand',current)
        scene.collection.objects.link(isolated)
        mesh.hide_render=True
        shot('hand_'+side+'_isolated',center,.20,(0,-1,.1))
        shot('hand_'+side+'_isolated_back',center,.20,(0,1,.1))
        mesh.hide_render=False
        bpy.data.objects.remove(isolated,do_unlink=True)
        bpy.data.meshes.remove(current)
    low=arm.matrix_world@arm.pose.bones['下半身'].head
    neck=arm.matrix_world@arm.pose.bones['首'].head
    shot('torso',low.lerp(neck,.5),max(.4,(neck-low).length*1.4),(0,-1,0))
    shot('torso_side',low.lerp(neck,.5),max(.4,(neck-low).length*1.4),(1,-1,0))
    shot('torso_opposite',low.lerp(neck,.5),max(.4,(neck-low).length*1.4),(-1,-1,0))
write_json(out/'report.json',{'seams':seams[:10],'motion_path':motion_path,
    'seams_scope':'hypothetical normal offset of retained skin; covered skin backups are excluded',
    'isolation_scope':'isolated views have open cuts at selection boundaries; visible interiors are not proof of full-model exposure',
    'skin_coverage':[p.get('skin_coverage',{}) for p in result.get('adaptations',{}).get('patches',[])],
    'motion':reports,**probe.report()})
print('REGION_REVIEW',[(r['frame'],r['materials'],r['regions']) for r in reports],flush=True)
