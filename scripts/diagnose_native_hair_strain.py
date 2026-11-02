import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'hair_tests_v2'
bpy.ops.wm.open_mainfile(filepath=str(root/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);p=json.loads((root/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);hairids=set(parts['ids']['hair_root']+parts['ids']['hair_mobile']);edges=np.array([e.vertices[:] for e in mesh.data.edges if all(i in hairids for i in e.vertices)])
bpy.context.scene.frame_set(1);bpy.context.view_layer.update();co1=coords(mesh);l1=np.linalg.norm(co1[edges[:,0]]-co1[edges[:,1]],axis=1);bpy.context.scene.frame_set(30);bpy.context.view_layer.update();co30=coords(mesh);l30=np.linalg.norm(co30[edges[:,0]]-co30[edges[:,1]],axis=1);sim=np.load(out/'native_xpbd_probe/frame30_coords.npy');ls=np.linalg.norm(sim[edges[:,0]]-sim[edges[:,1]],axis=1);valid=l1>.0005;ratio=np.where(valid,ls/np.maximum(l30,1e-9),1.);indices=np.argsort(ratio)[-15:][::-1];rows=[]
for j in indices:
 row={'edge':edges[j].tolist(),'frame1_length':float(l1[j]),'frame30_length':float(l30[j]),'sim_length':float(ls[j]),'ratio_current_source':float(ratio[j]),'source_positions':co30[edges[j]].tolist(),'sim_positions':sim[edges[j]].tolist(),'weights':[]}
 for i in edges[j]:row['weights'].append([(mesh.vertex_groups[g.group].name,g.weight) for g in mesh.data.vertices[int(i)].groups if mesh.vertex_groups[g.group].name in arm.pose.bones])
 rows.append(row)
report={'source_frame1_to30_ratio_max':float((l30[valid]/l1[valid]).max()),'sim_to_current_source_p99':float(np.percentile(ratio[valid],99)),'sim_to_current_source_max':float(ratio[valid].max()),'worst_edges':rows}
(out/'native_xpbd_probe/strain_diagnosis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('HAIR_STRAIN',json.dumps(report,ensure_ascii=False),flush=True)
