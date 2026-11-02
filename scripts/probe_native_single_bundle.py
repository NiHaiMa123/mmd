"""One actual Sidetail bundle, native curve dynamics, untouched source animation."""
import sys,json,time,argparse
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords,audit_frame
from animation_contact_tools.native_hair_curves import attach_curve_dynamics,curve_positions_world
from animation_contact_tools.native_hair_surface import new_tree,named,integer_compare
from animation_contact_tools.strand_binding import bind_vertices,deform_vertices,conservative_radii,bind_rod_vertices,deform_rod_vertices
from animation_contact_tools.hair_bundle_profile import resolve_bundle
p=argparse.ArgumentParser();p.add_argument('--tag',default='single_bundle_R');p.add_argument('--source');p.add_argument('--bundle-profile');p.add_argument('--initial-surface-project',action='store_true');p.add_argument('--out');p.add_argument('--first',type=int,default=1);p.add_argument('--last',type=int,default=250);p.add_argument('--substeps',type=int,default=60);p.add_argument('--iterations',type=int,default=200);p.add_argument('--no-collision',action='store_true');p.add_argument('--no-gravity',action='store_true');p.add_argument('--mesh-guide',action='store_true');p.add_argument('--body-proxies',action='store_true');p.add_argument('--skin-cage',action='store_true');p.add_argument('--cage-rest-pose',action='store_true');p.add_argument('--split-cage',action='store_true');p.add_argument('--voxel-size',type=float,default=.006);p.add_argument('--contact-margin',type=float,default=.001);p.add_argument('--bendiness',type=float,default=.25);p.add_argument('--root-bendiness',type=float,default=.2);p.add_argument('--rod-frames',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=Path(a.out).resolve() if a.out else base/'hair_curves_20261028'/a.tag;out.mkdir(parents=True,exist_ok=True)
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.source).resolve() if a.source else base/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False)
bundle_config=json.loads(Path(a.bundle_profile).read_text('utf8')) if a.bundle_profile else None;rig_profile_path=Path(bundle_config.get('source_profile',str(base/'body_track/rig_profile.json'))) if bundle_config else base/'body_track/rig_profile.json';profile=json.loads(rig_profile_path.read_text('utf8'));mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(mesh,arm,profile);scene=bpy.context.scene;scene.frame_start=a.first;scene.frame_end=a.last;scene.frame_set(a.first);bpy.context.view_layer.update();source=coords(mesh)
if bundle_config is None:
 topology=np.load(base/'hair_tests_v2/hair_topology.npz');bundle_config={'schema':1,'component':4,'vertex_ids':topology['ids'][topology['component']==4].tolist(),'guide_bones':[f'Sidetail{i}.R' for i in range(1,7)],'anchor_bone':'頭'}
bundle=resolve_bundle(mesh,arm,parts,bundle_config);ids=bundle['ids'];bundle_set=set(ids.tolist());bundlefaces=bundle['faces'];bundlepolys=bundle['polygons'];anchor=bundle['anchor_bone'];original_rest=source[ids].copy();chain=bundle['guide_bones'];path=np.array([arm.matrix_world@chain[0].head]+[arm.matrix_world@b.tail for b in chain]);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(path,axis=0),axis=1))];samples=np.linspace(0,arc[-1],41);guide=np.stack([np.interp(samples,arc,path[:,i]) for i in range(3)],axis=1)
if a.mesh_guide:
 # Replace bone-centred cross-sections by the actual bundle's geometric
 # centres. Bone pivots can extend into the scalp while visible hair does not.
 rough=guide.copy();dist=np.linalg.norm(source[ids,None,:]-rough[None,:,:],axis=2);bins=np.argmin(dist,axis=1);occupied=sorted(set(bins.tolist()));centres=np.array([source[ids][bins==i].mean(0) for i in occupied]);guide=np.stack([np.interp(np.arange(len(guide)),occupied,centres[:,i]) for i in range(3)],axis=1)
 # Gentle longitudinal smoothing, retaining exact end cross-sections.
 for _ in range(4):guide[1:-1]=(guide[:-2]+2*guide[1:-1]+guide[2:])*.25
