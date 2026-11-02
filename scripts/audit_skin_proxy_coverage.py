"""Compare source-skin -> collider coverage, including true contact regions."""
import json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,regions
from animation_contact_tools.skin_collision_cage import build_skin_cage
from animation_contact_tools.exact_skin_collider import build_exact_skin_topology
root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029';source=json.loads((root/'rest_cage_refined_steps/report.json').read_text('utf8'))['source'];profile=json.loads((ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028/body_track/rig_profile.json').read_text('utf8'));engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=source,load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(mesh,arm,profile);cage,meta=build_skin_cage(mesh,arm,profile,voxel_size=.003,binding_pose='REST');ids,faces,exact=build_exact_skin_topology(mesh,arm,profile);rows=[]
for frame in [247.5,342,350,355,373]:
 bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();co=coords(mesh);trees={'voxel':BVHTree.FromPolygons(coords(cage).tolist(),[tuple(p.vertices) for p in cage.data.polygons]),'exact':BVHTree.FromPolygons(co[ids].tolist(),faces)};results={}
 for role in ['arm.R','hand.R','head']:
  points=np.vstack((co[parts['ids'][role]],np.array([co[list(f)].mean(0) for f in parts['faces'][role]])));stride=max(1,int(np.ceil(len(points)/12000)));points=points[::stride];metrics={}
  for name,tree in trees.items():
   d=np.array([tree.find_nearest(Vector(p))[3] for p in points]);metrics[name]={'peak_m':float(d.max()),'p99_m':float(np.percentile(d,99)),'samples_above_1cm':int(np.sum(d>.01))}
  results[role]={'source_samples':len(points),'stride':stride,**metrics}
 rows.append({'frame':frame,'regions':results});print('SKIN_COVERAGE',frame,results,flush=True)
(root/'surface_projection/skin_proxy_coverage.json').write_text(json.dumps({'voxel':meta,'exact':exact,'samples':rows,'full_surface_bound_proven':False},ensure_ascii=False,indent=2),encoding='utf8')
