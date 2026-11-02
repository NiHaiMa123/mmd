import bpy,json,sys,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();p=ROOT.parent/'work/headswap_xl_codex/jiggle_physics_20261031/candidate12'
bpy.ops.wm.open_mainfile(filepath=str(p/'完整角色_JigglePhysics原版_15秒.blend'),use_scripts=False,load_ui=False)
m=bpy.data.objects['东雪莲x达妮娅_素体'];arm=m.find_armature();report=json.loads((p/'early_diagnostic/surface_audit.json').read_text('utf8'))
rows=[]
for frame in report['rows']:
 if not frame['crossings']:continue
 bpy.context.scene.frame_set(int(frame['frame']));bpy.context.view_layer.update()
 for witness in frame['witnesses'][:5]:
  row=dict(frame=frame['frame'],witness=witness,vertices=[])
  for i in witness['hair_vertices']:
   weights={m.vertex_groups[g.group].name:g.weight for g in m.data.vertices[i].groups if m.vertex_groups[g.group].name in arm.pose.bones}
   row['vertices'].append(dict(id=i,weights=weights))
  rows.append(row)
(p/'root_contacts.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8');print(json.dumps(rows,ensure_ascii=False),flush=True)
