"""Independent actual-surface audit and deterministic cache replay of one bundle."""
import sys,json,argparse
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame,coords
from animation_contact_tools.hair_position_cache import bind_position_cache
parser=argparse.ArgumentParser();parser.add_argument('--run');parser.add_argument('--step',type=float,default=.5);parser.add_argument('--head-local',action='store_true');options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=Path(options.run).resolve() if options.run else base/'hair_curves_20261028/single_bundle_rod_frames';report=json.loads((out/'report.json').read_text('utf8'));motion=np.load(out/'bundle_motion.npz');ids=motion['ids'];selected=set(ids.tolist());positions=motion['coordinates'];first,last=report['frames']
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=report['source'],load_ui=False,use_scripts=False)
anchor=report.get('anchor_bone','頭');profile=json.loads(Path(report.get('rig_profile',str(base/'body_track/rig_profile.json'))).read_text('utf8'));profile['pairs']=[];mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(mesh,arm,profile);faces=[];polys=[]
for name in ('hair_root','hair_mobile'):
 for face,poly in zip(parts['faces'][name],parts['source_faces'][name]):
  if all(i in selected for i in face):faces.append(face);polys.append(poly)
 for key in ('faces','ids','source_faces','samples','closed'):parts[key].pop(name,None)
parts['faces']['hair_mobile']=faces;parts['source_faces']['hair_mobile']=polys;parts['ids']['hair_mobile']=ids.tolist();parts['samples']['hair_mobile']=ids[::8].tolist();parts['closed']['hair_mobile']=False
outside=sorted(set(range(len(mesh.data.vertices)))-selected);rows=[];checks={};scene=bpy.context.scene
lookup={int(v):i for i,v in enumerate(ids)};edges=np.array([(lookup[e.vertices[0]],lookup[e.vertices[1]]) for e in mesh.data.edges if all(v in selected for v in e.vertices)]);rest=motion['rest_coordinates'];length=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1);valid=length>.0005
scene.frame_set(first);bpy.context.view_layer.update();anchor0=np.array(arm.matrix_world@arm.pose.bones[anchor].matrix);root0=motion['rest_guide'][0];root_data=np.load(out/'initial_projection.npz') if report.get('explicit_surface_root_projection') else None;root_mask=None if root_data is None else root_data['pinned']
anchor_matrices=np.asarray(motion['head_deltas'])@anchor0;inverse=np.linalg.inv(anchor_matrices);local_positions=np.einsum('fij,fvj->fvi',inverse[:,:3,:3],positions)+inverse[:,None,:3,3];local_roots=np.einsum('fij,fj->fi',inverse[:,:3,:3],motion['guides'][:,0])+inverse[:,:3,3]
for f in np.arange(first,last+.001,options.step):
 scene.frame_set(int(f),subframe=float(f%1));bpy.context.view_layer.update();source=coords(mesh);co=source.copy();index=int(f-first);t=f-int(f);co[ids]=positions[index]*(1-t)+positions[min(index+1,len(positions)-1)]*t
 if options.head_local:
  current=np.array(arm.matrix_world@arm.pose.bones[anchor].matrix);local=local_positions[index]*(1-t)+local_positions[min(index+1,len(positions)-1)]*t;co[ids]=local@current[:3,:3].T+current[:3,3]
 r=audit_frame(mesh,arm,profile,parts,hair=True,cap=1000000,coordinates_m=co);ratio=np.linalg.norm(co[ids][edges[:,0]]-co[ids][edges[:,1]],axis=1)[valid]/length[valid];delta=np.array(arm.matrix_world@arm.pose.bones[anchor].matrix)@np.linalg.inv(anchor0);expected_root=delta[:3,:3]@root0+delta[:3,3];root=motion['guides'][index,0]*(1-t)+motion['guides'][min(index+1,len(positions)-1),0]*t
 if options.head_local:root=current[:3,:3]@(local_roots[index]*(1-t)+local_roots[min(index+1,len(positions)-1)]*t)+current[:3,3]
 visible_root_error=None if root_mask is None else float(np.max(np.linalg.norm(co[ids][root_mask]-(root_data['coordinates'][root_mask]@delta[:3,:3].T+delta[:3,3]),axis=1)))
 rows.append({'visible_root_pin_error_m':visible_root_error,'frame':float(f),'crossings':r['ordinary_crossings'],'min_mesh_edge_ratio':float(ratio.min()),'max_mesh_edge_ratio':float(ratio.max()),'interpolated_guide_root_error_m':float(np.linalg.norm(root-expected_root)),'pairs':[{'pair':x['pair'],'crossings':x['triangle_crossings']} for x in r['pairs'] if x['triangle_crossings']]})
 if f in (first,last,217,217.5,218,220,236,240):
  checks[float(f)]=co.copy()
  if float(f).is_integer():np.savez_compressed(out/f'keypose{int(f):04}.npz',coordinates=co)
