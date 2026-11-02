import sys,json
from pathlib import Path
from collections import defaultdict,deque
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();fit=ROOT/'outputs/stockings_sleeves/v21';bpy.ops.wm.open_mainfile(filepath=str(fit/'work.blend'),load_ui=False,use_scripts=False);body=bpy.data.objects['达妮娅_mesh'];me=body.data;me.calc_loop_triangles();mask=me.attributes['OutfitSleeveLiningFaces'];chosen={f.index for f in me.polygons if mask.data[f.index].value};edges=defaultdict(list)
for fi in chosen:
    face=me.polygons[fi];ps=[tuple(round(c,6) for c in me.vertices[i].co) for i in face.vertices]
    for k in range(len(ps)):edges[tuple(sorted((ps[k],ps[(k+1)%len(ps)])))].append(fi)
adj=defaultdict(set);boundary=set()
for ids in edges.values():
    if len(ids)==1:boundary.update(ids)
    for i in ids:adj[i].update(set(ids)-{i})
dist={i:0 for i in boundary};queue=deque(boundary)
while queue:
    i=queue.popleft()
    for j in adj[i]:
        if j not in dist:dist[j]=dist[i]+1;queue.append(j)
tri=[t for t in me.loop_triangles if me.materials[t.material_index].mmd_material.name_j=='Body'];rows=json.loads((fit/'review/visible_sleeve_lining_coverage.json').read_text(encoding='utf-8'))['3401'];print('LINING_BOUNDARY_SAMPLES',[(e['body_triangle'],tri[e['body_triangle']].polygon_index,dist.get(tri[e['body_triangle']].polygon_index),e['depth_m']) for r in rows for e in r['examples']],flush=True)
