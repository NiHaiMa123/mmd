import bpy,json,sys
from pathlib import Path
root=Path(r'E:\project\mmd\work\headswap_xl_codex\jiggle_physics_20261031');out=root/'candidate05'
bpy.ops.wm.open_mainfile(filepath=str(out/'完整角色_JigglePhysics原版_15秒.blend'),use_scripts=False,load_ui=False)
m=bpy.data.objects['东雪莲x达妮娅_素体'];arm=bpy.data.objects['东雪莲x达妮娅_骨架'];gn={g.index:g.name for g in m.vertex_groups}
def weights(ids):
 return {str(i):{gn[g.group]:round(g.weight,5) for g in m.data.vertices[i].groups if gn[g.group] in arm.pose.bones} for i in sorted(ids)}
rows=json.loads((out/'audit/surface_audit.json').read_text('utf8'))['rows'];results=[]
for r in rows:
 if not r['crossings']:continue
 h={i for w in r['witnesses'] for i in w['hair_vertices']};s={i for w in r['witnesses'] for i in w['skin_vertices']}
 results.append(dict(frame=r['frame'],hair=weights(h),skin=weights(s)))
(root/'remaining_witness_weights.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(results,ensure_ascii=False),flush=True)
