import bpy,sys,json,numpy as np
from pathlib import Path
from bpy_extras.object_utils import world_to_camera_view
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools()
base=repo.parent/'work/headswap_xl_codex';src=base/'normal_preview15_20261101/完整角色_现有最佳流程_15秒预览.blend'
bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
s=bpy.context.scene;arm=bpy.data.objects['东雪莲x达妮娅_骨架'];obj=bpy.data.objects['东雪莲x达妮娅_素体']
d=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'))
rows=[]
for f in [1,151,331,450]:
 s.frame_set(f);bpy.context.view_layer.update();ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
 for j,c in enumerate(meta['chains']):
  if not c['name'].startswith(('Sidehair','Sidetail')):continue
  ids=d['ids'][d['chain_labels']==j];pts=[world_to_camera_view(s,s.camera,ev.matrix_world@me.vertices[int(i)].co) for i in ids]
  bbox=[[min(p[k] for p in pts),max(p[k] for p in pts)] for k in range(2)]
  bones=[]
  for name in c['bones']:
   b=arm.pose.bones[name];pts2=[world_to_camera_view(s,s.camera,arm.matrix_world@p) for p in [b.head,b.tail]]
   bones.append(dict(name=name,screen=[list(p)[:2] for p in pts2]))
  rows.append(dict(frame=f,chain=c['name'],bbox=bbox,bones=bones))
 ev.to_mesh_clear()
action=arm.animation_data.action
report=dict(rows=rows,action=action.name,slot=arm.animation_data.action_slot.identifier,nla=[dict(track=t.name,strips=[dict(name=x.name,start=x.frame_start,end=x.frame_end,scale=x.scale) for x in t.strips]) for t in arm.animation_data.nla_tracks])
out=base/'short_sidehair_20261101';out.mkdir(exist_ok=True)
(out/'inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(report,ensure_ascii=False),flush=True)
