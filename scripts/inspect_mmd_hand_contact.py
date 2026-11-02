"""Read-only original MMD hand geometry and semantic anchors, never a repair."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,add_glove_hands,evaluated_coords,contacts,compact,HAND_PREFIX
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--frames',nargs='+',type=int,default=[280,300,310,325,340]);p.add_argument('--skip-render',action='store_true');p.add_argument('--hand-only',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
engine('import_export').ensure_mmd_tools();source=ROOT/'outputs/cynical_cloth15/sleeve_stable/Cynical_Cloth_15s.blend';bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
scene=bpy.context.scene;arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];regions=skin_regions(body,arm);report={'status':'READ_ONLY_INPUT_CAPTURE','source':str(source),'original_action':arm.animation_data.action.name,'frames':{},'hands':add_glove_hands(regions,body,arm,bpy.data.objects['Cloth'])};glove=regions['extra_objects'][0]
names={g.index:g.name for g in glove.vertex_groups if g.name in arm.pose.bones};dom=[max(((g.weight,names[g.group]) for g in v.groups if g.group in names),default=(0.,''))[1] for v in glove.data.vertices];glove.data.calc_loop_triangles();faces=np.array([f.vertices[:] for f in glove.data.loop_triangles]);ids={s:np.array([i for i,n in enumerate(dom) if n.endswith('.'+s)],dtype=int) for s in ('L','R')};side_faces={s:np.array([f for f in faces if all(dom[i].endswith('.'+s) for i in f)],dtype=int) for s in ('L','R')}
source_cloth=bpy.data.objects['Cloth'];source_names={g.index:g.name for g in source_cloth.vertex_groups if not g.name.startswith('mmd_') and g.name in arm.pose.bones};source_dom=[max(((g.weight,source_names[g.group]) for g in v.groups if g.group in source_names),default=(0.,''))[1] for v in source_cloth.data.vertices];chosen={i for i,n in enumerate(source_dom) if n.startswith(HAND_PREFIX)};source_cloth.data.calc_loop_triangles();source_ids=np.array(sorted({i for f in source_cloth.data.loop_triangles if all(i in chosen for i in f.vertices) for i in f.vertices}));report['source_cloth_modifiers']=[{'name':m.name,'type':m.type,'viewport':m.show_viewport} for m in source_cloth.modifiers]
data={'faces':faces,'ids_L':ids['L'],'ids_R':ids['R'],'faces_L':side_faces['L'],'faces_R':side_faces['R'],'rest_vertices':np.array([v.co[:] for v in glove.data.vertices]),'source_vertex_ids':source_ids};pose=[];coords=[];wrist=[];visible=[]
for f in a.frames:
    scene.frame_set(f);bpy.context.view_layer.update();co=evaluated_coords(glove);coords.append(co);actual=evaluated_coords(source_cloth)[source_ids];visible.append(actual);wm=np.array([arm.matrix_world@arm.pose.bones['手首.'+s].matrix for s in ('L','R')]);wrist.append(wm);row={'body_audit_skipped':True} if a.hand_only else compact(contacts(body,arm,regions,.002,True,sample_contacts=False));row['wrist_distance_m']=float(np.linalg.norm(wm[0,:3,3]-wm[1,:3,3]));row['hands_bounds_m']={s:np.ptp(co[ids[s]],axis=0).tolist() for s in ids};row['audit_vs_visible_hand_max_error_m']=float(np.linalg.norm(co-actual,axis=1).max());report['frames'][str(f)]=row;pose.append(np.array([arm.pose.bones[n].matrix for n in ('腕.L','ひじ.L','手首.L','腕.R','ひじ.R','手首.R')]));print('MMD_CONTACT_INPUT',f,json.dumps(row),flush=True)
data.update(frames=np.array(a.frames),hand_vertices=np.array(coords),visible_hand_vertices=np.array(visible),wrist_matrices=np.array(wrist),bone_matrices=np.array(pose));np.savez_compressed(out/'source_hands.npz',**data)
if a.skip_render:
    (out/'input_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('MMD_CONTACT_INPUT_CAPTURED',str(out),flush=True);raise SystemExit(0)
# Clothed close-ups of the actual source pose, not the rejected correction.
for obj in regions['extra_objects']:obj.hide_render=True
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True;scene.display.shading.background_type='WORLD';scene.world.color=(.55,.55,.55)
camdata=bpy.data.cameras.new('OriginalHandContact');camdata.type='ORTHO';camdata.ortho_scale=.52;cam=bpy.data.objects.new('OriginalHandContact',camdata);scene.collection.objects.link(cam);scene.camera=cam
for f in a.frames:
    scene.frame_set(f);bpy.context.view_layer.update();center=sum((arm.matrix_world@arm.pose.bones['手首.'+s].head for s in ('L','R')),Vector())*.5
    axes=(arm.matrix_world@arm.pose.bones['上半身3'].matrix@arm.pose.bones['上半身3'].bone.matrix_local.inverted()).to_3x3()
    for view,local in [('front',(0,-2,.15)),('side',(2,-.3,.15)),('back',(0,2,.15))]:
        cam.location=center+axes@Vector(local);cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'{f}_{view}.png');bpy.ops.render.render(write_still=True)
(out/'input_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('MMD_CONTACT_INPUT_CAPTURED',str(out),flush=True)
