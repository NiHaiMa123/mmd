import sys,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
base=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030';out=base/'review_11s_20261030';engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(base/'FINAL_REPRO15/完整角色_整头连续物理_15秒.blend'),load_ui=False,use_scripts=False);s=bpy.context.scene;s.frame_set(326);m=bpy.data.objects['东雪莲x达妮娅_素体'];bpy.context.view_layer.update();co=coords(m);m.data.calc_loop_triangles();attr=m.data.attributes['SurfaceClass'];tris=[t for t in m.data.loop_triangles if attr.data[t.polygon_index].value in [1,2,3]];tree=BVHTree.FromPolygons(co.tolist(),[t.vertices[:] for t in tris],all_triangles=True);cam=s.camera;projection=cam.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(),x=1920,y=1080);inverse=projection.inverted();ids=np.load(base/'input_body_aware/hair_ids.npy');hard=np.load(base/'input_body_aware/hard_roots.npy');mask=np.zeros(len(co),dtype=bool);mask[ids]=hard;rows=[]
for y in range(324,350,2):
 for x in range(910,965,2):
  q=inverse@Vector((2*(x+.5)/1920-1,1-2*(y+.5)/1080,-1,1));q/=q.w;direction=(cam.matrix_world.to_3x3()@q.xyz).normalized();point,normal,index,d=tree.ray_cast(cam.matrix_world.translation,direction)
  if index is None:continue
  t=tris[index];cls=attr.data[t.polygon_index].value
  if cls==3:rows.append(dict(pixel=[x,y],vertices=list(t.vertices),hard=mask[list(t.vertices)].tolist(),world=list(point),material=m.material_slots[m.data.polygons[t.polygon_index].material_index].material.name))
(out/'visible_shoulder_hair.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8');print('SHOULDER_HAIR_HITS',len(rows),'all_hard',sum(all(r['hard']) for r in rows),'all_free',sum(not any(r['hard']) for r in rows),flush=True)
