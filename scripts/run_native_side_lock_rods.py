"""Stock Hair Dynamics on the two cheek locks, native bone bake for display.

Static centerline fitting and a stock Shrinkwrap prepare the guides. Dynamics,
rod rotations and edge contacts are exclusively the bundled Blender asset.
The adapter transfers those rigid frames to existing bones, without contact
correction, motion filtering, weight edits or manual per-frame animation.
"""
import argparse,json,sys,time,shutil,traceback
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Matrix,Vector,Quaternion
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.native_hair_curves import attach_curve_dynamics,curve_positions_world
from animation_contact_tools.closed_collider_field import ClosedColliderField
from animation_contact_tools.hair_contact_threshold import embedded_patch_metrics
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--last',type=int,default=450);p.add_argument('--contact-limit-cm',type=float,default=5.);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
assert a.contact_limit_cm>0;contact_limit=a.contact_limit_cm/100.
base=repo.parent/'work/headswap_xl_codex';source=base/'normal_preview15_20261101/完整角色_现有最佳流程_15秒预览.blend';started=time.monotonic()
def status(stage,**kw):
 row=dict(stage=stage,elapsed_s=time.monotonic()-started,**kw);tmp=out/'status.tmp.json';tmp.write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8');tmp.replace(out/'status.json');print('NATIVE_SIDE_RODS',json.dumps(row,ensure_ascii=False),flush=True)
