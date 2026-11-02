"""Independent saved-file checks and clothed 1080p keypose comparisons."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,add_glove_hands,contacts,compact,evaluated_coords,HAND_PREFIX
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--capture',required=True);p.add_argument('--no-render',action='store_true');p.add_argument('--step',type=float);p.add_argument('--render-frames',nargs='+',type=int);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=Path(a.input).resolve();out=folder/'review';out.mkdir(exist_ok=True)
engine('import_export').ensure_mmd_tools()
def geometry(obj):
    h=hashlib.sha256();co=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',co);h.update(co.tobytes())
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:key.data.foreach_get('co',co);h.update(co.tobytes())
    return h.hexdigest()
def action_digest(action):
    h=hashlib.sha256()
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:h.update(str((fc.data_path,fc.array_index,[(tuple(k.co),tuple(k.handle_left),tuple(k.handle_right),k.interpolation) for k in fc.keyframe_points])).encode())
    return h.hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/cynical_cloth15/sleeve_stable/Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);base={o.name:geometry(o) for o in engine('import_export').model_meshes()};digest=action_digest(bpy.data.objects['达妮娅_arm'].animation_data.action)
bpy.ops.wm.open_mainfile(filepath=str(folder/'MMD_Contact_Keyposes.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];cloth=bpy.data.objects['Cloth'];corrected=arm.animation_data.action;original=bpy.data.actions['シニカルナイトプラン_bone'];assert base=={name:geometry(bpy.data.objects[name]) for name in base};assert digest==action_digest(original)
with np.load(Path(a.capture)/'source_hands.npz') as z:source_ids=z['source_vertex_ids'].copy()
regions=skin_regions(body,arm);add_glove_hands(regions,body,arm,cloth);glove=regions['extra_objects'][0];report={'scope':'Saved keypose or short-window samples; no CCD, gesture or cloth acceptance','protected_meshes_and_morphs':len(base),'original_action_preserved':True,'frames':{}};frames=list(map(int,json.loads((folder/'keypose_report.json').read_text())['frames']));render_frames=a.render_frames or frames
if a.step is not None:
    if a.step<=0:raise ValueError('Positive sample spacing required')
    frames=list(np.arange(min(frames),max(frames)+a.step*.1,a.step))
primary=[n for n in ('頭','上半身3','下半身','足首D.L','足首D.R','足ＩＫ.L','足ＩＫ.R') if n in arm.pose.bones];protected=[b.name for b in arm.pose.bones if b.name.startswith(HAND_PREFIX[1:])]+primary;baselines={};primary_baselines={};source_q={};corrections=[];controls=[p+'.'+s for s in ('L','R') for p in ('腕','ひじ','手首')]
for label,action in (('before',original),('after',corrected)):
    arm.animation_data.action=action
    for f in frames:
        scene.frame_set(int(f),subframe=float(f%1));bpy.context.view_layer.update();matrices=np.array([arm.pose.bones[n].matrix_basis for n in protected]);primary_matrices=np.array([arm.matrix_world@arm.pose.bones[n].matrix for n in primary]);row=compact(contacts(body,arm,regions,.002,True,sample_contacts=False));row['audit_vs_visible_hand_max_error_m']=float(np.linalg.norm(evaluated_coords(glove)-evaluated_coords(cloth)[source_ids],axis=1).max())
        if label=='before':baselines[f]=matrices;primary_baselines[f]=primary_matrices;source_q[f]=[arm.pose.bones[n].rotation_quaternion.copy() for n in controls]
        else:
            row['protected_local_matrix_error']=float(np.abs(matrices-baselines[f]).max());row['primary_world_matrix_error']=float(np.abs(primary_matrices-primary_baselines[f]).max());corrections.append(np.array([list(q.inverted()@arm.pose.bones[n].rotation_quaternion) for q,n in zip(source_q[f],controls)]))
        report['frames'].setdefault(f'{f:g}',{})[label]=row
        print('SAVED_MMD_CONTACT_QA',f,label,row['triangle_crossings'],row['audit_vs_visible_hand_max_error_m'],flush=True)
report['status']='SAVED_STATIC_CONTACT_GEOMETRY_PASS_GESTURE_UNREVIEWED' if all(v['after']['triangle_crossings']==0 and v['after']['audit_vs_visible_hand_max_error_m']<1e-5 and v['after']['protected_local_matrix_error']<1e-6 and v['after']['primary_world_matrix_error']<1e-6 for v in report['frames'].values()) else 'SAVED_STATIC_KEYPOSE_NOT_ACCEPTED'
if a.step is not None:
    correction=np.array(corrections);correction/=np.linalg.norm(correction,axis=-1,keepdims=True);velocity=2*np.arccos(np.clip(np.abs(np.sum(correction[1:]*correction[:-1],axis=-1)),0,1))*180/np.pi/a.step;report['max_correction_rotation_change_deg_per_frame']=float(velocity.max());report['sample_step_frames']=a.step;report['samples']=len(frames);report['status']='SAVED_SAMPLED_CONTACT_WINDOW_PASS_GESTURE_CLOTH_UNACCEPTED' if report['status'].startswith('SAVED_STATIC_CONTACT_GEOMETRY_PASS') and velocity.max()<6. else 'SAMPLED_CONTACT_WINDOW_NOT_ACCEPTED'
(folder/'reload_qa.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if a.no_render:raise SystemExit(0)
for obj in regions['extra_objects']:obj.hide_render=True
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.display.shading.light='STUDIO';scene.display.shading.color_type='TEXTURE';scene.display.shading.show_cavity=True;scene.display.shading.background_type='WORLD';scene.world.color=(.55,.55,.55)
camdata=bpy.data.cameras.new('GroupedContactReview');camdata.type='ORTHO';camdata.ortho_scale=.83;cam=bpy.data.objects.new('GroupedContactReview',camdata);scene.collection.objects.link(cam);scene.camera=cam
for f in render_frames:
    arm.animation_data.action=original;scene.frame_set(f);bpy.context.view_layer.update();center=(arm.matrix_world@arm.pose.bones['上半身3'].head)+Vector((0,0,.09));upper=arm.pose.bones['上半身3'];axes=(arm.matrix_world@upper.matrix@upper.bone.matrix_local.inverted()).to_3x3()
    for label,action in (('before',original),('after',corrected)):
        arm.animation_data.action=action;scene.frame_set(f);bpy.context.view_layer.update()
        for view,local in [('front',(0,-2,.15)),('side',(2,-.3,.15)),('back',(0,2,.15))]:
            cam.location=center+axes@Vector(local);cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'{f}_{label}_{view}.png');bpy.ops.render.render(write_still=True)
print('SAVED_MMD_KEYPOSE_REVIEW',report['status'],flush=True)
