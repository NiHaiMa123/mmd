"""Read-only gravity/pin/transfer audit on the delivered native hair cache."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--physics',required=True);p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run=Path(a.physics);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
r=json.loads((run/'result.json').read_text('utf8'));setup=json.loads((run/'setup.json').read_text('utf8'));prepared=json.loads((Path(setup['prepared']).parent/'setup.json').read_text('utf8'))
base=repo.parent/'work/headswap_xl_codex';d=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'))
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=r['blend'],load_ui=False,use_scripts=False)
s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();s.frame_set(1);bpy.context.view_layer.update();initial=coords(actor)
report=dict(source=r['blend'],read_only=True,scene_gravity=list(s.gravity),scene_use_gravity=s.use_gravity,source_fps=s.render.fps,fps_base=s.render.fps_base,unit_scale=s.unit_settings.scale_length,scene_time_scale=s.rigidbody_world.time_scale if s.rigidbody_world else None,field_objects=[],chains=[],frames=[])
for ob in bpy.data.objects:
 if ob.field and ob.field.type!='NONE':
  report['field_objects'].append(dict(name=ob.name,type=ob.field.type,strength=ob.field.strength,hide_viewport=ob.hide_viewport,world_matrix=[list(q) for q in ob.matrix_world]))
rests={};masks={};tips={};rootpos={}
gn={q.index:q.name for q in actor.vertex_groups};bn=set(arm.pose.bones.keys())
for label,row in enumerate(prepared['proxies']):
 proxy=bpy.data.objects[row['proxy']];q=coords(proxy);rests[label]=q;pins=np.array([x.value>.99 for x in proxy.data.attributes['HairRootPin'].data]);masks[label]=pins
 ids=d['ids'][d['chain_labels']==label];root=np.array(arm.matrix_world@arm.pose.bones[meta['chains'][label]['bones'][0]].head);rootpos[label]=root
 radius=np.linalg.norm(initial[ids]-root,axis=1);tip=ids[radius>=np.quantile(radius,.8)];tips[label]=tip
 md=next(m for m in proxy.modifiers if m.type=='CLOTH');cs=md.settings
 weights=[]
 for i in tip:
  ws={gn[g.group]:g.weight for g in actor.data.vertices[int(i)].groups if gn.get(g.group) in bn};total=sum(ws.values());weights.append(ws.get('頭',0)/total if total else 0.)
 axis=np.array(arm.matrix_world@arm.pose.bones[meta['chains'][label]['bones'][0]].tail)-root
 pin_radius=np.linalg.norm(q[pins]-root,axis=1)
 proxy_radius=np.linalg.norm(q-root,axis=1);proxy_tip=(proxy_radius>=np.quantile(proxy_radius,.8))&~pins
 bones=[]
 for name in meta['chains'][label]['bones']:
  b=arm.pose.bones[name];con=[c for c in b.constraints if c.name.startswith('ClassicCloth_跟踪代理_')]
  bones.append(dict(name=name,head=list(b.head),tail=list(b.tail),length=b.length,location=list(b.location),scale=list(b.scale),tracks=[dict(type=c.type,influence=c.influence,target=c.target.name if c.target else None) for c in con]))
 report['chains'].append(dict(label=label,name=row['chain'],proxy_vertices=len(q),pinned=int(pins.sum()),free=int((~pins).sum()),pinned_fraction=float(pins.mean()),pin_furthest_distance_from_root_m=float(pin_radius.max()),strand_furthest_distance_from_root_m=float(proxy_radius.max()),pin_in_furthest_20_percent=int((pins&(proxy_radius>=np.quantile(proxy_radius,.8))).sum()),tip_head_weight_mean=float(np.mean(weights)),tip_head_weight_max=float(max(weights)),cloth=dict(gravity_weight=cs.effector_weights.gravity,all_force_weight=cs.effector_weights.all,time_scale=cs.time_scale,use_dynamic_mesh=cs.use_dynamic_mesh,shrink_min=cs.shrink_min,mass=cs.mass,air_damping=cs.air_damping,bending_stiffness=cs.bending_stiffness,tension_stiffness=cs.tension_stiffness,tension_damping=cs.tension_damping,compression_damping=cs.compression_damping,shear_damping=cs.shear_damping,bending_damping=cs.bending_damping,pin_group=cs.vertex_group_mass,effector_collection=cs.effector_weights.collection.name if cs.effector_weights.collection else None,wind_weight=cs.effector_weights.wind),bones=bones,proxy_tip_mask=proxy_tip.tolist()))
for f in [1,31,61,91,151,226,331,376,451,526]:
 s.frame_set(f);bpy.context.view_layer.update();co=coords(actor);delta=np.array(bpy.data.objects['ClassicHair_HeadMotion'].evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world);chains=[]
 for label,row in enumerate(prepared['proxies']):
  proxy=bpy.data.objects[row['proxy']];q=coords(proxy);rigid=rests[label]@delta[:3,:3].T+delta[:3,3];res=q-rigid;free=~masks[label];proxy_tip=np.array(report['chains'][label]['proxy_tip_mask'])
  tip=tips[label];display=co[tip]-(initial[tip]@delta[:3,:3].T+delta[:3,3])
  chains.append(dict(name=row['chain'],proxy_free_mean_vertical_from_rigid_cm=float(res[free,2].mean()*100) if free.any() else 0,proxy_free_rms_from_rigid_cm=float(np.sqrt((res[free]**2).sum(1).mean())*100) if free.any() else 0,proxy_tip_mean_vertical_from_rigid_cm=float(res[proxy_tip,2].mean()*100) if proxy_tip.any() else 0,display_tip_mean_vertical_from_rigid_cm=float(display[:,2].mean()*100),display_tip_rms_from_rigid_cm=float(np.sqrt((display**2).sum(1).mean())*100)))
 report['frames'].append(dict(frame=f,seconds=(f-1)/30,chains=chains))
for row in report['chains']:row.pop('proxy_tip_mask')
(out/'rear_gravity_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print('REAR_GRAVITY_AUDIT',json.dumps(dict(scene_gravity=report['scene_gravity'],scene_use_gravity=report['scene_use_gravity'],field_objects=report['field_objects'],frames_checked=[q['frame'] for q in report['frames']],output=str(out/'rear_gravity_audit.json')),ensure_ascii=False),flush=True)
