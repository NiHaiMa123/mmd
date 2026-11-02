import sys,json,math
from pathlib import Path
from collections import defaultdict,Counter
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords,crosses
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=base/'hair_tests_v2';out.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(base/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False)
p=json.loads((base/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);units=p.get('units_to_m',1.)
hairfaces=parts['faces']['hair_root']+parts['faces']['hair_mobile'];hairids=sorted({i for f in hairfaces for i in f});parent={i:i for i in hairids}
def find(i):
 while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
 return i
def union(a,b):
 a,b=find(a),find(b)
 if a!=b:parent[b]=a
for f in hairfaces:
 for a,b in zip(f,(f[1],f[2],f[0])):union(a,b)
rest=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices])*units;weld={}
for i in hairids:
 key=tuple(np.rint(rest[i]*1e6).astype(int))
 if key in weld:union(i,weld[key])
 else:weld[key]=i
component_roots=sorted({find(i) for i in hairids});index={n:j for j,n in enumerate(component_roots)};component={i:index[find(i)] for i in hairids};comps=defaultdict(list)
for i,c in component.items():comps[c].append(i)
anchors={mesh.vertex_groups[n].index for n in p['root_hair_anchor_bones'] if n in mesh.vertex_groups};bonegroups={g.index:g.name for g in mesh.vertex_groups if g.name in arm.pose.bones};headweight={i:sum(g.weight for g in mesh.data.vertices[i].groups if g.group in anchors) for i in hairids}
stats=[]
source_polys=parts['source_faces']['hair_root']+parts['source_faces']['hair_mobile']
for c,ids in comps.items():
 weights=Counter()
 for i in ids:
  for g in mesh.data.vertices[i].groups:
   if g.group in bonegroups:weights[bonegroups[g.group]]+=g.weight
 materials=Counter(mesh.material_slots[mesh.data.polygons[poly].material_index].name for f,poly in zip(hairfaces,source_polys) if component[f[0]]==c)
 stats.append({'component':c,'vertices':len(ids),'triangles':sum(component[f[0]]==c for f in hairfaces),'min':rest[ids].min(0).tolist(),'max':rest[ids].max(0).tolist(),'anchor_weight_min':min(headweight[i] for i in ids),'anchor_weight_max':max(headweight[i] for i in ids),'dominant_bones':weights.most_common(8),'materials':materials.most_common()})
rows=[];allpairs=[]
for frame in (1,100,226,240,285,361,450):
 bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();co=coords(mesh)*units;world=co.tolist();hairtree=BVHTree.FromPolygons(world,hairfaces,all_triangles=True);hits=[]
 for region in ('head','torso','arm.L','arm.R','hand.L','hand.R','leg.L','leg.R'):
  fs=parts['faces'][region];tree=BVHTree.FromPolygons(world,fs,all_triangles=True)
  for ia,ib in hairtree.overlap(tree):
   ta,tb=hairfaces[ia],fs[ib]
   if crosses([Vector(co[i]) for i in ta],[Vector(co[i]) for i in tb]):
    hit={'hair_triangle':list(ta),'body_triangle':list(tb),'region':region,'component':component[ta[0]],'point':co[list(ta)].mean(0).tolist(),'anchor_weight_mean':sum(headweight[i] for i in ta)/3};hits.append(hit)
 row={'frame':frame,'crossings':len(hits),'by_region':dict(Counter(h['region'] for h in hits)),'by_component':dict(Counter(h['component'] for h in hits)),'hits':hits};rows.append(row);print('HAIR_COMPONENT_AUDIT',frame,len(hits),row['by_region'],flush=True)
report={'components':stats,'component_count':len(stats),'hair_vertices':len(hairids),'frames':rows,'note':'Includes rigid/head-weighted hair vs head; no attachment exemptions applied'}
(out/'component_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');np.savez_compressed(out/'hair_topology.npz',ids=hairids,faces=hairfaces,component=np.array([component[i] for i in hairids]))
# Diagnostic render uses evaluated copies, source data is never edited.
scene=bpy.context.scene
for obj in scene.objects:obj.hide_render=True
camera_data=bpy.data.cameras.new('HairContactAudit');camera_data.type='ORTHO';camera_data.ortho_scale=.70;camera=bpy.data.objects.new('HairContactAudit',camera_data);scene.collection.objects.link(camera);scene.camera=camera
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1080;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.world.color=(.12,.12,.12);shade=scene.display.shading;shade.light='STUDIO';shade.color_type='MATERIAL';shade.show_cavity=True;shade.show_shadows=True;shade.background_type='WORLD'
mats=[]
for name,col in [('Body',(.58,.62,.67,1)),('Hair',(.23,.43,.66,1)),('HairCollision',(1,.22,.10,1))]:
 m=bpy.data.materials.new(name);m.diffuse_color=col;mats.append(m)
for frame in (1,240):
 scene.frame_set(frame);bpy.context.view_layer.update();co=coords(mesh)*units;hitfaces={tuple(h['hair_triangle']) for r in rows if r['frame']==frame for h in r['hits']};skinfaces=[f for r,fs in parts['faces'].items() if not r.startswith('hair') for f in fs];faces=skinfaces+hairfaces;data=bpy.data.meshes.new('ContactCopy');data.from_pydata(co.tolist(),[],faces);obj=bpy.data.objects.new('ContactCopy',data);scene.collection.objects.link(obj)
 for mat in mats:data.materials.append(mat)
 for poly in data.polygons:poly.use_smooth=True;poly.material_index=0 if poly.index<len(skinfaces) else 2 if tuple(poly.vertices) in hitfaces else 1
 target=arm.matrix_world@arm.pose.bones['頭'].head+Vector((0,0,-.08))
 for name,offset in [('front',(0,-3,0)),('side',(3,0,0)),('back',(0,3,0))]:
  camera.location=target+Vector(offset);camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'audit_f{frame:04}_{name}.png');bpy.ops.render.render(write_still=True)
 bpy.data.objects.remove(obj,do_unlink=True)
print('HAIR_V2_DIAGNOSIS_READY',out,flush=True)
