import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';old=base/'hair_curves_20261028/single_bundle_rod_frames';out=base/'hair_arm_feedback_20261028';out.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(base/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);p=json.loads((base/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);motion=np.load(old/'bundle_motion.npz');guide=motion['rest_guide'];radii=motion['radii'];scene=bpy.context.scene;scene.frame_set(200);bpy.context.view_layer.update();anchor0=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix);rows=[]
for f in (200,208,212,214,216,217,218,219,220,222,224,228,232,240,250):
 scene.frame_set(f);bpy.context.view_layer.update();co=coords(mesh);m=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix)@np.linalg.inv(anchor0);g=guide@m[:3,:3].T+m[:3,3];row={'frame':f,'regions':{}}
 for role in ('arm.R','hand.R'):
  ids=parts['ids'][role];v=co[ids];summary=[]
  for n in (3,6,10):
   a=g[:n];d=g[1:n+1]-a;u=np.clip(np.einsum('vsi,si->vs',v[:,None,:]-a[None,:,:],d)/np.sum(d*d,axis=1),0,1);q=a+u[:,:,None]*d;r=radii[:n]+u*(radii[1:n+1]-radii[:n]);gap=np.linalg.norm(v[:,None,:]-q,axis=2)-r;iv,iseg=np.unravel_index(np.argmin(gap),gap.shape);summary.append({'segments':n,'min_gap_m':float(gap[iv,iseg]),'violating_vertices':int(np.sum(gap.min(1)<.004)),'vertex':int(ids[iv]),'segment':int(iseg),'point':v[iv].tolist(),'normal':((v[iv]-q[iv,iseg])/max(np.linalg.norm(v[iv]-q[iv,iseg]),1e-12)).tolist()})
  row['regions'][role]=summary
 rows.append(row)
 print('ROOT_CONTACT',f,[(role,[(s['segments'],round(s['min_gap_m']*1000,1),s['violating_vertices']) for s in entries]) for role,entries in row['regions'].items()],flush=True)
(out/'root_contact_diagnosis.json').write_text(json.dumps({'source':bpy.data.filepath,'anchor_bone':'頭','anchor_bind_matrix':anchor0.tolist(),'guide':guide.tolist(),'radii':radii.tolist(),'rows':rows},ensure_ascii=False,indent=2),encoding='utf8')
