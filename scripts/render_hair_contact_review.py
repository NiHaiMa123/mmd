"""Matching 1080p orthographic surface evidence; orange marks exact crossings."""
import sys,json,argparse
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords,audit_frame
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--profile',required=True);p.add_argument('--cases',required=True);p.add_argument('--out',required=True);p.add_argument('--component-map');p.add_argument('--component',type=int);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.source).resolve()),load_ui=False,use_scripts=False)
profile=json.loads(Path(a.profile).read_text('utf8'));mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(mesh,arm,profile)
if a.component_map:
 topology=np.load(a.component_map);selected=set(topology['ids'][topology['component']==a.component].tolist());faces=[];polys=[]
 for name in ('hair_root','hair_mobile'):
  for face,poly in zip(parts['faces'].get(name,[]),parts['source_faces'].get(name,[])):
   if all(i in selected for i in face):faces.append(face);polys.append(poly)
  for key in ('faces','source_faces','ids','samples','closed'):parts[key].pop(name,None)
 parts['faces']['hair_mobile']=faces;parts['source_faces']['hair_mobile']=polys;parts['ids']['hair_mobile']=sorted(selected);parts['samples']['hair_mobile']=sorted(selected)[::8];parts['closed']['hair_mobile']=False
out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);cases=json.loads(Path(a.cases).read_text('utf8'));scene=bpy.context.scene
for obj in scene.objects:obj.hide_render=True
camdata=bpy.data.cameras.new('HairContactReview');camdata.type='ORTHO';camdata.ortho_scale=2.2;camera=bpy.data.objects.new('HairContactReview',camdata);scene.collection.objects.link(camera);scene.camera=camera
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
scene.world.color=(.045,.045,.045);shade=scene.display.shading;shade.light='STUDIO';shade.color_type='MATERIAL';shade.show_cavity=True;shade.show_shadows=True;shade.background_type='WORLD'
materials=[]
for name,color in [('Skin',(.55,.59,.64,1)),('Hair',(.12,.36,.62,1)),('Crossing hair triangles',(1,.22,.035,1))]:
 mat=bpy.data.materials.new(name);mat.diffuse_color=color;materials.append(mat)
hairfaces=parts['faces'].get('hair_root',[])+parts['faces'].get('hair_mobile',[]);skinfaces=[f for r,fs in parts['faces'].items() if not r.startswith('hair') for f in fs];rows=[]
for case in cases:
 scene.frame_set(case['frame']);bpy.context.view_layer.update();source=coords(mesh);co=np.load(case['coordinates'])['coordinates'] if case.get('coordinates') else source
 report=audit_frame(mesh,arm,profile,parts,hair=True,cap=1000000,coordinates_m=co*profile.get('units_to_m',1.),return_witness_pairs=True)
 hits={tuple(tri) for r in report['pairs'] if r['pair'][0].startswith('hair') for tri,_ in r.get('witness_pairs',[])}
 hairids=sorted({i for f in hairfaces for i in f});target=Vector((source[hairids].min(0)+source[hairids].max(0))*.5)
 data=bpy.data.meshes.new('ReviewCopy');data.from_pydata(co.tolist(),[],skinfaces+hairfaces);obj=bpy.data.objects.new('ReviewCopy',data);scene.collection.objects.link(obj)
 for mat in materials:data.materials.append(mat)
 for poly in data.polygons:poly.use_smooth=True;poly.material_index=0 if poly.index<len(skinfaces) else 2 if tuple(poly.vertices) in hits else 1
 row={'name':case['name'],'frame':case['frame'],'head_crossings':sum(r['triangle_crossings'] for r in report['pairs'] if r['pair'][0].startswith('hair') and r['pair'][1]=='head'),'body_crossings':sum(r['triangle_crossings'] for r in report['pairs'] if r['pair'][0].startswith('hair') and r['pair'][1]!='head'),'images':[]}
 for view,offset in [('front',(0,-3,0)),('oblique',(2,-2,0)),('side',(3,0,0)),('back',(0,3,0))]:
  camera.location=target+Vector(offset);camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();path=out/f"{case['name']}_{view}.png";scene.render.filepath=str(path);bpy.ops.render.render(write_still=True);row['images'].append(str(path))
 rows.append(row);bpy.data.objects.remove(obj,do_unlink=True);print('HAIR_REVIEW',row['name'],row['head_crossings'],row['body_crossings'],flush=True)
(out/'review.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