initial_projection=None
if a.initial_surface_project:
 from animation_contact_tools.exact_skin_collider import build_exact_skin_topology
 from animation_contact_tools.closed_collider_field import ClosedColliderField
 from animation_contact_tools.surface_contact_projection import project_surface
 tangent0=guide[1]-guide[0];tangent0/=np.linalg.norm(tangent0);normal0=np.eye(3)[np.argmin(np.abs(tangent0))];normal0-=tangent0*np.dot(normal0,tangent0);normal0/=np.linalg.norm(normal0);initial_binding=bind_vertices(original_rest,guide,normal0);pinned=bundle['root_pin_mask'] if bundle['root_pin_mask'] is not None else initial_binding['segment']<bundle_config.get('root_guide_segments',2);lookup0={int(v):i for i,v in enumerate(ids)};edges0=np.array([(lookup0[e.vertices[0]],lookup0[e.vertices[1]]) for e in mesh.data.edges if all(v in bundle_set for v in e.vertices)]);triangles0=np.array([[lookup0[i] for i in f] for f in bundlefaces]);skin_ids,skin_faces,skin_meta=build_exact_skin_topology(mesh,arm,profile);field=ClosedColliderField(source[skin_ids],skin_faces);fixed,detail=project_surface(original_rest,original_rest,edges0,triangles0,pinned,field,margin=.006,iterations=240,target_strength=.002);source[ids]=fixed;initial_audit=audit_frame(mesh,arm,dict(profile,pairs=[]),bundle['parts'],hair=True,cap=1000000,coordinates_m=source);initial_projection={'triangle_crossings':initial_audit['ordinary_crossings'],'root_pin_count':int(pinned.sum()),'metrics':detail,'skin':skin_meta};(out/'initial_projection.json').write_text(json.dumps(initial_projection,ensure_ascii=False,indent=2),encoding='utf8');np.savez_compressed(out/'initial_projection.npz',ids=ids,coordinates=fixed,original=original_rest,pinned=pinned);print('SINGLE_BUNDLE_INITIAL_PROJECT',json.dumps(initial_projection),flush=True)
 if initial_audit['ordinary_crossings'] or detail['min_edge_ratio']<.9 or detail['max_edge_ratio']>1.1:raise RuntimeError('Unable to construct a legal initial hair surface without moving roots/body')
 dist=np.linalg.norm(source[ids,None,:]-guide[None,:,:],axis=2);bins=np.argmin(dist,axis=1);occupied=sorted(set(bins.tolist()));centres=np.array([source[ids][bins==i].mean(0) for i in occupied]);guide=np.stack([np.interp(np.arange(len(guide)),occupied,centres[:,i]) for i in range(3)],axis=1)
 for _ in range(4):guide[1:-1]=(guide[:-2]+2*guide[1:-1]+guide[2:])*.25
tangent=guide[1]-guide[0];tangent/=np.linalg.norm(tangent);axis=np.eye(3)[np.argmin(np.abs(tangent))];normal=axis-tangent*np.dot(axis,tangent);normal/=np.linalg.norm(normal);binormal=np.cross(tangent,normal)
binding=bind_vertices(source[ids],guide,normal);radii=conservative_radii(binding,len(guide));rest_error=float(np.max(np.abs(deform_vertices(binding,guide,normal)-source[ids])));assert rest_error<1e-8
head0=arm.matrix_world@arm.pose.bones[anchor].matrix.copy();initial=Matrix.Identity(4)
# Local X/Y span the root plane; local Z is the strand's rest tangent.
for k,v in enumerate((normal,binormal,tangent)):
 for j in range(3):initial[j][k]=float(v[j])
