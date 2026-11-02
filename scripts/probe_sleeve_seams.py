import sys,json
from pathlib import Path
from collections import Counter,defaultdict
import bpy
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/cynical_cloth15/chest_hd/Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);obj=bpy.data.objects['ClothSimulationSurface'];mesh=obj.data;report={}
for side in ('L','R'):
 group=obj.vertex_groups['腕.'+side].index;ids={v.index for v in mesh.vertices if any(g.group==group and g.weight>.5 for g in v.groups)};edges=Counter(tuple(sorted(e)) for f in mesh.polygons if all(i in ids for i in f.vertices) for e in f.edge_keys);boundary={i for edge,count in edges.items() if count==1 for i in edge};kd=KDTree(len(ids))
 for i in ids:kd.insert(mesh.vertices[i].co,i)
 kd.balance();pairs=sorted({tuple(sorted((i,j))) for i in ids for _,j,d in kd.find_range(mesh.vertices[i].co,1e-5) if i!=j});report[side]={'vertices':len(ids),'boundary_edges':sum(n==1 for n in edges.values()),'duplicate_pairs':len(pairs),'duplicated_boundary_pairs':sum(a in boundary and b in boundary for a,b in pairs),'examples':[{'ids':[a,b],'position':list(mesh.vertices[a].co)} for a,b in pairs[:8]]}
out=ROOT/'outputs/sleeve_13s/diagnosis/seams.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('SLEEVE_SEAMS',json.dumps(report),flush=True)
