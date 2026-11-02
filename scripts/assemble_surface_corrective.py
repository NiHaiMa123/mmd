"""Compose checked surface windows into a dense, head-local full-range cache."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.hair_position_cache import bind_position_cache
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--patch',action='append',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);basepath=Path(a.base);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
if (out/'assembly_report.json').exists():raise ValueError('Choose a new assembly directory')
base=json.loads((basepath/'report.json').read_text('utf8'));motion=np.load(basepath/'bundle_motion.npz');ids=motion['ids'];engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=base['source'],load_ui=False,use_scripts=False);rig_profile_path=Path(base.get('rig_profile',str(ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028/body_track/rig_profile.json')));profile=json.loads(rig_profile_path.read_text('utf8'));anchor_bone=base.get('anchor_bone','頭');mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];scene=bpy.context.scene;first,last=base['frames'];scene.frame_set(first);bpy.context.view_layer.update();anchor0=np.array(arm.matrix_world@arm.pose.bones[anchor_bone].matrix);original_matrices=np.asarray(motion['head_deltas'])@anchor0;inverse=np.linalg.inv(original_matrices);original_local=np.einsum('fij,fvj->fvi',inverse[:,:3,:3],motion['coordinates'])+inverse[:,None,:3,3];frames=np.arange(first,last+.001,.25);baseline=[];matrices=[]
for frame in frames:
 scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();head=np.array(arm.matrix_world@arm.pose.bones[anchor_bone].matrix);index=int(frame-first);u=frame-int(frame);local=original_local[index]*(1-u)+original_local[min(index+1,len(original_local)-1)]*u;baseline.append(local@head[:3,:3].T+head[:3,3]);matrices.append(head)
baseline=np.asarray(baseline);matrices=np.asarray(matrices);positions=baseline.copy();occupied=set();patches=[];rootmask=None
for folder in map(Path,a.patch):
 report=json.loads((folder/'report.json').read_text('utf8'));patch=np.load(folder/'surface_motion.npz');assert report['step_frames']==.25 and report['source']==base['source'];assert report['failed_collision_samples']==0,'Patch still has triangle collisions';np.testing.assert_array_equal(ids,patch['ids'])
 indices=np.rint((np.arange(report['frames'][0],report['frames'][1]+.001,.25)-first)/.25).astype(int)
 if occupied.intersection(indices.tolist()):raise ValueError('Patch intervals overlap')
 occupied.update(indices.tolist());error=float(np.max(np.abs(patch['target']-baseline[indices])));assert error<2e-6,error;positions[indices]=patch['coordinates'];rootmask=patch['pinned'] if rootmask is None else rootmask;np.testing.assert_array_equal(rootmask,patch['pinned']);patches.append({'directory':str(folder),'frames':report['frames'],'max_correction_m':report['max_correction_m'],'target_error_m':error})
outside=sorted(set(range(len(mesh.data.vertices)))-set(ids.tolist()));checks={};keyframes=[1,200,247.5,256,285,321,342,350,355,373,376,450]
for frame in keyframes:scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();checks[frame]=coords(mesh)[outside]
metadata=bind_position_cache(mesh,ids,positions,out/'SurfaceCorrective_Motion.pc2',first=first,anchor_armature=arm,anchor_bone=anchor_bone,anchor_matrices=matrices,sample_step=.25);reload_error=0.;body_error=0.
for frame in keyframes:
 scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();actual=coords(mesh);index=int(round((frame-first)*4));reload_error=max(reload_error,float(np.max(np.abs(actual[ids]-positions[index]))));body_error=max(body_error,float(np.max(np.abs(actual[outside]-checks[frame]))))
assert reload_error<2e-6 and body_error==0,(reload_error,body_error)
scene.frame_start=first;scene.frame_end=last;scene.frame_set(350);candidate=out/'SelectedBundle_SurfaceCorrective_NotFullyAccepted.blend';bpy.ops.wm.save_as_mainfile(filepath=str(candidate),compress=True);bpy.ops.wm.open_mainfile(filepath=str(candidate),load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']]
for frame in keyframes:bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();reload_error=max(reload_error,float(np.max(np.abs(coords(mesh)[ids]-positions[int(round((frame-first)*4))]))))
assert reload_error<2e-6,reload_error
np.savez_compressed(out/'dense_motion.npz',coordinates=positions.astype(np.float32),baseline=baseline.astype(np.float32),ids=ids,anchor_matrices=matrices,pinned=rootmask,rest_coordinates=motion['rest_coordinates'])
result={'status':'DENSE_SURFACE_CORRECTIVE_REQUIRES_INDEPENDENT_VALIDATION','accepted':False,'source':base['source'],'source_base':str(basepath),'rig_profile':str(rig_profile_path),'anchor_bone':anchor_bone,'candidate':str(candidate),'frames':[first,last],'step_frames':.25,'sample_count':len(frames),'patches':patches,'cache':metadata,'reload_error_m':reload_error,'unselected_vertices_error_m':body_error,'source_body_modified':False,'whole_hair_solved':False}
(out/'assembly_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('SURFACE_ASSEMBLY',json.dumps(result),flush=True)
