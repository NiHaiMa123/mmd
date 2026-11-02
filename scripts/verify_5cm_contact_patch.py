"""Confirm that the over-limit vertex component is connected inside skin."""
import bpy,sys,json,argparse,heapq,collections,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
from animation_contact_tools.hair_contact_threshold import embedded_patch_metrics
p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run=Path(a.run)
r=json.loads((run/'result.json').read_text('utf8'));frame=(r.get('stop') or {}).get('frame',r['frames'][1])
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=r['blend'],load_ui=False,use_scripts=False);s=bpy.context.scene;s.frame_set(frame);bpy.context.view_layer.update();actor=bpy.data.objects['东雪莲x达妮娅_素体'];co=coords(actor)
base=repo.parent/'work/headswap_xl_codex';d=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'));exp=base/'fullhair_repro_20261030/input_body_aware';skin=np.load(exp/'skin_ids.npy');faces=np.load(exp/'body_faces.npy');field=ClosedColliderField(co[skin],faces)
if r.get('stop'):worst=r['stop']['worst_patch']
else:
 signed_all,_=field(co[d['ids']]);measured=embedded_patch_metrics(co[d['ids']],signed_all,d['edges'],limit_m=.05);assert measured['exceeds_limit'];worst=measured['patches'][0]
members=np.array(worst['local_vertex_ids'],int);points=co[d['ids'][members]];local={int(v):i for i,v in enumerate(members)}
delta=points[:,None]-points[None,:];distance=np.linalg.norm(delta,axis=2);aa,bb=np.unravel_index(np.argmax(distance),distance.shape)
edges=[(local[int(a)],local[int(b)]) for a,b in d['edges'] if int(a) in local and int(b) in local]
segments=[];slices=[];cursor=0
for a,b in edges:
 samples=np.linspace(points[a],points[b],max(3,int(np.ceil(np.linalg.norm(points[b]-points[a])/.001))+1));segments.append(samples);slices.append((cursor,cursor+len(samples)));cursor+=len(samples)
allpoints=np.concatenate(segments);signed,_=field(allpoints);good=[];bad=[];adj={i:[] for i in range(len(points))}
for (a,b),(start,end) in zip(edges,slices):
 row=dict(local_endpoints=[int(members[a]),int(members[b])],maximum_sampled_signed_distance_m=float(signed[start:end].max()),minimum_sampled_signed_distance_m=float(signed[start:end].min()))
 if row['maximum_sampled_signed_distance_m']<0:
  good.append(row);length=float(np.linalg.norm(points[a]-points[b]));adj[a].append((b,length));adj[b].append((a,length))
 else:bad.append(row)
best={int(aa):0.};previous={};queue=[(0.,int(aa))]
while queue:
 cost,node=heapq.heappop(queue)
 if cost>best[node]:continue
 if node==bb:break
 for nxt,w in adj[node]:
  if cost+w<best.get(nxt,float('inf')):best[nxt]=cost+w;previous[nxt]=node;heapq.heappush(queue,(cost+w,nxt))
path=[]
if int(bb) in best:
 node=int(bb);path=[node]
 while node!=int(aa):node=previous[node];path.append(node)
 path.reverse()
def screen(point):
 v=world_to_camera_view(s,s.camera,Vector(point));return [float(v.x*1920),float((1-v.y)*1080)]
chains=sorted({meta['chains'][int(d['chain_labels'][j])]['name'] if d['chain_labels'][j]>=0 else 'head-attached hair' for j in members})
real=np.load(exp/'real_body_faces.npy').astype(bool);actualfaces=faces[real];tree=BVHTree.FromPolygons(co[skin].tolist(),actualfaces.tolist(),all_triangles=True);bodybones=collections.Counter();arm=actor.find_armature();bonenames=set(arm.pose.bones.keys())
for point in points:
 _,_,index,_=tree.find_nearest(Vector(point));weights={}
 for vi in skin[actualfaces[index]]:
  for group in actor.data.vertices[int(vi)].groups:
   name=actor.vertex_groups[group.group].name
   if name in bonenames:weights[name]=weights.get(name,0)+group.weight
 bodybones[max(weights,key=weights.get)]+=1
report=dict(frame=frame,original_seconds=(frame-1)/30,maximum_embedded_span_cm=float(distance[aa,bb]*100),maximum_depth_cm=worst['maximum_depth_m']*100,chains=chains,patch_vertices=len(points),tested_edges=len(edges),fully_inside_edges=len(good),edges_with_outside_samples=len(bad),widest_pair_connected_by_verified_inside_mesh_edges=bool(path),verified_inside_surface_path_length_cm=best.get(int(bb),0)*100,widest_pair_source_vertices=d['ids'][members[[aa,bb]]].tolist(),widest_pair_pixels=[screen(points[aa]),screen(points[bb])],inside_path_pixels=[screen(points[i]) for i in path],patch_pixels=[screen(p) for p in points],bad_edges=bad,simulation_started=False,classification='CONFIRMED_CONNECTED_OVER_5CM_PATCH' if path else 'COARSE_VERTEX_CONNECTIVITY_NEEDS_REFINEMENT')
report['nearest_actual_body_bones']=dict(bodybones.most_common())
signed_all,_=field(co[d['ids']]);all_measured=embedded_patch_metrics(co[d['ids']],signed_all,d['edges'],limit_m=.05)
report['reopened_maximum_extent_cm']=all_measured['maximum_patch_extent_m']*100
report['reopened_maximum_depth_cm']=all_measured['maximum_depth_m']*100
report['side_surface_display_contacts']=[]
for label in [23,24]:
 masked=signed_all.copy();masked[d['chain_labels']!=label]=1.
 contact=embedded_patch_metrics(co[d['ids']],masked,d['edges'],limit_m=.05)
 report['side_surface_display_contacts'].append(dict(chain=meta['chains'][label]['name'],inside_vertices=contact['inside_vertices'],maximum_extent_cm=contact['maximum_patch_extent_m']*100,maximum_depth_cm=contact['maximum_depth_m']*100,over_5cm=contact['exceeds_limit']))
report['all_over_limit_patches']=[dict(vertices=patch['vertices'],chains=sorted({meta['chains'][int(d['chain_labels'][j])]['name'] if d['chain_labels'][j]>=0 else 'head-attached hair' for j in patch['local_vertex_ids']}),maximum_extent_cm=patch['maximum_spatial_extent_m']*100,maximum_depth_cm=patch['maximum_depth_m']*100) for patch in all_measured['patches'] if patch['exceeds_limit']]
(run/'threshold_patch_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
