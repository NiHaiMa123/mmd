"""Independent body replay and conservative clump audit after saving a detour."""
import argparse,hashlib,json,sys,time
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,regions,audit_frame
from animation_contact_tools.hair_bundle_profile import resolve_bundle
from animation_contact_tools.track import fcurves
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--step',type=float,default=.125);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.run);r=json.loads((out/'report.json').read_text('utf8'))
if 'candidate' not in r:raise ValueError('A saved candidate is required')
profile=r['rig_profile'];config=r['bundle'];first,last=r['frames'];frames=np.arange(first,last+.001,a.step);extra=[first-.125,last+.125,256.,285.,321.];engine('import_export').ensure_mmd_tools()
def action_hashes():
 result={}
 for act in bpy.data.actions:
  values=[(c.data_path,c.array_index,[(tuple(k.co),tuple(k.handle_left),tuple(k.handle_right),k.interpolation) for k in c.keyframe_points]) for c in fcurves(act)]
  result[act.name]=hashlib.sha256(json.dumps(values).encode()).hexdigest()
 return result
def geometry_hash(mesh):
 h=hashlib.sha256();buffer=np.empty(len(mesh.data.vertices)*3,dtype=np.float32);mesh.data.vertices.foreach_get('co',buffer);h.update(buffer.tobytes());loop=np.empty(len(mesh.data.loops),dtype=np.int32);mesh.data.loops.foreach_get('vertex_index',loop);h.update(loop.tobytes())
 for key in mesh.data.shape_keys.key_blocks:key.data.foreach_get('co',buffer);h.update(key.name.encode());h.update(buffer.tobytes())
 for v in mesh.data.vertices:
  for group in v.groups:h.update(f'{v.index}:{mesh.vertex_groups[group.group].name}:{group.weight:.9g};'.encode())
 return h.hexdigest()
bpy.ops.wm.open_mainfile(filepath=r['source'],load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];source_actions=action_hashes();source_geometry=geometry_hash(mesh);root=profile['control_chains'][0][0];descendants={b.name for b in arm.data.bones if b.name==root or root in {p.name for p in b.parent_recursive}};affected_groups={g.index for g in mesh.vertex_groups if g.name in descendants};outside=np.array([v.index for v in mesh.data.vertices if not any(g.group in affected_groups and g.weight>1e-7 for g in v.groups)]);source={};source_wrist={};primary_names=list(dict.fromkeys([config['anchor_bone']]+[name for name in profile.get('protected_bones',[]) if name in arm.pose.bones]));primaries={}
for frame in list(frames)+extra:
 bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();co=coords(mesh);source[float(frame)]=co if frame in extra else co[outside];source_wrist[float(frame)]=np.array(arm.matrix_world@arm.pose.bones[profile['control_chains'][0][2]].head);primaries[float(frame)]={n:np.array(arm.pose.bones[n].matrix) for n in primary_names}
bpy.ops.wm.open_mainfile(filepath=r['candidate'],load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];current_actions=action_hashes();assert all(current_actions.get(n)==v for n,v in source_actions.items());assert geometry_hash(mesh)==source_geometry
initial=np.load(ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029/multi_bundle/left_rig_root_native/initial_projection.npz');bundle=resolve_bundle(mesh,arm,regions(mesh,arm,profile),config);bpy.context.scene.frame_set(1);bpy.context.view_layer.update();head0=np.array(arm.matrix_world@arm.pose.bones[config['anchor_bone']].matrix);rows=[];start=time.monotonic();outside_error=0.;primary_error=0.;offsets=[]
for k,frame in enumerate(frames):
 bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();co=coords(mesh);outside_error=max(outside_error,float(np.max(np.abs(co[outside]-source[float(frame)]))));primary_error=max(primary_error,max(float(np.max(np.abs(np.array(arm.pose.bones[n].matrix)-m))) for n,m in primaries[float(frame)].items()));body=audit_frame(mesh,arm,profile,bundle['parts'],hair=False,cap=1000000,coordinates_m=co);head=np.array(arm.matrix_world@arm.pose.bones[config['anchor_bone']].matrix);delta=head@np.linalg.inv(head0);co[bundle['ids']]=initial['coordinates']@delta[:3,:3].T+delta[:3,3];hair=audit_frame(mesh,arm,dict(profile,pairs=[]),bundle['parts'],hair=True,cap=1000000,coordinates_m=co);offset=np.array(arm.matrix_world@arm.pose.bones[profile['control_chains'][0][2]].head)-source_wrist[float(frame)];offsets.append(offset);rows.append(dict(frame=float(frame),body_crossings=body['ordinary_crossings'],body_contained_samples=body['ordinary_contained_samples'],hair_crossings=hair['ordinary_crossings']))
 if k%32==0:print('CLUMP_REOPEN',frame,sum(bool(v['body_crossings'] or v['body_contained_samples'] or v['hair_crossings']) for v in rows),flush=True)
protected_error=0.
for frame in extra:
 bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();protected_error=max(protected_error,float(np.max(np.abs(coords(mesh)-source[float(frame)]))))
source_path=np.array([source_wrist[float(f)] for f in frames]);repaired_path=source_path+np.asarray(offsets)
failures=sum(bool(v['body_crossings'] or v['body_contained_samples'] or v['hair_crossings']) for v in rows);result=dict(status='CLUMP_DETOUR_SAMPLED_REOPEN_PASS' if not failures and max(outside_error,primary_error,protected_error)<2e-6 else 'CLUMP_DETOUR_UNRESOLVED',accepted=False,sample_count=len(rows),frames=[first,last],step_frames=a.step,failed_samples=failures,samples=rows,source_action_hashes_match=True,source_rest_topology_weights_and_shape_keys_match=True,source_action_count=len(source_actions),unaffected_vertices_peak_error_m=outside_error,primary_bone_peak_error=primary_error,protected_and_outside_window_peak_error_m=protected_error,max_wrist_offset_m=float(np.linalg.norm(offsets,axis=1).max()),peak_source_wrist_speed_m_per_frame=float(np.linalg.norm(np.diff(source_path,axis=0),axis=1).max()/a.step),peak_repaired_wrist_speed_m_per_frame=float(np.linalg.norm(np.diff(repaired_path,axis=0),axis=1).max()/a.step),peak_correction_speed_m_per_frame=float(np.linalg.norm(np.diff(offsets,axis=0),axis=1).max()/a.step),seconds=time.monotonic()-start,hair_resimulation_required=True,ccd_proven=False,all_hair_solved=False);(out/'independent_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('CLUMP_REOPEN_COMPLETE',json.dumps({k:v for k,v in result.items() if k!='samples'}),flush=True)
