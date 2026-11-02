import bpy,json,sys,time,traceback
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(r'E:\project\mmd\mmd_repo');sys.path.insert(0,str(ROOT/'addon'))
OUT=ROOT.parent/'work/headswap_xl_codex/native_mmd_bridge_20261030/headless_bullet/REVIEW_RAW'
def audit():
 try:
  from animation_contact_tools.surface import coords,crosses
  from animation_contact_tools.closed_collider_field import ClosedColliderField
  src=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input_body_aware';manifest=json.loads((src/'export_complete.json').read_text('utf8'));profile=json.loads(Path(manifest['rig_profile']).read_text('utf8'));mesh=bpy.data.objects[profile['mesh']];ids=np.load(src/'hair_ids.npy');skin=np.load(src/'skin_ids.npy');hf=np.load(src/'hair_faces.npy');bf=np.load(src/'body_faces.npy');real=np.load(src/'real_body_faces.npy').astype(bool);rows=[]
  for f in [1,211,331,336,450]:
   bpy.context.scene.frame_set(f);bpy.context.view_layer.update();co=coords(mesh);x=co[ids];b=co[skin];ht=BVHTree.FromPolygons(x.tolist(),hf.tolist(),all_triangles=True);bt=BVHTree.FromPolygons(b.tolist(),bf[real].tolist(),all_triangles=True);pairs=ht.overlap(bt);hits=[];hx=[Vector(v) for v in x];bv=[Vector(v) for v in b];faces=bf[real]
   for a,c in pairs:
    if crosses([hx[v] for v in hf[a]],[bv[v] for v in faces[c]]):hits.append([a,c])
   d,_=ClosedColliderField(b,bf)(x);rows.append(dict(frame=f,crossings=len(hits),inside_vertices=int((d<-.0001).sum()),minimum_distance_m=float(d.min()),witness_pairs=hits[:12]))
  report=dict(stage='DIAGNOSTIC_COMPLETE',rows=rows,actual_hair_triangles=len(hf),actual_skin_triangles=int(real.sum()))
 except BaseException as exc:report=dict(stage='FAILED',error=repr(exc),traceback=traceback.format_exc())
 (OUT/'raw_contact_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');bpy.context.scene.frame_set(1)
 return None
bpy.app.timers.register(audit,first_interval=.1);print('Whole head actual mesh contact audit queued via MCP')
