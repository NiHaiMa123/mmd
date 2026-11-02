import sys,json,hashlib,math,argparse
from pathlib import Path
import bpy,numpy as np
from mathutils import Quaternion,Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame,coords,DEFAULT_PAIRS
from animation_contact_tools.track import fcurves
parser=argparse.ArgumentParser();parser.add_argument('--candidate',default='BodyContact_UpperBodyCandidate.blend');parser.add_argument('--report',default='upper_body_independent_validation.json');options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'body_track'
bpy.ops.wm.open_mainfile(filepath=str(out/options.candidate),load_ui=False,use_scripts=False)
p=json.loads((out/'rig_profile.json').read_text('utf8'));p['pairs']=DEFAULT_PAIRS;p['protected_pairs']=[];arm=bpy.data.objects[p['armature']];mesh=bpy.data.objects[p['mesh']];parts=regions(mesh,arm,p)
r=json.loads((out/'body_track_report.json').read_text('utf8'));original=bpy.data.actions[r['original_action']];delta=bpy.data.actions[r['correction_action']];ad=arm.animation_data
def digest(action):
 rows=[(c.data_path,c.array_index,[(tuple(k.co),tuple(k.handle_left),tuple(k.handle_right),k.interpolation) for k in c.keyframe_points]) for c in fcurves(action)]
 return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
original_digest=digest(original);curve_lookup={(c.data_path,c.array_index):c for c in fcurves(delta)}
lookup=[];maximum=0.;velocity=0.;prev={};primary_error=0.;gesture_error=0.;hair_error=0.;remaining=[]
primary=p.get('protected_bones',['頭','上半身3','下半身','左足ＩＫ','右足ＩＫ']);primary=[n for n in primary if n in arm.pose.bones]
for frame in np.arange(1,450.001,.25):
 f=float(frame);ad.action=None;ad.use_nla=True;bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update()
 a=audit_frame(mesh,arm,p,parts,hair=False,cap=2000)
 if a['ordinary_crossings'] or a['ordinary_contained_samples']:remaining.append({'frame':f,'pairs':[{'pair':r['pair'],'crossings':r['triangle_crossings'],'contained':r['contained_samples']} for r in a['pairs'] if r['classification']=='ordinary_collision' and (r['triangle_crossings'] or r['contained_samples'])]})
 if frame%1==0:
  for name in [n for chain in p['control_chains'] for n in chain[:2]]:
   path=arm.pose.bones[name].path_from_id('rotation_quaternion');q=Quaternion([curve_lookup[path,i].evaluate(f) for i in range(4)]);q.normalize();angle=q.angle
   maximum=max(maximum,min(angle,2*math.pi-angle)*180/math.pi)
   if name in prev:velocity=max(velocity,prev[name].rotation_difference(q).angle*180/math.pi)
   prev[name]=q
 if 256<=f<=321 or frame%15==1:
  corrected=coords(mesh);mat={n:np.array(arm.pose.bones[n].matrix) for n in primary}
  ad.use_nla=False;ad.action=original;bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();base=coords(mesh)
  primary_error=max(primary_error,max(float(np.max(np.abs(np.array(arm.pose.bones[n].matrix)-m))) for n,m in mat.items()))
  hairids=parts['ids']['hair_root']+parts['ids']['hair_mobile'];hair_error=max(hair_error,float(np.max(np.abs(corrected[hairids]-base[hairids]))))
  if 256<=f<=321:gesture_error=max(gesture_error,float(np.max(np.abs(corrected-base))))
 if int(frame)%100==0 and frame%1==0:print('VERIFY_BODY',f,len(remaining),flush=True)
ad.action=None;ad.use_nla=True
result={'status':'EXPANDED_PAIR_DISCRETE_BODY_PASS' if not remaining else 'BODY_UNRESOLVED','sample_step_frames':.25,'sample_count':1797,'pair_count':len(DEFAULT_PAIRS),'pairs':DEFAULT_PAIRS,'remaining':remaining,'primary_bone_matrix_error':primary_error,'gesture_mesh_max_error_m':gesture_error,'hair_mesh_max_error_m':hair_error,'max_arm_control_delta_degrees':maximum,'max_arm_delta_step_degrees_per_frame':velocity,'original_action_sha256':original_digest,'closed_regions':parts['closed'],'unmapped_body_triangles':parts['missing_body_mapping'],'excluded':parts['excluded_surface_triangles'],'ccd_guarantee':False,'open_region_containment_proven':False}
(out/options.report).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('INDEPENDENT_RESULT',json.dumps({k:v for k,v in result.items() if k not in ['remaining','pairs','excluded']},ensure_ascii=False),'REMAINING',len(remaining),flush=True)
p['pairs']=DEFAULT_PAIRS;(out/'rig_profile.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
# Render the true evaluated geometry from matched angles, hide stage only in
# this diagnostic copy. Original production scene and camera stay untouched.
review=root/'review_upper_body';review.mkdir(exist_ok=True);scene=bpy.context.scene
for o in scene.objects:o.hide_render=o!=mesh
mesh.hide_render=False;mesh.color=(.53,.64,.78,1)
data=bpy.data.cameras.new('SurfaceReview');data.type='ORTHO';cam=bpy.data.objects.new('SurfaceReview',data);scene.collection.objects.link(cam);scene.camera=cam
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1080;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False;scene.world.color=(.19,.19,.19)
shade=scene.display.shading;shade.light='STUDIO';shade.color_type='OBJECT';shade.show_cavity=True;shade.show_shadows=True;shade.show_specular_highlight=True;shade.background_type='WORLD'
for frame in (1,240,361):
 for label in ('before','after'):
  ad.use_nla=label=='after';ad.action=None if label=='after' else original;scene.frame_set(frame);bpy.context.view_layer.update()
  for view,offset in [('front',Vector((0,-3,0))),('side',Vector((3,0,0))),('rear',Vector((0,3,0)))]:
   target=arm.matrix_world@arm.pose.bones['上半身3'].head+Vector((0,0,.035));data.ortho_scale=.9
   cam.location=target+offset;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(review/f'f{frame:04}_{view}_{label}.png');bpy.ops.render.render(write_still=True)
print('REVIEW_RENDERED',str(review),flush=True)
