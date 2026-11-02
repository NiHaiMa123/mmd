"""Locate proxy contact versus actual hair deformation at an instability."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,regions,audit_frame
from animation_contact_tools.root_envelope_feedback import capsule_features
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--frames',default='1,200,226,230,234,235,236,237,240,300,440');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
out=Path(a.run);report=json.loads((out/'report.json').read_text('utf8'));motion=np.load(out/'bundle_motion.npz');profile=json.loads((ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028/body_track/rig_profile.json').read_text('utf8'));engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=report['source'],load_ui=False,use_scripts=False)
mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(mesh,arm,profile);radii=motion['radii'];rest=motion['rest_guide'];ids=motion['ids'];skinfaces=[f for role,fs in parts['faces'].items() if not role.startswith('hair') for f in fs];rows=[]
for f in [int(x) for x in a.frames.split(',')]:
 bpy.context.scene.frame_set(f);bpy.context.view_layer.update();co=coords(mesh);guide=motion['guides'][f-report['frames'][0]];tree=BVHTree.FromPolygons(co.tolist(),skinfaces,all_triangles=True);near=[]
 for i,point in enumerate(guide):
  q,n,fi,d=tree.find_nearest(Vector(point));near.append({'point':i,'distance_minus_radius_m':float(d-radii[i]),'distance_m':float(d),'radius_m':float(radii[i]),'normal_sign':float((Vector(point)-q).dot(n))})
 regions_summary={}
 for role in ('head','arm.L','hand.L','arm.R','hand.R'):
  features=[]
  for count in (4,10,len(guide)):
   gap,_=capsule_features(co[parts['ids'][role]],guide[:count],radii[:count]);features.append({'guide_points':count,'min_vertex_gap_m':float(gap.min()),'vertices_inside':int(np.sum(gap<0))})
  regions_summary[role]=features
 ratio=np.linalg.norm(np.diff(guide,axis=0),axis=1)/np.linalg.norm(np.diff(rest,axis=0),axis=1)
 rows.append({'frame':f,'worst_guide_segment':int(np.argmax(ratio)),'max_guide_ratio':float(ratio.max()),'near_body':sorted(near,key=lambda r:r['distance_minus_radius_m'])[:6],'regions':regions_summary})
(out/'instability_diagnosis.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print('BUNDLE_INSTABILITY',json.dumps([{'frame':r['frame'],'guide_ratio':r['max_guide_ratio'],'near_body':r['near_body'][:2],'regions':{k:v[0]['min_vertex_gap_m'] for k,v in r['regions'].items()}} for r in rows]),flush=True)
