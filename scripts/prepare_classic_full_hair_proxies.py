"""Prepare two branch-preserving surface proxies and native Surface Deform.

No physical solve. Original actor topology, weights, keys and source action
remain present. Only a cloned side-lock rest action and two scoped modifiers
are used. Proxy simplification uses Blender's stock Decimate modifier.
"""
import argparse,json,sys,shutil,time,traceback,numpy as np
from pathlib import Path
import bpy,bmesh
from mathutils import Matrix
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.native_hair_surface import new_tree
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--ratio',type=float,default=.4);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
base=repo.parent/'work/headswap_xl_codex';source=base/'normal_preview15_20261101/完整角色_现有最佳流程_15秒预览.blend';started=time.monotonic()
def status(stage,**kw):
 row=dict(stage=stage,elapsed_s=time.monotonic()-started,**kw);tmp=out/'status.tmp.json';tmp.write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8');tmp.replace(out/'status.json');print('SIDE_SURFACE_PREP',json.dumps(row,ensure_ascii=False),flush=True)
def component_info(mesh,pins):
 parent=np.arange(len(mesh.vertices))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=int(parent[i])
  return i
 for e in mesh.edges:parent[find(e.vertices[0])]=find(e.vertices[1])
 groups={}
 for i in range(len(parent)):groups.setdefault(find(i),[]).append(i)
 return [dict(vertices=len(v),pins=int((pins[v]>.999).sum())) for v in groups.values()]

def panel_seams(points,faces,pin):
 """Standard Cloth sewing: join nearby detached panels without new head pins."""
 parent=np.arange(len(points))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=int(parent[i])
  return i
 for face in faces:
  for i,j in zip(face,np.roll(face,1)):parent[find(int(i))]=find(int(j))
 panels={}
 for i in range(len(points)):panels.setdefault(find(i),[]).append(i)
 anchored=[v for v in panels.values() if sum(pin[i]>.99 for i in v)>=2]
 loose=[v for v in panels.values() if sum(pin[i]>.99 for i in v)<2]
 assert anchored,'No physical root region'
 targets=np.array([i for panel in anchored for i in panel],int);edges=[];records=[]
 for panel in sorted(loose,key=len,reverse=True):
  source=np.array(panel,int);dist=np.linalg.norm(points[source,None,:]-points[targets][None,:,:],axis=2)
  order=np.argsort(dist,axis=None);used_source=set();used_target=set();chosen=[]
  for ij in order:
   i,j=np.unravel_index(int(ij),dist.shape)
   if i in used_source or j in used_target:continue
   gap=float(dist[i,j])
   if gap>.01:break
   edges.append((int(source[i]),int(targets[j])));chosen.append(gap);used_source.add(i);used_target.add(j)
   if len(chosen)==3:break
  assert len(chosen)>=2,('Detached authored panel has no nearby seam',len(panel),float(dist.min()))
  records.append(dict(panel_vertices=len(panel),sewing_links=len(chosen),maximum_initial_gap_m=max(chosen)))
  targets=np.concatenate([targets,source])
 return edges,records
