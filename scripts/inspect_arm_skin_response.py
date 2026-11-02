import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords
from animation_contact_tools.root_envelope_feedback import capsule_features
from animation_contact_tools.two_bone_contact_path import apply_two_bone_goal
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';p=json.loads((base/'body_track/rig_profile.json').read_text('utf8'));env=json.loads((base/'hair_arm_feedback_20261028/root_contact_diagnosis.json').read_text('utf8'));bpy.ops.wm.open_mainfile(filepath=str(base/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);arm=bpy.data.objects[p['armature']];mesh=bpy.data.objects[p['mesh']];parts=regions(mesh,arm,p);bpy.context.scene.frame_set(219);bpy.context.view_layer.update();co=coords(mesh);chain=p['control_chains'][1];wrist=arm.pose.bones[chain[2]];before=np.array(arm.matrix_world@wrist.head);result=apply_two_bone_goal(arm,chain,before+np.array([0,0,.10]));after=coords(mesh);matrix=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix);d=matrix@np.linalg.inv(env['anchor_bind_matrix']);guide=np.asarray(env['guide'])[:4]@d[:3,:3].T+d[:3,3];r=np.asarray(env['radii'])[:4];rows=[]
for role in ('arm.R','hand.R'):
 ids=np.array(parts['ids'][role]);gaps,_=capsule_features(after[ids],guide,r);i=int(ids[np.argmin(gaps)]);weights=[(mesh.vertex_groups[g.group].name,g.weight) for g in mesh.data.vertices[i].groups];bones=[]
 for name,weight in weights:
  b=arm.pose.bones.get(name)
  if b:bones.append({'name':name,'parent':b.parent.name if b.parent else None,'constraints':[(c.name,c.type,c.influence) for c in b.constraints],'head':list(arm.matrix_world@b.head),'deform':b.bone.use_deform})
 rows.append({'role':role,'max_mesh_displacement_m':float(np.linalg.norm(after[ids]-co[ids],axis=1).max()),'worst_vertex':i,'before':co[i].tolist(),'after':after[i].tolist(),'weights':weights,'bone_info':bones,'min_gap_m':float(gaps.min())})
report={'wrist_before':before.tolist(),'wrist_after':list(arm.matrix_world@wrist.head),'ik':result,'rows':rows,'modifiers':[(m.name,m.type,getattr(m,'object',None).name if getattr(m,'object',None) else None) for m in mesh.modifiers]};(base/'hair_arm_feedback_20261028/skin_response.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('ARM_SKIN_RESPONSE',json.dumps(report,ensure_ascii=False),flush=True)