initial.translation=Vector(guide[0])
bpy.ops.object.select_all(action='DESELECT');bpy.ops.mesh.primitive_plane_add(size=.08);scalp=bpy.context.object;scalp.name='SingleBundle_HeadAttachment';scalp.matrix_world=initial
bpy.ops.object.curves_empty_hair_add();hair=bpy.context.object;hair.name='SingleBundle_RodGuide'
for mod in list(hair.modifiers):hair.modifiers.remove(mod)
hair.data.add_curves([len(guide)]);inv=np.asarray(hair.matrix_world.inverted());local=guide@inv[:3,:3].T+inv[:3,3];hair.data.points.foreach_set('position',local.astype(np.float32).ravel());hair.data.set_types(type='POLY')
rad=hair.data.attributes.get('radius') or hair.data.attributes.new('radius','FLOAT','POINT');rad.data.foreach_set('value',radii.astype(np.float32));uv=hair.data.attributes.get('surface_uv_coordinate') or hair.data.attributes.new('surface_uv_coordinate','FLOAT2','CURVE');uv.data.foreach_set('vector',[.5,.5]);hair.data.update_tag()
head_deltas=[]
proxies=[]
if a.body_proxies:
 attr=mesh.data.attributes[profile['surface_attribute']];skinids={i for f in mesh.data.polygons if attr.data[f.index].value in (1,2) for i in f.vertices};names={mesh.vertex_groups[g.group].name for i in skinids for g in mesh.data.vertices[i].groups if g.weight>.01}
 for obj in list(scene.objects):
  if getattr(obj,'mmd_type','')=='RIGID_BODY' and obj.mmd_rigid.bone in names:
   copy=bpy.data.objects.new('SingleBundle_Proxy_'+obj.name,obj.data.copy());scene.collection.objects.link(copy);copy.hide_render=True;copy.hide_set(True);proxies.append((copy,obj.mmd_rigid.bone,obj.matrix_world.copy()))
for frame in range(a.first,a.last+1):
 scene.frame_set(frame);bpy.context.view_layer.update();delta=(arm.matrix_world@arm.pose.bones[anchor].matrix)@head0.inverted();head_deltas.append(np.array(delta));scalp.matrix_world=delta@initial;scalp.rotation_mode='QUATERNION';scalp.keyframe_insert('location',frame=frame);scalp.keyframe_insert('rotation_quaternion',frame=frame);scalp.keyframe_insert('scale',frame=frame)
 for obj,name,restmatrix in proxies:
  obj.matrix_world=arm.matrix_world@arm.pose.bones[name].matrix@arm.data.bones[name].matrix_local.inverted()@arm.matrix_world.inverted()@restmatrix;obj.rotation_mode='QUATERNION';obj.keyframe_insert('location',frame=frame);obj.keyframe_insert('rotation_quaternion',frame=frame);obj.keyframe_insert('scale',frame=frame)
scene.frame_set(a.first);bpy.context.view_layer.update()
# Independent source copy: the simulator never reads its own mapped hair.
collider=mesh.copy();collider.name='SingleBundle_AnimatedSkinReference';scene.collection.objects.link(collider);collider.hide_render=True;collider.hide_set(True)
tree,inp,output=new_tree('SingleBundle_OnlyBodyAndHead');links=tree.links;cls=named(tree,profile['surface_attribute'],'INT');a1=integer_compare(tree,links,cls,'EQUAL',1);a2=integer_compare(tree,links,cls,'EQUAL',2);join=tree.nodes.new('FunctionNodeBooleanMath');join.operation='OR';links.new(a1,join.inputs[0]);links.new(a2,join.inputs[1]);separate=tree.nodes.new('GeometryNodeSeparateGeometry');separate.domain='FACE';links.new(inp.outputs['Geometry'],separate.inputs['Geometry']);links.new(join.outputs[0],separate.inputs['Selection']);links.new(separate.outputs['Selection'],output.inputs['Geometry']);cm=collider.modifiers.new('Actual animated skin only','NODES');cm.node_group=tree
cage_info=None
if a.skin_cage:
 from animation_contact_tools.skin_collision_cage import build_skin_cage
 collider,cage_info=build_skin_cage(mesh,arm,profile,voxel_size=a.voxel_size,binding_pose='REST' if a.cage_rest_pose else 'CURRENT')
 print('SINGLE_BUNDLE_SKIN_CAGE',json.dumps(cage_info),flush=True)
ev=collider.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();world_body=[collider.matrix_world@v.co for v in me.vertices];body_tree=BVHTree.FromPolygons(world_body,[tuple(f.vertices) for f in me.polygons]);ev.to_mesh_clear();initial_clearances=[]
for i,point in enumerate(guide):
 q,n,fi,d=body_tree.find_nearest(Vector(point));initial_clearances.append({'point':i,'signed_distance_m':float((Vector(point)-q).dot(n)),'radius_m':float(radii[i]),'surface_distance_m':float(d),'conservative_clearance_m':float((Vector(point)-q).dot(n)-radii[i])})