kwargs={'anchor_armature':arm,'anchor_bone':anchor,'anchor_matrices':anchor_matrices} if options.head_local else {};metadata=bind_position_cache(mesh,ids,positions,out/'SingleBundle_MeasuredMotion.pc2',first=first,**kwargs);cacheerror=0.;skinerror=0.
for f,expected in checks.items():
 scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();actual=coords(mesh);cacheerror=max(cacheerror,float(np.max(np.abs(actual-expected))));skinerror=max(skinerror,float(np.max(np.abs(actual[outside]-expected[outside]))))
assert cacheerror<2e-6,(cacheerror,skinerror);assert skinerror<1e-8,skinerror
source_outside={}
modifier=mesh.modifiers[-1]
for f in (first-1,first-.5,last+.5,last+1):
 scene.frame_set(int(f),subframe=f%1);modifier.show_viewport=False;bpy.context.view_layer.update();source_outside[f]=coords(mesh);modifier.show_viewport=True;bpy.context.view_layer.update();assert np.max(np.abs(coords(mesh)-source_outside[f]))<1e-8
scene.frame_start=first;scene.frame_end=last;scene.frame_set(240);target=out/'SingleBundle_CachedCandidate_NotAccepted.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target),compress=True)
bpy.ops.wm.open_mainfile(filepath=str(target),load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']]
for f,expected in checks.items():
 bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();cacheerror=max(cacheerror,float(np.max(np.abs(coords(mesh)-expected))))
assert cacheerror<2e-6,cacheerror
shape_fail=any(r['min_mesh_edge_ratio']<.9 or r['max_mesh_edge_ratio']>1.1 for r in rows);root_error=max(r['interpolated_guide_root_error_m'] for r in rows);failures=sum(r['crossings']>0 for r in rows);visible_root_peak=max((r['visible_root_pin_error_m'] for r in rows if r['visible_root_pin_error_m'] is not None),default=None);local_pass=failures==0 and not shape_fail and (visible_root_peak<2e-6 if visible_root_peak is not None else root_error<.0005)
result={'status':'SELECTED_BUNDLE_SAMPLED_SURFACE_AND_STRAIN_PASS' if local_pass else 'SINGLE_BUNDLE_UNRESOLVED','accepted':False,'selected_bundle_samples_pass':local_pass,'candidate':str(target),'frames':[first,last],'samples':rows,'sample_count':len(rows),'sample_step':options.step,'failed_samples':failures,'crossing_peak':max(r['crossings'] for r in rows),'min_mesh_edge_ratio':min(r['min_mesh_edge_ratio'] for r in rows),'max_mesh_edge_ratio':max(r['max_mesh_edge_ratio'] for r in rows),'interpolated_root_error_peak_m':root_error,'visible_root_pin_peak_error_m':visible_root_peak,'root_acceptance_metric':'actual surface pins' if visible_root_peak is not None else 'native guide root','cache':metadata,'cache_reload_max_error_m':cacheerror,'all_unselected_vertices_max_error_m':skinerror,'outside_range_source_preserved':True,'surface_containment':'open source regions not fully checked','ccd_proven':False,'shape_failures_in_solver_report':shape_fail,'whole_hair_solved':False}
(out/'independent_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('NATIVE_BUNDLE_INDEPENDENT',json.dumps({k:v for k,v in result.items() if k not in ('samples','cache')}),flush=True)
