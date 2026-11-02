"""Save a reviewable numerical cloth probe with its actual portable cache."""
import sys,json,math,struct
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,Quaternion
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,add_glove_hands
folder=ROOT/'outputs/cynical_cloth15/contact_motion/sequence_v5/temporal/ppf/coherent_probe_untangled_clean';manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'));engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=manifest['source'],load_ui=False,use_scripts=False);scene=bpy.context.scene;arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];cloth=bpy.data.objects['Cloth'];reference=arm.animation_data.action;reference.use_fake_user=True;preview=reference.copy();preview.name='PPF_probe_with_recorded_preroll';preview.use_fake_user=True
for f in range(1,47):
    arm.animation_data.action=reference;scene.frame_set(f);strength=1-((f-1)/45)**2*(3-2*(f-1)/45);quats=[]
    for side,sign in (('L',-1),('R',1)):
        bone=arm.pose.bones['腕.'+side];axis=(arm.matrix_world@bone.matrix).to_3x3().inverted()@Vector((0,1,0));quats.append(bone.rotation_quaternion@Quaternion(axis,sign*math.radians(manifest['preroll_arm_open_degrees'])*strength))
    arm.animation_data.action=preview
    for side,q in zip(('L','R'),quats):b=arm.pose.bones['腕.'+side];b.rotation_quaternion=q;b.keyframe_insert(data_path='rotation_quaternion',frame=f,group=b.name)
arm.animation_data.action=preview
for o in bpy.data.objects:o.hide_render=True;o.hide_set(True)
body.hide_render=False;body.hide_set(False);body.color=(.40,.46,.58,1)
for o in engine('import_export').model_meshes():
    if o.get('external_shoe') or o.name=='Stockings':o.hide_render=False;o.hide_set(False)
regions=skin_regions(body,arm);add_glove_hands(regions,body,arm,cloth)
for o in regions['extra_objects']:o.hide_render=False;o.hide_set(False);o.color=(.74,.46,.16,1)
names={g.index:g.name for g in cloth.vertex_groups if g.name in arm.pose.bones};dominant=[max(((g.weight,names[g.group]) for g in v.groups if g.group in names),default=(0,''))[1] for v in cloth.data.vertices];fs=[f.index for f in cloth.data.polygons if all(dominant[i].startswith(('上半身','下半身','胸','首','おっぱい','乳')) and cloth.data.vertices[i].co.z>.88 for i in f.vertices)];torso,_=engine('garment')._copy_mesh_subset(cloth,fs,'TorsoVisualReferenceOnly');torso.modifiers.new('Reference skinning','ARMATURE').object=arm;torso.hide_render=False;torso.hide_set(False);torso.color=(.3,.19,.55,1)
source=bpy.data.objects['ClothSimulationSurface'];mesh=source.data.copy();obj=bpy.data.objects.new('PPF_ActualClothProbe',mesh);scene.collection.objects.link(obj);obj.matrix_world=source.matrix_world;obj.color=(.6,.49,.85,1);obj.hide_set(False);obj.hide_render=False
arr=np.load(folder/'PPFCloth.npy');inverse=np.asarray(obj.matrix_world.inverted());arr=(arr@inverse[:3,:3].T+inverse[:3,3]).astype('<f4');cache=folder/'PhysicsProbeClothLocal.pc2'
with cache.open('wb') as handle:handle.write(struct.pack('<12siiffi',b'POINTCACHE2\0',1,arr.shape[1],0.,1.,len(arr)));handle.write(arr.tobytes())
mod=obj.modifiers.new('Actual PPF results, no armature','MESH_CACHE');mod.cache_format='PC2';mod.filepath=str(cache);mod.play_mode='SCENE';mod.time_mode='FRAME';mod.frame_start=1;mod.frame_scale=1.;mod.deform_mode='OVERWRITE';mod.interpolation='LINEAR'
camdata=bpy.data.cameras.new('PhysicsProbeReview');camdata.type='ORTHO';camdata.ortho_scale=2.35;cam=bpy.data.objects.new('PhysicsProbeReview',camdata);scene.collection.objects.link(cam);scene.camera=cam;scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.display.shading.light='STUDIO';scene.display.shading.color_type='OBJECT';scene.display.shading.show_cavity=True;scene.display.shading.background_type='WORLD';scene.world.color=(.85,.85,.85);scene.render.fps=30;scene.frame_start=1;scene.frame_end=len(arr)
font=bpy.data.curves.new('ProbeLabel','FONT');font.size=.043;font.body='Actual PPF cloth-body probe | 60 frames incl. preroll\nFixed clothing is visual reference; full-layer coupling not verified';label=bpy.data.objects.new('ProbeLabel',font);scene.collection.objects.link(label);label.parent=cam;label.location=(-1.10,.56,-1);label.color=(.02,.02,.03,1)
for frame in (47,60):
    scene.frame_set(frame);center=arm.matrix_world@arm.pose.bones['上半身3'].head+Vector((0,0,-.13))
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());posed=evaluated.to_mesh();co=np.empty(len(posed.vertices)*3,dtype=np.float32);posed.vertices.foreach_get('co',co);evaluated.to_mesh_clear();assert np.max(np.abs(co.reshape(-1,3)-arr[frame-1]))<1e-5,'Probe did not read the actual cache'
    for view,direction in [('front',(0,-3,.1)),('side',(3,-1,.1))]:
        cam.location=center+Vector(direction);cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(folder/f'physics_probe_{frame}_{view}.png');bpy.ops.render.render(write_still=True)
scene.frame_set(60)
for window in bpy.context.window_manager.windows:
    for area in window.screen.areas:
        if area.type=='VIEW_3D':area.spaces.active.overlay.show_overlays=False;area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='SOLID';area.spaces.active.shading.color_type='OBJECT'
scene['physics_probe_scope']='60 frames including preroll; full layered clothing not verified';bpy.ops.wm.save_as_mainfile(filepath=str(folder/'PhysicsContactProbe_2s.blend'),compress=True);mod.filepath='//PhysicsProbeClothLocal.pc2';bpy.ops.wm.save_as_mainfile(filepath=str(folder/'PhysicsContactProbe_2s.blend'),compress=True)
bpy.ops.wm.open_mainfile(filepath=str(folder/'PhysicsContactProbe_2s.blend'),load_ui=False,use_scripts=False);obj=bpy.data.objects['PPF_ActualClothProbe'];errors={}
for frame in (60,1,47):
    bpy.context.scene.frame_set(frame);ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();co=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',co);ev.to_mesh_clear();errors[str(frame)]=float(np.max(np.abs(co.reshape(-1,3)-arr[frame-1])))
assert max(errors.values())<1e-5,errors
(folder/'probe_preview_qa.json').write_text(json.dumps(dict(cache_reload_errors_m=errors,frames=60,scope='raw numerical cloth-body probe; fixed clothing visual reference'),indent=2),encoding='utf-8');print('PPF_PROBE_PREVIEW_READY',str(folder),errors,flush=True)