print('SINGLE_BUNDLE_INITIAL_CLEARANCE',json.dumps(initial_clearances),flush=True)
physical_colliders=[collider]
if a.split_cage:
 if not a.skin_cage or not a.cage_rest_pose:raise ValueError('Closed anatomical splitting requires --skin-cage --cage-rest-pose')
 from animation_contact_tools.anatomical_colliders import split_rest_cage
 physical_colliders,split_info=split_rest_cage(mesh,arm,collider,profile,parts);cage_info['anatomical_parts']=split_info
modifier,metadata=attach_curve_dynamics(hair,[] if a.no_collision else [p[0] for p in proxies] if a.body_proxies else physical_colliders,substeps=a.substeps,iterations=a.iterations,gravity=not a.no_gravity,bendiness=a.bendiness,root_bendiness=a.root_bendiness,collision_margin=a.contact_margin)
if cage_info:metadata['skin_cage']=cage_info
for bake in modifier.bakes:bake.use_custom_simulation_frame_range=True;bake.frame_start=a.first;bake.frame_end=a.last
(out/'setup.json').write_text(json.dumps({'metadata':metadata,'rest_error_m':rest_error,'radii':radii.tolist(),'guide':guide.tolist(),'initial_clearances':initial_clearances,'mesh_derived_guide':a.mesh_guide},ensure_ascii=False,indent=2),encoding='utf8')
bundleparts={k:dict(v) if isinstance(v,dict) else v for k,v in parts.items()}
for key in ('faces','ids','source_faces','samples','closed'):
 for name in ('hair_root','hair_mobile'):bundleparts[key].pop(name,None)