try:
 assert not (out/'setup.json').exists(),'Use a new candidate directory'
 engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 s=bpy.context.scene;s.frame_start=1;s.frame_end=450;s.render.fps=30;s.use_preview_range=False;s.tool_settings.use_keyframe_insert_auto=False
 if s.rigidbody_world:s.rigidbody_world.enabled=False
 actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();s.frame_set(1);bpy.context.view_layer.update()
 metadata=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8')); names={n for ch in metadata['chains'] for n in ch['bones']};old=arm.animation_data.action;old.use_fake_user=True;arm.animation_data.action=old.copy();action=arm.animation_data.action;action.name='ClassicCloth_全头静置_原身体动作保留'
 for layer in action.layers:
  for strip in layer.strips:
   for bag in getattr(strip,'channelbags',[]):
    for fc in list(bag.fcurves):
     if any(fc.data_path.startswith('pose.bones['+json.dumps(n)+']') for n in names):bag.fcurves.remove(fc)
 for name in names:
  b=arm.pose.bones[name];b.location=(0,0,0);b.rotation_mode='QUATERNION';b.rotation_quaternion=(1,0,0,0);b.scale=(1,1,1)
  for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(prop,frame=1,group=name)
 s.frame_set(1);bpy.context.view_layer.update();initial=coords(actor)
 inspection=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');rest=np.load(base/'hair_initial_repair_20261030/DELIVER_INITIAL/InitialHairRest.npz');meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'))
 basis=np.array([p.co[:] for p in actor.data.shape_keys.key_blocks[0].data]);mw=np.array(actor.matrix_world);restworld=basis@mw[:3,:3].T+mw[:3,3]
 actor.data.calc_loop_triangles();tri=np.array([t.vertices[:] for t in actor.data.loop_triangles],int);cls=actor.data.attributes['SurfaceClass'];hairfaces=tri[np.array([cls.data[t.polygon_index].value==3 for t in actor.data.loop_triangles])]
 groupnames={g.index:g.name for g in actor.vertex_groups};bonenames=set(arm.pose.bones.keys());hard=set(map(int,rest['ids'][rest['same_true_hard_root_mask']]))
 # Rigid head delta, as mesh deformation in a fixed world-space proxy object.
 delta=bpy.data.objects.new('ClassicHair_HeadMotion',None);s.collection.objects.link(delta);delta.hide_render=True
 c=delta.constraints.new('CHILD_OF');c.target=arm;c.subtarget='頭';c.inverse_matrix=(arm.matrix_world@arm.pose.bones['頭'].matrix).inverted()
 rows=[];proxies=[];bindings=[]
 for ci in range(len(meta['chains'])):
  chain=meta['chains'][ci];selected=inspection['ids'][inspection['chain_labels']==ci];selectedset=set(map(int,selected));faces=[f for f in hairfaces if any(int(v) in selectedset for v in f)];sourceids=sorted({int(i) for f in faces for i in f})
  # Weld original authoring seams, not nearby branches in the groomed pose.
  buckets={}
  for vi in sourceids:buckets.setdefault(tuple(np.rint(restworld[vi]/1e-6).astype(np.int64)),[]).append(vi)
  groups=list(buckets.values());mapping={vi:j for j,g in enumerate(groups) for vi in g};points=np.array([initial[g].mean(0) for g in groups]);pin=[]
  root_start=np.array(arm.matrix_world@arm.pose.bones[chain['bones'][0]].head);root_end=np.array(arm.matrix_world@arm.pose.bones[chain['bones'][0]].tail);root_axis=root_end-root_start
  for g in groups:
   weight=0.
   for vi in g:
    real=[(groupnames[x.group],x.weight) for x in actor.data.vertices[vi].groups if groupnames.get(x.group) in bonenames];den=sum(w for _,w in real)
    w=sum(w for n,w in real if n=='頭')/den if den else 0.
    root_band=float(np.dot(initial[vi]-root_start,root_axis)/max(np.dot(root_axis,root_axis),1e-14))<=.15
    weight=max(weight,w,1. if vi in hard or root_band else 0.)
   pin.append(1. if weight>=.8 else 0.)
  seen=set();simfaces=[]
  for f in faces:
   mapped=tuple(mapping[int(i)] for i in f);key=tuple(sorted(mapped))
   if len(set(mapped))<3 or key in seen:continue
   seen.add(key);simfaces.append(mapped)
  sewing_edges,sewing_records=panel_seams(points,simfaces,pin)
  mesh=bpy.data.meshes.new('ClassicHair_'+chain['name']);mesh.from_pydata(points.tolist(),sewing_edges,simfaces);mesh.update();attr=mesh.attributes.new('HairRootPin','FLOAT','POINT');attr.data.foreach_set('value',np.array(pin,np.float32))
  proxy=bpy.data.objects.new('ClassicHair_'+chain['name'],mesh);s.collection.objects.link(proxy);proxy.hide_render=True
  raw_components=component_info(mesh,np.array(pin));rootless_raw=[g for g in raw_components if g['pins']<2]
  # Stock reduction keeps each authored branch's connectivity.
  dec=proxy.modifiers.new('Native_Decimate_OnlyProxy','DECIMATE');dec.ratio=a.ratio;dec.use_collapse_triangulate=True;bpy.context.view_layer.update()
  ev=proxy.evaluated_get(bpy.context.evaluated_depsgraph_get());reduced=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get());proxy.modifiers.remove(dec);proxy.data=reduced
  assert 'HairRootPin' in reduced.attributes,'Decimation lost root weights'
  pin=np.array([x.value for x in reduced.attributes['HairRootPin'].data]);pin=(pin>=.75).astype(np.float32);reduced.attributes['HairRootPin'].data.foreach_set('value',pin)
  components=component_info(reduced,pin);rootless_reduced=[g for g in components if g['pins']<2]
  bm=bmesh.new();bm.from_mesh(reduced);nonmanifold=sum(len(e.link_faces)>2 for e in bm.edges);doubles=len(reduced.vertices)-len(np.unique(np.rint(np.array([v.co[:] for v in reduced.vertices])/1e-7).astype(np.int64),axis=0));bm.free();assert not nonmanifold and not doubles,('Invalid Surface Deform target',nonmanifold,doubles)
  # Geometry transforms under the head while object space stays world-aligned.
  tree,inp,output=new_tree('ClassicHair_HeadAttachment_'+chain['name']);info=tree.nodes.new('GeometryNodeObjectInfo');info.inputs['Object'].default_value=delta;info.transform_space='ORIGINAL';transform=tree.nodes.new('GeometryNodeTransform');tree.links.new(inp.outputs['Geometry'],transform.inputs['Geometry'])
  for outputname,inputname in [('Location','Translation'),('Rotation','Rotation'),('Scale','Scale')]:tree.links.new(info.outputs[outputname],transform.inputs[inputname])
  tree.links.new(transform.outputs['Geometry'],output.inputs['Geometry']);attachment=proxy.modifiers.new('Native_HeadMotion','NODES');attachment.node_group=tree
  mask=actor.vertex_groups.new(name='ClassicHair_Display_'+chain['name']);mask.add([int(i) for i in selected if int(i) not in hard],1.,'REPLACE')
  md=actor.modifiers.new('Native_SurfaceDeform_'+chain['name'],'SURFACE_DEFORM');md.target=proxy;md.vertex_group=mask.name;md.use_sparse_bind=True;md.falloff=4.;md.strength=1.
  bpy.ops.object.select_all(action='DESELECT');actor.hide_set(False);actor.select_set(True);bpy.context.view_layer.objects.active=actor;bpy.context.view_layer.update();bpy.ops.object.surfacedeform_bind(modifier=md.name);assert md.is_bound
  bindings.append(md);proxies.append(proxy);row=dict(chain=chain['name'],proxy=proxy.name,display_vertices=len(selected),raw_proxy_vertices=len(points),proxy_vertices=len(reduced.vertices),proxy_faces=len(reduced.polygons),components=components,raw_components=raw_components,pinned_vertices=int(pin.sum()),attachment_rule='All original true hard roots and head-weighted vertices; additional root boundary band within first 15 percent of authored root segment, not the whole first hair bone',nonmanifold_edges=nonmanifold,duplicate_vertices=doubles,unanchored_raw_components=rootless_raw,unanchored_reduced_components=rootless_reduced,native_sewing_panels=sewing_records,original_weights_edited=False);rows.append(row);status('PROXY_NATIVE_BIND_READY',**row)
 (out/'proxy_inventory.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
 # Check that head animation is not applied twice by the mapping layer.
 controls=[]
 for f in [1,151,201,226,376,450]:
  s.frame_set(f);bpy.context.view_layer.update();actual=coords(actor)
  for md in bindings:md.show_viewport=False
  bpy.context.view_layer.update();reference=coords(actor)
  for md in bindings:md.show_viewport=True
  bpy.context.view_layer.update();error=float(np.max(np.abs(actual-reference)));controls.append(dict(frame=f,rigid_head_transfer_error_m=error));assert error<.0001,('Head transfer interface mismatch',f,error)
 s.frame_set(1);bpy.context.view_layer.update();neutral=coords(actor)
 # Small native bending control, no physical simulation or keyed correction.
 bendmods=[]
 for proxy in proxies:
  origin=bpy.data.objects.new('OnlyBindingControl_Origin',None);s.collection.objects.link(origin);origin.location=np.array([v.co[:] for v in proxy.data.vertices]).mean(0)
  mod=proxy.modifiers.new('OnlyBindingControl_5deg','SIMPLE_DEFORM');mod.deform_method='BEND';mod.deform_axis='Z';mod.angle=float(np.deg2rad(5));mod.origin=origin;bendmods.append((proxy,mod,origin))
 bpy.context.view_layer.update();bent=coords(actor);edges=inspection['edges'];ids=inspection['ids'];l0=np.linalg.norm(neutral[ids[edges[:,0]]]-neutral[ids[edges[:,1]]],axis=1);l1=np.linalg.norm(bent[ids[edges[:,0]]]-bent[ids[edges[:,1]]],axis=1);valid=l0>.001
 bend=dict(max_displacement_m=float(np.linalg.norm(bent-neutral,axis=1).max()),edge_ratio_p01_p99=np.quantile(l1[valid]/l0[valid],[.01,.99]).tolist(),not_physics=True)
 for proxy,mod,origin in bendmods:proxy.modifiers.remove(mod);bpy.data.objects.remove(origin,do_unlink=True)
 bpy.context.view_layer.update();assert np.isfinite(bent).all() and bend['max_displacement_m']<.05,('Binding deforms excessively',bend)
 unanchored=[row for row in rows if row['unanchored_reduced_components']]
 if unanchored:raise RuntimeError('Unanchored proxy pieces require native attachment setup; see proxy_inventory.json')
 # Self-contained copies of the body/wrist caches; their clocks are retained.
 cache=out/'cache';cache.mkdir(exist_ok=True)
 for ob in bpy.data.objects:
  for md in ob.modifiers:
   if md.type=='MESH_CACHE':
    src=Path(bpy.path.abspath(md.filepath));dst=cache/src.name
    if not dst.exists():shutil.copy2(src,dst)
    md.filepath=str(dst)
 for im in bpy.data.images:
  if im.filepath and im.source in {'FILE','MOVIE','SEQUENCE','TILED'}:im.filepath=bpy.path.abspath(im.filepath)
 s['UserHairContactLimitCM']=5.;s['ShutdownForbidden']=True;s['ReviewAllHairCollisionSolved']=False;s.frame_set(1)
 blend=out/'完整角色_全头经典Cloth代理_未物理.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
 report=dict(status='FULL_HEAD_SURFACE_PROXIES_BOUND_NOT_PHYSICS_ACCEPTED',blend=str(blend),source=str(source),proxies=rows,rigid_head_controls=controls,bend_control=bend,initial_max_error_m=float(np.max(np.abs(neutral-initial))),original_source_action_preserved=old.name,whole_actor_vertices=len(actor.data.vertices),original_shape_keys=len(actor.data.shape_keys.key_blocks),original_materials_preserved=True,full_head_visible=True,physics_started=False,user_contact_limit_cm=5,shutdown_forbidden=True)
 (out/'setup.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');status('PREPARATION_COMPLETE_NOT_PHYSICAL',blend=str(blend))
except BaseException as exc:status('SCRIPT_OR_PROXY_SETUP_ERROR',error=repr(exc),traceback=traceback.format_exc());raise
