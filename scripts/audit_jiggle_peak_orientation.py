"""Read-only separation of bone swing/twist and visible hair movement."""
import argparse,json,math,sys,runpy
from pathlib import Path
import bpy,numpy as np
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(a.root);engine('import_export').ensure_mmd_tools();meta=json.loads((repo.parent/'work/headswap_xl_codex/standard_proxy_20261031/inspection/inputs.json').read_text('utf8'));results=[]
def angle(a,b):return float(np.degrees(np.arccos(np.clip(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)),-1,1))))
cases=[('baseline',repo.parent/'work/headswap_xl_codex/jiggle_physics_20261031/candidate13',356,357,'Hair3-1.R'),('A_ellipsoids_only',root/'A_ellipsoids_only',344,345,'Sidetail1.R'),('B_smaller_radius',root/'B_smaller_radius',343,344,'Sidetail1.R'),('C_shorter_root',root/'C_shorter_root',351,352,'Hair_in3-1.R')]
for name,folder,f0,f1,chain in cases:
 source=json.loads((folder/'bake_report.json').read_text('utf8'))['blend'];bpy.ops.wm.open_mainfile(filepath=source,load_ui=False,use_scripts=False);s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();chainrow=next(c for c in meta['chains'] if c['name']==chain);names=chainrow['bones'];states=[]
 for frame in [f0,f1]:
  s.frame_set(frame);bpy.context.view_layer.update();h=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix);ih=np.linalg.inv(h);state={}
  for n in names:
   b=arm.pose.bones[n];world=np.array(arm.matrix_world@b.matrix);mat=ih@world;head=np.array(arm.matrix_world@b.head);tail=np.array(arm.matrix_world@b.tail)
   state[n]=dict(matrix=mat,head=ih[:3,:3]@head+ih[:3,3],tail=ih[:3,:3]@tail+ih[:3,3],constraints=[dict(type=c.type,name=c.name,influence=c.influence,mute=c.mute) for c in b.constraints],connected=b.bone.use_connect,inherit_scale=b.bone.inherit_scale)
  states.append(state)
 rows=[]
 for n in names:
  q0,q1=states[0][n],states[1][n];r0=q0['matrix'][:3,:3];r1=q1['matrix'][:3,:3];r0=r0/np.linalg.norm(r0,axis=0);r1=r1/np.linalg.norm(r1,axis=0);delta=r0.T@r1;total=float(np.degrees(np.arccos(np.clip((np.trace(delta)-1)/2,-1,1))))
  rows.append(dict(bone=n,head_local_head_step_cm=float(np.linalg.norm(q1['head']-q0['head'])*100),head_local_tail_step_cm=float(np.linalg.norm(q1['tail']-q0['tail'])*100),orientation_change_deg=total,y_axis_swing_deg=angle(r0[:,1],r1[:,1]),constraints=q0['constraints'],connected=q0['connected'],inherit_scale=q0['inherit_scale']))
 results.append(dict(name=name,frames=[f0,f1],chain=chain,bones=rows))
(root/'peak_orientation_review.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf8');print('PEAK_ORIENTATION_REVIEW',json.dumps(results,ensure_ascii=False),flush=True)
for name,frames in [('C_shorter_root','349,350'),('B_smaller_radius','343,344')]:
 folder=root/name;source=json.loads((folder/'bake_report.json').read_text('utf8'))['blend'];sys.argv=[str(repo/'scripts/render_full_hair_showcase.py'),'--','--source',source,'--out',str(folder/'keyframes'),'--frames',frames,'--samples','24','--device','GPU'];runpy.run_path(str(repo/'scripts/render_full_hair_showcase.py'),run_name='__main__')
