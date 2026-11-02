"""Locate whether contact failures arise in physics, attachment or display transfer."""
import argparse, json, sys
from pathlib import Path
import bpy, numpy as np
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
from animation_contact_tools.exact_skin_collider import build_exact_skin_topology
p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.run)
r=json.loads((out/'report.json').read_text('utf8'));m=np.load(out/'native_integer.npz');config=r['setup']['bundle'];profile=json.loads(Path(config['source_profile']).read_text('utf8'));engine('import_export').ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=str(out/'SurfaceProxy_Live_Unbaked.blend'),load_ui=False,use_scripts=False)
proxy=next(o for o in bpy.context.scene.objects if any(x.type=='CLOTH' for x in o.modifiers));pf=[tuple(f.vertices) for f in proxy.data.polygons];group=proxy.vertex_groups['HairProxy_Attachment'].index;pw=np.array([sum(g.weight for g in v.groups if g.group==group) for v in proxy.data.vertices]);pe=np.array([e.vertices[:] for e in proxy.data.edges]);pl=np.linalg.norm(m['proxy_coordinates'][0][pe[:,0]]-m['proxy_coordinates'][0][pe[:,1]],axis=1)
bpy.ops.wm.open_mainfile(filepath=r['candidate'],load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];skin_ids,faces,meta=build_exact_skin_topology(mesh,arm,profile,triangulate=True);weights=np.load(ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029/multi_bundle/left_root_pin_audit.npz')['head_weights'];rows=[]
for frame in (1,240,242,243,245,248,250,255,260,270):
 if frame>len(m['proxy_coordinates']):continue
 bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();co=coords(mesh);field=ClosedColliderField(co[skin_ids],faces);pc=m['proxy_coordinates'][frame-1];dd,dn=field(co[m['ids']]);pd,pn=field(pc);pt=BVHTree.FromPolygons(pc.tolist(),pf,all_triangles=True);st=field.tree;ratio=np.linalg.norm(pc[pe[:,0]]-pc[pe[:,1]],axis=1)/pl
 bad=np.flatnonzero(dd<-.0001);pbad=np.flatnonzero(pd<-.0001)
 rows.append(dict(frame=frame,proxy_skin_intersections=len(pt.overlap(st)),proxy_inside=len(pbad),proxy_min_signed_m=float(pd.min()),proxy_bad_pin_weights=pw[pbad].tolist(),display_inside=len(bad),display_min_signed_m=float(dd.min()),display_bad_pin_weights=weights[bad].tolist(),proxy_min_edge_ratio=float(ratio.min()),proxy_max_edge_ratio=float(ratio.max())))
(out/'contact_diagnosis.json').write_text(json.dumps(dict(samples=rows,skin_topology=meta),indent=2),encoding='utf8')
for row in rows:print(json.dumps(row),flush=True)
