"""Matched before/after geometry replay, one selected bundle, fixed camera."""
import sys,json,argparse
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords,audit_frame
p=argparse.ArgumentParser();p.add_argument('--stills',action='store_true');p.add_argument('--rigid-root-profile');p.add_argument('--root-initial');p.add_argument('--zoom',type=float,default=2.35);p.add_argument('--target-z',type=float,default=-.12);p.add_argument('--sequence-names',action='store_true');p.add_argument('--before');p.add_argument('--component',type=int,default=4);p.add_argument('--after');p.add_argument('--out');p.add_argument('--first',type=int,default=200);p.add_argument('--last',type=int,default=250);p.add_argument('--frame-step',type=int,default=1);p.add_argument('--frames');a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []);engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';root=base/'hair_arm_feedback_20261028';out=Path(a.out).resolve() if a.out else root/('review1080' if a.stills else 'comparison_frames');out.mkdir(parents=True,exist_ok=True);profile=json.loads((base/'body_track/rig_profile.json').read_text('utf8'));profile['pairs']=[]
before=Path(a.before).resolve() if a.before else base/'hair_curves_20261028/single_bundle_rod_frames/SingleBundle_CachedCandidate_NotAccepted.blend';after=Path(a.after).resolve() if a.after else root/'guarded_bundle/SingleBundle_CachedCandidate_NotAccepted.blend';frames=[float(f) for f in a.frames.split(',')] if a.frames else [216,218,219,220,242,249] if a.stills else list(range(a.first,a.last+1,a.frame_step));data=[];parts=None
root_config=json.loads(Path(a.rigid_root_profile).read_text('utf8')) if a.rigid_root_profile else None;root_initial=np.load(a.root_initial) if root_config else None
for path in (before,after):
 bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']]
 if root_config:
  bpy.context.scene.frame_set(1);bpy.context.view_layer.update();root_bind=np.array(arm.matrix_world@arm.pose.bones[root_config['anchor_bone']].matrix);root_ids=np.array(root_config['root_vertex_ids']);root_lookup={int(v):i for i,v in enumerate(root_initial['ids'])};root_points=root_initial['coordinates'][[root_lookup[int(v)] for v in root_ids]]
 if parts is None:
  parts=regions(mesh,arm,profile);topology=np.load(base/'hair_tests_v2/hair_topology.npz');ids=set(root_config['root_vertex_ids']) if root_config else set(topology['ids'][topology['component']==a.component].tolist());faces=[];polys=[]
  for name in ('hair_root','hair_mobile'):
   for f,pi in zip(parts['faces'][name],parts['source_faces'][name]):
    if all(i in ids for i in f):faces.append(f);polys.append(pi)
   for key in ('faces','ids','source_faces','samples','closed'):parts[key].pop(name,None)
  parts['faces']['hair_mobile']=faces;parts['ids']['hair_mobile']=sorted(ids);parts['source_faces']['hair_mobile']=polys;parts['samples']['hair_mobile']=sorted(ids)[::8];parts['closed']['hair_mobile']=False
 values={}
 for frame in frames:
  bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();co=coords(mesh)
  if root_config:
   delta=np.array(arm.matrix_world@arm.pose.bones[root_config['anchor_bone']].matrix)@np.linalg.inv(root_bind);co[root_ids]=root_points@delta[:3,:3].T+delta[:3,3]
  r=audit_frame(mesh,arm,profile,parts,hair=True,cap=1000000,coordinates_m=co,return_witness_pairs=True);hit={tuple(t) for row in r['pairs'] for t,_ in row.get('witness_pairs',[])};values[frame]={'co':co,'hits':hit,'crossings':r['ordinary_crossings']}
 data.append(values)
scene=bpy.context.scene
for o in scene.objects:o.hide_render=True
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.world.color=(.045,.05,.06);s=scene.display.shading;s.light='STUDIO';s.color_type='MATERIAL';s.show_shadows=True;s.show_cavity=True;s.background_type='WORLD'
mats=[]
for name,color in [('Body',(.57,.61,.66,1)),('Selected hair',(.1,.42,.7,1)),('Actual surface crossing',(1,.19,.03,1))]:
 mat=bpy.data.materials.new(name);mat.diffuse_color=color;mats.append(mat)
skin=[f for name,fs in parts['faces'].items() if not name.startswith('hair') for f in fs];hair=parts['faces']['hair_mobile'];objects=[]
for i in range(2):
 me=bpy.data.meshes.new('ComparisonMesh');me.from_pydata(data[i][frames[0]]['co'].tolist(),[],skin+hair);obj=bpy.data.objects.new('Before' if i==0 else 'Arm and hair feedback',me);scene.collection.objects.link(obj)
 for m in mats:me.materials.append(m)
 for poly in me.polygons:poly.use_smooth=True
 objects.append(obj)
camdata=bpy.data.cameras.new('FixedComparisonCamera');camdata.type='ORTHO';camdata.ortho_scale=a.zoom;cam=bpy.data.objects.new('FixedComparisonCamera',camdata);scene.collection.objects.link(cam);scene.camera=cam;target=np.mean(data[1][frames[len(frames)//2]]['co'][parts['ids']['head']],axis=0)+np.array([0,0,a.target_z]);views=[('front',(0,-3,.1)),('side',(-3,0,.1)),('oblique',(-2,-3,.2))] if a.stills else [('oblique',(-2,-3,.2))];rows=[]
for frame_index,frame in enumerate(frames):
 for view,offset in views:
  cam.location=Vector(target)+Vector(offset);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();right=cam.rotation_euler.to_quaternion()@Vector((1,0,0))
  for i,obj in enumerate(objects):
   value=data[i][frame];co=value['co']+np.array(right)*(-a.zoom*.21 if i==0 else a.zoom*.21);obj.data.vertices.foreach_set('co',co.astype(np.float32).ravel());obj.data.update()
   for poly in obj.data.polygons:poly.material_index=0 if poly.index<len(skin) else 2 if tuple(poly.vertices) in value['hits'] else 1
  label=f'{int(frame):04}' if float(frame).is_integer() else f'{frame:08.3f}';name=f'{label}_{view}.png' if a.stills else f'{frame_index+1:04}.png' if a.sequence_names else f'{label}.png';scene.render.filepath=str(out/name);bpy.ops.render.render(write_still=True)
 rows.append({'frame':frame,'before_crossings':data[0][frame]['crossings'],'after_crossings':data[1][frame]['crossings']})
 if frame%10==0:print('ARM_HAIR_COMPARISON_RENDER',frame,flush=True)
(out/'render_report.json').write_text(json.dumps({'inputs':[str(before),str(after)],'selected_bundle_only':not bool(root_config),'rigid_roots_only':bool(root_config),'resolution':[1920,1080],'frames':frames,'samples':rows},indent=2),encoding='utf8')
