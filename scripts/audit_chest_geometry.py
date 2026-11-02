"""Compare chest geometry, independently of the restored shading normals."""
import sys,json,math
from pathlib import Path
from collections import defaultdict
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();faces=json.loads((ROOT/'outputs/cynical_cloth15/inspection.json').read_text(encoding='utf-8'))['Cloth']['all_islands'][2]['faces'];result={}
for label,folder in [('before','structured_v2'),('after','chest_hd')]:
 bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/cynical_cloth15'/folder/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);bpy.context.scene.frame_set(1);cloth=bpy.data.objects['Cloth'];mesh=cloth.data;neighbors=defaultdict(list);angles=[]
 for fi in faces:
  f=mesh.polygons[fi]
  for edge in f.edge_keys:neighbors[tuple(sorted(edge))].append(fi)
 for edge,fs in neighbors.items():
  if len(fs)==2:angles.append(math.degrees(mesh.polygons[fs[0]].normal.angle(mesh.polygons[fs[1]].normal)))
 result[label]={'faces':len(faces),'interior_edges':len(angles),'dihedral_degrees':{'median':float(np.median(angles)),'p90':float(np.percentile(angles,90)),'max':float(max(angles))},'edges_over_45_degrees':sum(a>45 for a in angles),'zero_area_faces':sum(mesh.polygons[i].area<1e-12 for i in faces),'shape_keys':len(mesh.shape_keys.key_blocks)}
result['scope']='Neutral base chest panel, geometric face normals; no material/shading normals. This is not an all-frame collision guarantee.'
(ROOT/'outputs/cynical_cloth15/chest_hd/chest_geometry_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('CHEST_GEOMETRY_AUDIT',json.dumps(result),flush=True)