bundleparts['faces']['hair_mobile']=bundlefaces;bundleparts['ids']['hair_mobile']=ids.tolist();bundleparts['source_faces']['hair_mobile']=bundlepolys;bundleparts['samples']['hair_mobile']=ids[::8].tolist();bundleparts['closed']['hair_mobile']=False
lookup={int(v):i for i,v in enumerate(ids)};edges=np.array([(lookup[e.vertices[0]],lookup[e.vertices[1]]) for e in mesh.data.edges if all(v in bundle_set for v in e.vertices)]);restlength=np.linalg.norm(original_rest[edges[:,0]]-original_rest[edges[:,1]],axis=1);valid=restlength>.0005
rows=[];positions=[];raw_surface_positions=[];guideframes=[];start=time.monotonic();keys=[];profile_hair=dict(profile,pairs=[])
for frame in range(a.first,a.last+1):
 scene.frame_set(frame);bpy.context.view_layer.update();co=coords(mesh);current=curve_positions_world(hair);delta=head_deltas[frame-a.first];rootnormal=delta[:3,:3]@normal;mapped=deform_vertices(binding,current,rootnormal);result=co.copy();result[ids]=mapped;positions.append(mapped.astype(np.float32));guideframes.append(current.astype(np.float32));ratio=np.linalg.norm(mapped[edges[:,0]]-mapped[edges[:,1]],axis=1)[valid]/restlength[valid]
 if a.rod_frames:
  ev=hair.evaluated_get(bpy.context.evaluated_depsgraph_get());quaternions=np.empty(len(current)*4,dtype=np.float32);ev.data.attributes['rotation'].data.foreach_get('value',quaternions);quaternions=quaternions.reshape(-1,4).astype(float);quaternions[-1]=quaternions[-2]
  if frame==a.first:rod_binding=bind_rod_vertices(source[ids],current,quaternions,binding['segment'],binding['factor'])
  mapped=deform_rod_vertices(rod_binding,current,quaternions);result[ids]=mapped;positions[-1]=mapped.astype(np.float32);ratio=np.linalg.norm(mapped[edges[:,0]]-mapped[edges[:,1]],axis=1)[valid]/restlength[valid]
 raw_surface_positions.append(mapped.astype(np.float32));surface_root_projection=0.
 if bundle_config.get('enforce_surface_roots',False):
  if bundle['root_pin_mask'] is None:raise ValueError('Hard surface roots need an explicit root vertex selection')
  rootmask=bundle['root_pin_mask'];expected=source[ids][rootmask]@delta[:3,:3].T+delta[:3,3];surface_root_projection=float(np.max(np.linalg.norm(mapped[rootmask]-expected,axis=1)));mapped[rootmask]=expected;result[ids]=mapped;positions[-1]=mapped.astype(np.float32);ratio=np.linalg.norm(mapped[edges[:,0]]-mapped[edges[:,1]],axis=1)[valid]/restlength[valid]
 guide_ratio=np.linalg.norm(np.diff(current,axis=0),axis=1)/np.linalg.norm(np.diff(guide,axis=0),axis=1)
 row={'frame':frame,'surface_root_projection_m':surface_root_projection,'root_error_m':float(np.linalg.norm(current[0]-(delta[:3,:3]@guide[0]+delta[:3,3]))),'min_guide_edge_ratio':float(guide_ratio.min()),'max_guide_edge_ratio':float(guide_ratio.max()),'min_mesh_edge_ratio':float(ratio.min()),'max_mesh_edge_ratio':float(ratio.max()),'mesh_edge_ratio_p99':float(np.percentile(ratio,99))}
 if frame%10==0 or frame in (1,226,240,250):
  before=audit_frame(mesh,arm,profile_hair,bundleparts,hair=True,cap=1000000,coordinates_m=co);after=audit_frame(mesh,arm,profile_hair,bundleparts,hair=True,cap=1000000,coordinates_m=result);row['source_crossings']=before['ordinary_crossings'];row['mapped_crossings']=after['ordinary_crossings'];row['pairs']=[{'pair':r['pair'],'crossings':r['triangle_crossings']} for r in after['pairs'] if r['triangle_crossings']];print('SINGLE_BUNDLE_SAMPLE',json.dumps(row),flush=True)
 if frame in (1,10,50,100,226,240,250):np.savez_compressed(out/f'keypose{frame:04}.npz',coordinates=result);keys.append(frame)
 rows.append(row)
 if frame%25==0:
  (out/'progress.json').write_text(json.dumps({'status':'RUNNING','last_frame':frame,'samples':rows},ensure_ascii=False),encoding='utf8');np.savez_compressed(out/'motion_checkpoint.npz',coordinates=positions,guides=guideframes,ids=ids)
np.savez_compressed(out/'bundle_motion.npz',coordinates=positions,raw_coordinates=raw_surface_positions,guides=guideframes,ids=ids,rest_guide=guide,radii=radii,rest_coordinates=original_rest,binding_rest_coordinates=source[ids],head_deltas=head_deltas)
report={'status':'SINGLE_BUNDLE_UNRESOLVED','accepted':False,'source':bpy.data.filepath,'metadata':metadata,'component':bundle_config.get('component'),'anchor_bone':anchor,'bundle_profile':a.bundle_profile,'rig_profile':str(rig_profile_path),'initial_projection':initial_projection,'explicit_surface_root_projection':bool(bundle_config.get('enforce_surface_roots',False)),'max_surface_root_projection_m':max(r['surface_root_projection_m'] for r in rows),'bone_chain':[b.name for b in chain],'mapped_vertices':len(ids),'mapped_triangles':len(bundlefaces),'rest_binding_error_m':rest_error,'radius_min_m':float(radii.min()),'radius_max_m':float(radii.max()),'max_root_error_m':max(r['root_error_m'] for r in rows),'min_mesh_edge_ratio':min(r['min_mesh_edge_ratio'] for r in rows),'max_mesh_edge_ratio':max(r['max_mesh_edge_ratio'] for r in rows),'frames':[a.first,a.last],'keyposes':keys,'samples':rows,'seconds':time.monotonic()-start,'body_animation_changed':False,'whole_hair_solved':False,'self_collision_tested':False,'continuous_collision_proven':False,'zero_initial_velocity':True}
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');scene.frame_set(a.first);bpy.ops.wm.save_as_mainfile(filepath=str(out/'NativeSingleBundle_Live_NotAccepted.blend'),compress=True);print('SINGLE_BUNDLE_COMPLETE',report['seconds'],flush=True)
