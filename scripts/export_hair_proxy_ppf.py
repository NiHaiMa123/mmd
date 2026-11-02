"""Export a clean physical hair clump and animated exact skin to native PPF."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.exact_skin_collider import build_exact_skin_topology
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--weld-distance',type=float,default=1e-6);p.add_argument('--out',required=True);p.add_argument('--first',type=int,default=236);p.add_argument('--last',type=int,default=254);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
if (out/'manifest.json').exists():raise ValueError('Use a new PPF proxy directory')
run=Path(a.run);r=json.loads((run/'report.json').read_text('utf8'));d=np.load(run/'native_integer.npz');config=r['setup']['bundle'];profile=json.loads(Path(config['source_profile']).read_text('utf8'));engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(run/'SurfaceProxy_Live_Unbaked.blend'),load_ui=False,use_scripts=False);proxy=next(o for o in bpy.context.scene.objects if any(m.type=='CLOTH' for m in o.modifiers));faces=np.array([tuple(p.vertices) for p in proxy.data.polygons]);group=proxy.vertex_groups['HairProxy_Attachment'].index;pins=np.array([sum(g.weight for g in v.groups if g.group==group) for v in proxy.data.vertices]);pins=(pins>.999).astype(float);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];skin_ids,skin_faces,meta=build_exact_skin_topology(mesh,arm,profile,triangulate=True,weld_distance=a.weld_distance);arm.data.pose_position='REST';bpy.context.view_layer.update();body_rest=coords(mesh)[skin_ids];arm.data.pose_position='POSE';bpy.context.scene.frame_set(a.first);bpy.context.view_layer.update();head0=np.array(arm.matrix_world@arm.pose.bones[config['anchor_bone']].matrix);start=d['proxy_coordinates'][a.first-1];cloth=[];body=[];frames=np.arange(a.first,a.last+.001,.25)
for frame in frames:
 bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();head=np.array(arm.matrix_world@arm.pose.bones[config['anchor_bone']].matrix);delta=head@np.linalg.inv(head0);cloth.append(start@delta[:3,:3].T+delta[:3,3]);body.append(coords(mesh)[skin_ids])
np.savez_compressed(out/'trajectories.npz',cloth=cloth,body=body,cloth_faces=faces,body_faces=skin_faces,pins=pins,original_mapping=np.arange(len(start)),skin_ids=skin_ids,body_rest=body_rest)
manifest=dict(source_run=str(run),source_blend=r['source'],proxy_vertices=len(start),proxy_triangles=len(faces),fps=30,sample_times_s=((frames-a.first)/30).tolist(),source_frames=[a.first,a.last],hard_pins=int(pins.sum()),skin_topology=meta,contact_exemptions=0)
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');print('HAIR_PPF_EXPORT',json.dumps({k:v for k,v in manifest.items() if k!='sample_times_s'}),flush=True)
