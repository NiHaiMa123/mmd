"""Read-only: distinguish pinned/skin-weighted contact from solver failure."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
from animation_contact_tools.hair_contact_threshold import embedded_patch_metrics
p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run=Path(a.run)
r=json.loads((run/'result.json').read_text('utf8'));setup=json.loads((run/'setup.json').read_text('utf8'));prepared=json.loads((Path(setup['prepared']).parent/'setup.json').read_text('utf8'));base=repo.parent/'work/headswap_xl_codex';d=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'));skin=np.load(base/'fullhair_repro_20261030/input_body_aware/skin_ids.npy');bf=np.load(base/'fullhair_repro_20261030/input_body_aware/body_faces.npy')
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=r['blend'],load_ui=False,use_scripts=False);s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();members=np.array(r['stop']['worst_patch']['local_vertex_ids']);sourceids=d['ids'][members];labels=sorted(set(d['chain_labels'][members].tolist()));rows=[]
s.frame_set(1);bpy.context.view_layer.update();initial=coords(actor);field0=ClosedColliderField(initial[skin],bf)
rest_frames={}
for label in labels:
 for name in meta['chains'][label]['bones']:
  goal=bpy.data.objects['ClothBoneGoal_'+name].evaluated_get(bpy.context.evaluated_depsgraph_get());rest_frames[name]=((arm.matrix_world@arm.pose.bones[name].matrix).to_quaternion(),goal.matrix_world.to_quaternion())
for label in labels:
 proxy=bpy.data.objects[prepared['proxies'][label]['proxy']];q0=coords(proxy);dist0,_=field0(q0);pins=np.array([q.value>.99 for q in proxy.data.attributes['HairRootPin'].data]);rows.append(dict(chain=meta['chains'][label]['name'],initial_inside_pinned=int((pins&(dist0<-.0001)).sum()),initial_minimum_signed_m=float(dist0.min())))
s.frame_set(r['frames'][1]);bpy.context.view_layer.update();co=coords(actor);field=ClosedColliderField(co[skin],bf)
for row,label in zip(rows,labels):
 proxy=bpy.data.objects[prepared['proxies'][label]['proxy']];q=coords(proxy);dist,_=field(q);pins=np.array([x.value>.99 for x in proxy.data.attributes['HairRootPin'].data]);edges=np.array([e.vertices[:] for e in proxy.data.edges]);contact=embedded_patch_metrics(q,dist,edges,limit_m=.05)
 nearest=np.argmin(np.linalg.norm(co[sourceids,None,:]-q[None,:,:],axis=2),axis=1)
 row.update(proxy_vertices=len(q),inside_pinned=int((pins&(dist<-.0001)).sum()),inside_free=int((~pins&(dist<-.0001)).sum()),maximum_pinned_depth_m=float(max(0,-dist[pins].min())),maximum_free_depth_m=float(max(0,-dist[~pins].min())) if (~pins).any() else 0,proxy_maximum_embedded_extent_m=contact['maximum_patch_extent_m'],nearest_proxy_pinned_for_actual_patch=int(pins[nearest].sum()),actual_patch_vertices=len(sourceids))
weights=[];names={g.index:g.name for g in actor.vertex_groups};bones=set(arm.pose.bones.keys())
for vi in sourceids:
 w={names[g.group]:float(g.weight) for g in actor.data.vertices[int(vi)].groups if names.get(g.group) in bones};total=sum(w.values());weights.append(dict(source_vertex=int(vi),head_weight=w.get('頭',0)/total if total else 0,weights=w))
report=dict(frame=r['frames'][1],chains=rows,display_patch_weights=weights,head_weight_min=min(w['head_weight'] for w in weights),head_weight_max=max(w['head_weight'] for w in weights),new_physics_started=False,original_weights_edited=False)
orientation=[]
for name,(rest_bone,rest_goal) in rest_frames.items():
 goal=bpy.data.objects['ClothBoneGoal_'+name].evaluated_get(bpy.context.evaluated_depsgraph_get());expected=goal.matrix_world.to_quaternion()@rest_goal.inverted()@rest_bone;actual=(arm.matrix_world@arm.pose.bones[name].matrix).to_quaternion();y=Vector((0,1,0));z=Vector((0,0,1));binding=next(x for x in prepared['bone_tracking_bindings'] if x['bone']==name);proxy=bpy.data.objects[binding['proxy']];pins=np.array([x.value>.99 for x in proxy.data.attributes['HairRootPin'].data])
 orientation.append(dict(bone=name,triangle_frame_to_bone_rotation_difference_degrees=float(np.degrees(actual.rotation_difference(expected).angle)),y_axis_difference_degrees=float(np.degrees((actual@y).angle(expected@y))),z_axis_difference_degrees=float(np.degrees((actual@z).angle(expected@z))),tracking_triangle_pinned_vertices=int(pins[binding['triangle']].sum())))
report['surface_frame_vs_bone_orientation']=orientation
(run/'pin_contact_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
