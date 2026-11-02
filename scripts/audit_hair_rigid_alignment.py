import sys,json
from pathlib import Path
from collections import Counter
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'hair_tests_v2';bpy.ops.wm.open_mainfile(filepath=str(root/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);p=json.loads((root/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);arm.data.pose_position='REST';bpy.context.view_layer.update()
hairids=parts['ids']['hair_root']+parts['ids']['hair_mobile'];names={mesh.vertex_groups[g.group].name for i in hairids for g in mesh.data.vertices[i].groups if g.weight>.001 and mesh.vertex_groups[g.group].name in arm.data.bones};rows=[]
for obj in bpy.context.scene.objects:
 if getattr(obj,'mmd_type','')!='RIGID_BODY' or obj.mmd_rigid.bone not in arm.data.bones:continue
 bone=arm.data.bones[obj.mmd_rigid.bone];h=arm.matrix_world@bone.head_local;t=arm.matrix_world@bone.tail_local;c=obj.matrix_world.translation;v=t-h;u=max(0.,min(1.,(c-h).dot(v)/max(v.length_squared,1e-12)));distance=(c-(h+v*u)).length
 rows.append({'name':obj.name,'bone':bone.name,'hair':bone.name in names,'mode':str(obj.mmd_rigid.type),'shape':str(obj.mmd_rigid.shape),'size':list(obj.mmd_rigid.size),'centre':list(c),'head':list(h),'tail':list(t),'bone_length_m':v.length,'centre_to_segment_m':distance,'object_scale':list(obj.scale)})
hair=[r for r in rows if r['hair']];summary={'hair_rigids':len(hair),'hair_center_distance_median_m':float(np.median([r['centre_to_segment_m'] for r in hair])),'hair_center_distance_max_m':max(r['centre_to_segment_m'] for r in hair),'rigids':rows};(out/'rigid_alignment_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print('HAIR_ALIGNMENT',len(hair),summary['hair_center_distance_median_m'],summary['hair_center_distance_max_m'],flush=True)
# Isolate the exact worst deformation edges in the same source pose.
arm.data.pose_position='POSE';bpy.context.scene.frame_set(450);bpy.context.view_layer.update();source=coords(mesh);candidate=np.load(out/'mmd_filters_hybrid/keypose0450.npz')['coordinates'];hset=set(hairids);edges=np.array([edge.vertices[:] for edge in mesh.data.edges if all(i in hset for i in edge.vertices)]);length=np.linalg.norm(source[edges[:,0]]-source[edges[:,1]],axis=1);valid=length>.0005;ratio=np.linalg.norm(candidate[edges[:,0]]-candidate[edges[:,1]],axis=1)/np.maximum(length,1e-8);idx=np.flatnonzero(valid);idx=idx[np.argsort(ratio[idx])[-12:][::-1]];worst=[]
for j in idx:worst.append({'edge':edges[j].tolist(),'ratio':float(ratio[j]),'source_length_m':float(length[j]),'weights':[[(mesh.vertex_groups[g.group].name,g.weight) for g in mesh.data.vertices[int(i)].groups if mesh.vertex_groups[g.group].name in arm.pose.bones] for i in edges[j]]})
(out/'hybrid_worst_edges.json').write_text(json.dumps(worst,ensure_ascii=False,indent=2),encoding='utf8');print('HYBRID_WORST',json.dumps(worst[:3],ensure_ascii=False),flush=True)
