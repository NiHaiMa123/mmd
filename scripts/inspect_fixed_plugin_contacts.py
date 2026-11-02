import bpy,json,sys,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();p=ROOT.parent/'work/headswap_xl_codex/jiggle_physics_20261031/candidate16_convex'
config=json.loads((p/'configuration.json').read_text('utf8'));report=json.loads((p/'targeted_diagnostic/surface_audit.json').read_text('utf8'))
bpy.ops.wm.open_mainfile(filepath=str(p/'完整角色_JigglePhysics原版_15秒.blend'),load_ui=False,use_scripts=False)
m=bpy.data.objects['东雪莲x达妮娅_素体'];fixed={r['name'] for r in config['hair_bones'] if not r['enabled']}|{'頭','首'}
rows=[]
for row in report['rows']:
 if not row['crossings']:continue
 unique={hit['hair_triangle']:hit for hit in row['witnesses']};examples=[];fully=0
 for hit in unique.values():
  weights=[{m.vertex_groups[g.group].name:g.weight for g in m.data.vertices[i].groups if m.vertex_groups[g.group].name in m.find_armature().pose.bones} for i in hit['hair_vertices']]
  shares=[sum(w for name,w in ws.items() if name in fixed) for ws in weights]
  fully+=min(shares)>.9999
  if len(examples)<3:examples.append(dict(vertices=hit['hair_vertices'],fixed_shares=shares,weights=weights,point=hit['point']))
 rows.append(dict(frame=row['frame'],skin_bones=row['skin_collision_bones'],sampled_unique_hair_triangles=len(unique),fully_fixed_triangles=fully,examples=examples))
(p/'fixed_contact_analysis.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8');print(json.dumps(rows,ensure_ascii=False),flush=True)