try:
 assert not (out/'result.json').exists(),'Use a fresh run directory'
 engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 s=bpy.context.scene;s.frame_start=1;s.frame_end=a.last;s.use_preview_range=False;s.render.fps=30;s.render.fps_base=1.;s.tool_settings.use_keyframe_insert_auto=False
 if s.rigidbody_world:s.rigidbody_world.enabled=False
 actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature()
 data=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'))
 chains=[c for c in meta['chains'] if c['name'] in ['Sidehair1.L','Sidehair1.R']];assert len(chains)==2
 names={n for c in chains for n in c['bones']};targetids=data['ids'][np.isin(data['chain_labels'],[23,24])]
 exp=base/'fullhair_repro_20261030/input_body_aware';skinids=np.load(exp/'skin_ids.npy');bodyfaces=np.load(exp/'body_faces.npy');expectedbody=np.load(exp/'body.npy',mmap_mode='r')
 # Preserve body, all other hair, and the original completed bake.
 old=arm.animation_data.action;old.use_fake_user=True;arm.animation_data.action=old.copy();action=arm.animation_data.action;action.name='NativeHairDynamics_两侧短发_原生物理骨骼烘焙'
 for layer in action.layers:
  for strip in layer.strips:
   for bag in getattr(strip,'channelbags',[]):
    for fc in list(bag.fcurves):
     if any(fc.data_path.startswith('pose.bones['+json.dumps(n)+']') for n in names):bag.fcurves.remove(fc)
 for name in names:
  b=arm.pose.bones[name];b.location=(0,0,0);b.rotation_mode='QUATERNION';b.rotation_quaternion=(1,0,0,0);b.scale=(1,1,1)
  for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(data_path=prop,frame=1,group=name)
 s.frame_set(1);bpy.context.view_layer.update();initial=coords(actor);body0=np.asarray(expectedbody[0],float)
 restmat={n:(arm.matrix_world@arm.pose.bones[n].matrix).copy() for n in names}
 # Closed actual-body topology, with stock BMesh outward normal recalculation.
 bm=bmesh.new();[bm.verts.new(co) for co in body0];bm.verts.ensure_lookup_table()
 for f in bodyfaces:bm.faces.new([bm.verts[int(i)] for i in f])
 bm.verts.index_update();bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));oriented=[tuple(v.index for v in face.verts) for face in bm.faces];bm.free()
 mesh=bpy.data.meshes.new('NativeRods_ClosedActualBody');mesh.from_pydata(body0.tolist(),[],oriented);mesh.update()
 collider=bpy.data.objects.new('NativeRods_ClosedActualBody',mesh);s.collection.objects.link(collider);collider.hide_render=True
 originalcollider=next(ob for ob in bpy.data.objects if any(md.type=='MESH_CACHE' and Path(bpy.path.abspath(md.filepath)).name=='animated_body_collider.pc2' for md in ob.modifiers))
 originalmd=next(md for md in originalcollider.modifiers if md.type=='MESH_CACHE');cache=out/'cache';cache.mkdir(exist_ok=True)
 for ob in bpy.data.objects:
  for md in ob.modifiers:
   if md.type=='MESH_CACHE':
    src=Path(bpy.path.abspath(md.filepath));dest=cache/src.name
    if not dest.exists():shutil.copy2(src,dest)
    md.filepath=str(dest)
 md=collider.modifiers.new('ActualAnimatedBody_120Hz','MESH_CACHE');md.cache_format='PC2';md.filepath=originalmd.filepath;md.play_mode='CUSTOM';md.time_mode='FRAME';md.driver_add('eval_frame').driver.expression='(frame-1)*4'
 for f in [1,226,376,450]:
  s.frame_set(f);bpy.context.view_layer.update();assert np.max(np.abs(coords(collider)-expectedbody[(f-1)*8]))<5e-6,('body cache time',f)
 s.frame_set(1);bpy.context.view_layer.update()
 # Fit guides to cross-section centres of the actual resting locks. The old
 # bone pivots do not necessarily sit in the centre of the rendered hair.
 guides=[];indices={};rootnormals=[];guide_rows=[];offset=0;subdivide=3
 for c in chains:
  raw=np.array([arm.matrix_world@arm.pose.bones[n].head for n in c['bones']]+[arm.matrix_world@arm.pose.bones[c['bones'][-1]].tail])
  ci=next(i for i,row in enumerate(meta['chains']) if row['name']==c['name']);points=initial[data['ids'][data['chain_labels']==ci]]
  seg=raw[1:]-raw[:-1];all_t=np.clip(np.sum((points[:,None]-raw[None,:-1])*seg[None],axis=2)/np.maximum((seg*seg).sum(1),1e-14),0,1)
  closest=raw[None,:-1]+all_t[:,:,None]*seg[None];which=np.argmin(np.linalg.norm(points[:,None]-closest,axis=2),axis=1)
  length=np.linalg.norm(seg,axis=1);arc=np.r_[0,np.cumsum(length)];parameter=arc[which]+all_t[np.arange(len(points)),which]*length[which]
  delta=points-closest[np.arange(len(points)),which];fitted=[]
  for j in range(len(raw)):
   sigma=max(.005,float(np.median(length))*.65);w=np.exp(-.5*((parameter-arc[j])/sigma)**2)
   displacement=(delta*w[:,None]).sum(0)/max(w.sum(),1e-10)
   tangent=seg[min(j,len(seg)-1)];tangent=tangent/max(np.linalg.norm(tangent),1e-12);displacement-=tangent*np.dot(displacement,tangent)
   fitted.append(raw[j]+displacement)
  fitted=np.array(fitted);dense=np.concatenate([np.linspace(fitted[j],fitted[j+1],subdivide,endpoint=False) for j in range(len(fitted)-1)]+[fitted[-1:]])
  guides.append(dense);indices.update({n:offset+i*subdivide for i,n in enumerate(c['bones'])});offset+=len(dense)
  guide_rows.append(dict(chain=c['name'],points=len(dense),maximum_static_centre_fit_m=float(np.linalg.norm(fitted-raw,axis=1).max())))
 lengths=[len(g) for g in guides];guide=np.concatenate(guides)
 # One-time native Outside projection prepares collision-legal guide centres.
 gm=bpy.data.meshes.new('GuidePreparation');gm.from_pydata(guide.tolist(),[],[]);go=bpy.data.objects.new('GuidePreparation',gm);s.collection.objects.link(go)
 sw=go.modifiers.new('StaticGuideOutside_OnlyBeforePhysics','SHRINKWRAP');sw.target=collider;sw.wrap_method='NEAREST_SURFACEPOINT';sw.wrap_mode='OUTSIDE';sw.offset=.010
 projected=coords(go);bpy.data.objects.remove(go,do_unlink=True);guide=projected
 # Tiny UV attachment patches follow the existing head transform. They are
 # attachments only, not collision surfaces; the closed body handles contact.
 vertices=[];quads=[];uvs=[];cursor=0
 for i,n in enumerate(lengths):
  root=guide[cursor];t=guide[cursor+1]-root;t/=np.linalg.norm(t);axis=np.eye(3)[np.argmin(np.abs(t))];u=np.cross(t,axis);u/=np.linalg.norm(u);v=np.cross(t,u)
  rootnormals.append(t.tolist());k=len(vertices);vertices.extend([(root+dx*u*.002+dy*v*.002).tolist() for dx,dy in [(-1,-1),(1,-1),(1,1),(-1,1)]]);quads.append((k,k+1,k+2,k+3));uvs.append([(i,0),(i+1,0),(i+1,1),(i,1)]);cursor+=n
 sm=bpy.data.meshes.new('NativeRods_AttachmentUV');sm.from_pydata(vertices,[],quads);sm.uv_layers.new(name='UVMap')
 for poly,uv in zip(sm.polygons,uvs):
  for li,value in zip(poly.loop_indices,uv):sm.uv_layers.active.data[li].uv=value
 scalp=bpy.data.objects.new('NativeRods_HeadAttachments',sm);s.collection.objects.link(scalp);scalp.hide_render=True
 constraint=scalp.constraints.new('CHILD_OF');constraint.target=arm;constraint.subtarget='頭';constraint.inverse_matrix=(arm.matrix_world@arm.pose.bones['頭'].matrix).inverted()
 bpy.ops.object.select_all(action='DESELECT');scalp.select_set(True);bpy.context.view_layer.objects.active=scalp
 bpy.ops.object.curves_empty_hair_add();hair=bpy.context.object;hair.name='NativeRods_TwoCheekLocks';hair.parent=None;hair.matrix_world=Matrix.Identity(4);hair.hide_render=True
 for md in list(hair.modifiers):hair.modifiers.remove(md)
 hair.data.surface=scalp;hair.data.surface_uv_map='UVMap';hair.data.add_curves(lengths);hair.data.points.foreach_set('position',np.asarray(guide,np.float32).ravel());hair.data.set_types(type='POLY')
 ra=hair.data.attributes.get('radius') or hair.data.attributes.new('radius','FLOAT','POINT');ra.data.foreach_set('value',np.full(len(guide),.006,np.float32))
 uv=hair.data.attributes.get('surface_uv_coordinate') or hair.data.attributes.new('surface_uv_coordinate','FLOAT2','CURVE');uv.data.foreach_set('vector',np.asarray([(i+.5,.5) for i in range(len(lengths))],np.float32).ravel());hair.data.update_tag()
 modifier,metadata=attach_curve_dynamics(hair,[collider],substeps=60,iterations=120,gravity=False,bendiness=.15,root_bendiness=.05,collision_margin=.003)
 dyn=next(n for n in modifier.node_group.nodes if n.type=='GROUP' and n.node_tree.name.startswith('Hair Dynamics'))
 switches=[sock for sock in dyn.inputs if sock.type=='BOOLEAN' and 'Surface' in sock.name and 'Collision' in sock.name]
 assert switches,[(sock.name,sock.type) for sock in dyn.inputs]
 for sock in switches:sock.default_value=False
 for sock in dyn.inputs:
  if sock.name=='Linear Damping':sock.default_value=5.
  if sock.name=='Angular Damping':sock.default_value=2.
 for bake in modifier.bakes:bake.use_custom_simulation_frame_range=True;bake.frame_start=1;bake.frame_end=a.last
 for im in bpy.data.images:
  if im.filepath and im.source in {'FILE','MOVIE','SEQUENCE','TILED'}:im.filepath=bpy.path.abspath(im.filepath)
 setup=dict(source=str(source),backend=metadata,unchanged_hair_bones='all except Sidehair1..7.L/R',guides=guide_rows,guide_projection='Stock Blender Shrinkwrap Outside, rest preparation only',mapping='Native XPBD point quaternion delta applied to original rest bone frames; native Armature original weights',original_weights_edited=False,per_frame_contact_or_motion_filter=False,body_and_hug_256_321_preserved=True,physical_radius_m=.006,frames_planned=[1,a.last],native_surface_collision=False,external_closed_actual_body_collision=True,render_or_video_started=False,shutdown_forbidden=True,contact_policy=dict(limit_cm=a.contact_limit_cm,trigger='Either deepest penetration or maximum spatial extent of a connected embedded hair patch exceeds limit',below_limit='Record and continue',measurement_scope='All 24207 displayed hair vertices / all 27 chains, every source frame'))
 (out/'setup.json').write_text(json.dumps(setup,ensure_ascii=False,indent=2),'utf8')
 s.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'完整角色_原生侧发配置_未验收.blend'))
 rows=[];motion=[];rotations=[];stopped=None;restco=None;restq=None;previousq={}
 selected=[b.name for b in arm.pose.bones if b.name in names]
 originalcurves=sum(len(bag.fcurves) for layer in old.layers for strip in layer.strips for bag in getattr(strip,'channelbags',[]))
 for f in range(1,a.last+1):
  s.frame_set(f);bpy.context.view_layer.update();current=curve_positions_world(hair)
  ev=hair.evaluated_get(bpy.context.evaluated_depsgraph_get());rawq=np.empty(len(current)*4,np.float32);ev.data.attributes['rotation'].data.foreach_get('value',rawq);q=rawq.reshape(-1,4)
  if restco is None:restco=current.copy();restq=q.copy()
  desired={};arm_inv=arm.matrix_world.inverted()
  for name in selected:
   i=indices[name];delta=Quaternion(q[i].tolist())@Quaternion(restq[i].tolist()).inverted();mat=delta.to_matrix().to_4x4()@restmat[name]
   mat.translation=Vector(current[i])+delta@(restmat[name].translation-Vector(restco[i]));desired[name]=arm_inv@mat
  for name in selected:
   pb=arm.pose.bones[name];kw=dict(parent_matrix=desired.get(pb.parent.name,pb.parent.matrix),parent_matrix_local=pb.parent.bone.matrix_local) if pb.parent else {}
   pb.matrix_basis=pb.bone.convert_local_to_pose(desired[name],pb.bone.matrix_local,invert=True,**kw)
   if name in previousq and pb.rotation_quaternion.dot(previousq[name])<0:pb.rotation_quaternion.negate()
   previousq[name]=pb.rotation_quaternion.copy()
   for prop in ['location','rotation_quaternion','scale']:pb.keyframe_insert(data_path=prop,frame=f,group=name)
  bpy.context.view_layer.update();motion.append(current.copy());rotations.append(q.copy())
  if True:
   actual=coords(actor);body_error=float(np.max(np.abs(actual[skinids]-expectedbody[(f-1)*8])))
   assert body_error<5e-6,('body changed',f,body_error)
   field=ClosedColliderField(actual[skinids],bodyfaces);dist,_=field(actual[data['ids']]);contact=embedded_patch_metrics(actual[data['ids']],dist,data['edges'],limit_m=contact_limit)
   worst=contact['patches'][0] if contact['patches'] else None
   row=dict(frame=f,maximum_actual_hair_depth_m=contact['maximum_depth_m'],maximum_connected_embedded_extent_m=contact['maximum_patch_extent_m'],inside_display_vertices=contact['inside_vertices'],connected_embedded_patches=contact['connected_inside_patches'],exceeds_user_5cm_limit=contact['exceeds_limit'],body_preservation_error_m=body_error);rows.append(row)
   if f==1 or f%15==1 or f in [226,376,450] or contact['exceeds_limit']:status('NATIVE_PHYSICS_WITH_USER_CONTACT_LIMIT',**row)
   if f==1:assert np.max(np.abs(actual-initial))<5e-6,'Frame adapter changed the static display'
   if contact['exceeds_limit']:
    stopped=dict(reason='Connected embedded display-hair extent or inward depth exceeds the user limit.',limit_m=contact_limit,worst_patch=worst,**row);break
  elif f%15==0:status('NATIVE_PHYSICS_RUNNING',frame=f)
 # Baking is a direct physics transfer, with linear keys and no filtering.
 for layer in action.layers:
  for strip in layer.strips:
   for bag in getattr(strip,'channelbags',[]):
    for fc in bag.fcurves:
     if any(fc.data_path.startswith('pose.bones['+json.dumps(n)+']') for n in names):
      for key in fc.keyframe_points:key.interpolation='LINEAR'
 modifier.show_viewport=False;modifier.show_render=False;s.frame_end=f;s['NativeSidehairPhysicalFrames']=f;s['ShutdownForbidden']=True;s['ReviewAllHairCollisionSolved']=False;s['UserHairContactLimitCM']=a.contact_limit_cm
 blend=out/'完整角色_原生侧发物理_待复查.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
 np.savez_compressed(out/'native_rod_physics.npz',coordinates=np.asarray(motion,np.float32),rotations=np.asarray(rotations,np.float32),rest=guide,curve_point_counts=lengths)
 report=dict(status='STOPPED_USER_CONTACT_LIMIT_EXCEEDED' if stopped else 'NATIVE_SIDE_LOCKS_BAKED_WITHIN_USER_CONTACT_LIMIT',blend=str(blend),frames=[1,f],stop=stopped,samples=rows,all_hair_collision_solved=False,user_contact_limit_cm=a.contact_limit_cm,physical_backend=metadata,original_completed_action_preserved=old.name,physical_curve_object=hair.name,original_action_curve_count=originalcurves,render_or_video_created=False)
 (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');status(report['status'],frame=f,stop=stopped,blend=str(blend))
except BaseException as exc:status('SCRIPT_INTERFACE_OR_SETUP_ERROR',error=repr(exc),traceback=traceback.format_exc());raise
