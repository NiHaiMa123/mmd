import sys,json,hashlib
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords,audit_frame
from animation_contact_tools.track import fcurves
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=base/'hair_arm_feedback_20261028/baked_polished';p=json.loads((base/'body_track/rig_profile.json').read_text('utf8'));samples=sorted(set(np.arange(212,228.001,.125).tolist())|{1.,200.,211.875,228.125,250.,256.,285.,321.,450.});refs={}
def actions_hash():
 result={}
 for a in bpy.data.actions:
  data=[(c.data_path,c.array_index,[(list(k.co),list(k.handle_left),list(k.handle_right),k.interpolation) for k in c.keyframe_points]) for c in fcurves(a)];result[a.name]=hashlib.sha256(json.dumps(data).encode()).hexdigest()
 return result
bpy.ops.wm.open_mainfile(filepath=str(base/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);original=actions_hash();mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);affected={b.name for b in arm.data.bones if b.name=='右腕' or '右腕' in {x.name for x in b.parent_recursive}};groups={g.index for g in mesh.vertex_groups if g.name in affected};ids=[v.index for v in mesh.data.vertices if not any(g.group in groups and g.weight>1e-7 for g in v.groups)];primary=['頭','上半身3','下半身','左足ＩＫ','右足ＩＫ'];profile=dict(p,pairs=[])
for a,b in p['pairs']:
 if a in ('arm.R','hand.R'):profile['pairs'].append([a,b])
 elif b in ('arm.R','hand.R'):profile['pairs'].append([b,a])
for f in samples:
 bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();refs[f]={'co':coords(mesh),'primary':{n:np.array(arm.pose.bones[n].matrix) for n in primary}}
bpy.ops.wm.open_mainfile(filepath=str(out/'Body_With_ArmDetour.blend'),load_ui=False,use_scripts=False);current=actions_hash();assert all(current.get(n)==h for n,h in original.items());mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];rows=[];outside_error=0.;primary_error=0.;unaffected_error=0.;protected_error=0.
for f in samples:
 bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();co=coords(mesh);r=refs[f];audit=audit_frame(mesh,arm,profile,parts,hair=False,cap=5000);rows.append({'frame':f,'right_arm_body_crossings':audit['ordinary_crossings']});primary_error=max(primary_error,max(float(np.max(np.abs(np.array(arm.pose.bones[n].matrix)-m))) for n,m in r['primary'].items()));unaffected_error=max(unaffected_error,float(np.max(np.abs(co[ids]-r['co'][ids]))))
 if f<212 or f>228:outside_error=max(outside_error,float(np.max(np.abs(co-r['co']))))
 if 256<=f<=321:protected_error=max(protected_error,float(np.max(np.abs(co-r['co']))))
result={'status':'RIGHT_ARM_SUBFRAME_AND_SOURCE_INTEGRITY_CHECK','sample_step_frames':.125,'samples':rows,'failed_samples':sum(r['right_arm_body_crossings']>0 for r in rows if 212<=r['frame']<=228),'primary_matrix_error':primary_error,'unaffected_skin_error_m':unaffected_error,'outside_phase_mesh_error_m':outside_error,'clasp_window_checked_mesh_error_m':protected_error,'source_actions_hash_match':True,'original_action_count':len(original),'ccd_proven':False}
(out/'independent_body_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('ARM_DETOUR_SOURCE_VERIFIED',json.dumps({k:v for k,v in result.items() if k!='samples'}),flush=True)
