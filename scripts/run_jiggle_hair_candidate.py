"""Configure and bake the unmodified upstream Jiggle Physics add-on.

This is scene preparation and a call to the published bake operator, not a
custom dynamics solver. Original files/actions/weights remain untouched.
"""
import argparse, importlib.util, json, re, shutil, struct, sys, time, traceback
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords

p=argparse.ArgumentParser();p.add_argument('--out',required=True)
p.add_argument('--source');p.add_argument('--body-export');p.add_argument('--initial');p.add_argument('--plugin-provenance')
p.add_argument('--colliders',choices=['mesh','ellipsoids','both'],default='both')
p.add_argument('--angle',type=float,default=.7);p.add_argument('--radius-scale',type=float,default=1.)
p.add_argument('--root-elasticity',type=float,default=1.);p.add_argument('--length-elasticity',type=float,default=1.)
p.add_argument('--front-radius',type=float);p.add_argument('--side-radius',type=float)
p.add_argument('--fit-groom-bones',action='store_true');p.add_argument('--fit-radius',action='store_true')
p.add_argument('--preroll',type=int,default=60)
p.add_argument('--pin-root-segments',action='store_true')
p.add_argument('--root-segment-count',type=int,choices=[1,2],default=1)
p.add_argument('--pin-front-segments',action='store_true')
p.add_argument('--head-root-weight',type=float)
p.add_argument('--arm-capsules',action='store_true')
p.add_argument('--arm-padding',type=float,default=.005)
p.add_argument('--simulation-fps',type=int,choices=[30,60,120,240],default=30)
p.add_argument('--front-root-count',type=int,choices=[1,2],default=2)
p.add_argument('--last',type=int,default=450)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
base=ROOT.parent/'work/headswap_xl_codex';research=base/'jiggle_physics_20261031'
src=base/'native_mmd_bridge_20261030/headless_bullet/FINAL_MMD15/完整角色_整头连续物理_15秒.blend'
export=base/'fullhair_repro_20261030/input_body_aware'
if a.source:src=Path(a.source)
if a.body_export:export=Path(a.body_export)
started=time.monotonic()
def status(stage,**kw):
    data=dict(stage=stage,elapsed_s=time.monotonic()-started);data.update(kw)
    tmp=out/'status.tmp.json';tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8');tmp.replace(out/'status.json');print('JIGGLE_JOB',json.dumps(data,ensure_ascii=False),flush=True)
def local_coords(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    ar=np.empty(len(me.vertices)*3,np.float32);me.vertices.foreach_get('co',ar);ev.to_mesh_clear();return ar.reshape(-1,3).copy()
def write_pc2(path,points,step=1.):
    with path.open('wb') as f:
        f.write(struct.pack('<12siiffi',b'POINTCACHE2\0',1,points.shape[1],1.,step,points.shape[0]))
        for block in points:f.write(np.asarray(block,dtype='<f4').tobytes())

try:
    assert not (out/'bake_report.json').exists(),'Use a new candidate directory'
    status('PREPARING_STANDARD_PLUGIN_SCENE')
    engine('import_export').ensure_mmd_tools()
    bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
    s=bpy.context.scene;m=bpy.data.objects['东雪莲x达妮娅_素体'];arm=bpy.data.objects['东雪莲x达妮娅_骨架']
    s.frame_start=1;s.frame_end=a.last;s.render.fps=30;s.use_preview_range=False
    s.tool_settings.use_keyframe_insert_auto=False
    if s.rigidbody_world:s.rigidbody_world.enabled=False
    if 'FullHairCachePublication' in s:del s['FullHairCachePublication']
    removed=[]
    for mod in list(m.modifiers):
        if mod.name=='Full head / continuous bundle physics and body contact':
            removed.append(mod.name);m.modifiers.remove(mod)
    assert removed,'Expected old full-head animation cache modifier'
    # Keep only point carriers still referenced by the retained modifiers.
    referenced=set()
    def visit(group,seen):
        if not group or group.as_pointer() in seen:return
        seen.add(group.as_pointer())
        for node in group.nodes:
            for inp in node.inputs:
                v=getattr(inp,'default_value',None)
                if isinstance(v,bpy.types.Object):referenced.add(v)
            visit(getattr(node,'node_tree',None),seen)
    for mod in m.modifiers:
        if mod.type=='NODES':visit(mod.node_group,set())
    for obj in list(bpy.data.objects):
        if (obj.name.startswith('HairContact_MeasuredPoints') or obj.name=='FullHair_PhysicsPoints') and obj not in referenced:
            bpy.data.objects.remove(obj,do_unlink=True)
    # Copy the still-needed wrist caches, without copying discarded hair caches.
    cache=out/'cache';cache.mkdir(exist_ok=True)
    retained=[]
    for obj in bpy.data.objects:
        for mod in obj.modifiers:
            if mod.type=='MESH_CACHE':
                old=Path(bpy.path.abspath(mod.filepath));target=cache/old.name
                if not target.exists():shutil.copy2(old,target)
                mod.filepath=str(target);retained.append(dict(object=obj.name,path=str(target)))
    initial_file=Path(a.initial) if a.initial else base/'hair_initial_repair_20261030/DELIVER_INITIAL/InitialHairRest.npz'
    z=np.load(initial_file);ids=z['ids'];groups={g.index:g.name for g in m.vertex_groups}
    actual_hair_groups={groups[g.group] for i in ids for g in m.data.vertices[int(i)].groups if g.weight>1e-5}
    hair=[b for b in arm.pose.bones if b.name in actual_hair_groups and b.name not in ['頭','首'] and any(p.name=='頭' for p in b.parent_recursive)]
    hair_names={b.name for b in hair}
    weight_edits=[]
    if a.head_root_weight is not None:
        headgroup=m.vertex_groups['頭'];physical_groups={m.vertex_groups[n].index for n in hair_names if n in m.vertex_groups}
        for i in ids:
            vertex=m.data.vertices[int(i)];headweight=sum(g.weight for g in vertex.groups if g.group==headgroup.index)
            if a.head_root_weight<=headweight<.99999:
                old={groups[g.group]:g.weight for g in vertex.groups if g.group in physical_groups or g.group==headgroup.index}
                for group_id in list(g.group for g in vertex.groups if g.group in physical_groups):m.vertex_groups[group_id].remove([int(i)])
                headgroup.add([int(i)],1.,'REPLACE');weight_edits.append(dict(vertex=int(i),old=old))
    s.frame_set(1);bpy.context.view_layer.update()
    before_body={}
    # Capture body transforms before any plugin is registered.
    body_names=[b.name for b in arm.pose.bones if b.name not in hair_names and not any(p.name in hair_names for p in b.parent_recursive)]
    for frame in sorted({f for f in [1,69,175,242,256,280,310,321,331,336,375,a.last] if f<=a.last}):
        s.frame_set(frame);bpy.context.view_layer.update()
        before_body[frame]=np.asarray([np.array(arm.pose.bones[n].matrix) for n in body_names])
    s.frame_set(1);bpy.context.view_layer.update()
    # Transfer the already-reviewed static first-frame grooming to a separate
    # shape key, preserving all original shape keys, vertex weights and Actions.
    target=z['corrected_initial_world'].astype(float)
    head=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix);oldhead=z['head_matrix'].astype(float)
    tf=head@np.linalg.inv(oldhead);target=target@tf[:3,:3].T+tf[:3,3]
    arm_mod=next(mod for mod in m.modifiers if mod.type=='ARMATURE')
    assert not arm_mod.use_deform_preserve_volume,'Static inverse skinning adapter requires LBS'
    states=[(mod,mod.show_viewport) for mod in m.modifiers]
    for mod,_ in states:mod.show_viewport=False
    bpy.context.view_layer.update();pre=local_coords(m)
    for mod,state in states:mod.show_viewport=state
    mw=np.array(m.matrix_world);aw=np.array(arm.matrix_world);imw=np.linalg.inv(mw)
    localtarget=target@imw[:3,:3].T+imw[:3,3]
    matrices={b.name:imw@aw@np.array(b.matrix)@np.linalg.inv(np.array(b.bone.matrix_local))@np.linalg.inv(aw)@mw for b in arm.pose.bones if b.bone.use_deform}
    groups={g.index:g.name for g in m.vertex_groups};delta=np.zeros_like(pre,dtype=float)
    for j,i in enumerate(ids):
        weights=[(matrices[groups[g.group]],g.weight) for g in m.data.vertices[i].groups if groups[g.group] in matrices and g.weight>0]
        den=sum(w for _,w in weights)
        skin=sum(mat*w for mat,w in weights)/den if den else np.eye(4)
        rest=np.linalg.solve(skin,np.r_[localtarget[j],1.])[:3]
        delta[i]=rest-pre[i]
    original_key_count=len(m.data.shape_keys.key_blocks)
    key=m.shape_key_add(name='Jiggle_一次性初态发型整理',from_mix=False)
    basis=np.array([v.co[:] for v in m.data.shape_keys.key_blocks[0].data]);key.data.foreach_set('co',np.asarray(basis+delta,np.float32).ravel());key.value=1.
    bone_rest_edits=[]
    if a.fit_groom_bones:
        shifts={}
        for b in hair:
            gi=m.vertex_groups[b.name].index;selected=[(int(i),g.weight) for i in ids for g in m.data.vertices[int(i)].groups if g.group==gi and g.weight>.05]
            shifts[b.name]=sum(delta[i]*w for i,w in selected)/sum(w for _,w in selected) if selected else np.zeros(3)
        bpy.ops.object.select_all(action='DESELECT');arm.hide_set(False);arm.select_set(True);bpy.context.view_layer.objects.active=arm
        bpy.ops.object.mode_set(mode='EDIT')
        for n,shift in shifts.items():
            b=arm.data.edit_bones[n];b.use_connect=False
            children=[c.name for c in b.children if c.name in shifts]
            tailshift=shifts[children[0]] if children else shift
            b.head+=Vector(shift);b.tail+=Vector(tailshift)
            bone_rest_edits.append(dict(bone=n,head_offset=shift.tolist(),tail_offset=tailshift.tolist()))
        bpy.ops.object.mode_set(mode='OBJECT');s.frame_set(1)
    bpy.context.view_layer.update();initial=coords(m)[ids]
    initial_error=float(np.linalg.norm(initial-target,axis=1).max())
    assert initial_error<2e-5,('Static rest transfer failed',initial_error)
    np.save(out/'hair_ids.npy',ids);np.save(out/'static_rest_delta.npy',delta[ids])
    # The exact already-corrected animated skin is a standard mesh collider.
    coll=bpy.data.collections.new('Jiggle_Physics_Colliders');s.collection.children.link(coll)
    skin_ids=np.load(export/'skin_ids.npy');faces=np.load(export/'body_faces.npy')
    body_manifest=json.loads((export/'export_complete.json').read_text('utf8'))
    factor=a.simulation_fps//30
    stride=int(round(1/(factor*float(body_manifest['sample_step']))))
    assert stride>=1 and abs(stride*float(body_manifest['sample_step'])*factor-1)<1e-7 and body_manifest['frames'][0]==1
    simlast=1+(a.last-1)*factor
    body=np.load(export/'body.npy',mmap_mode='r')[::stride][:simlast]
    assert len(body)==simlast,'Body export must cover the requested full duration; generate a matching export first'
    exact=bpy.data.meshes.new('Jiggle_BodyColliderMesh');exact.from_pydata(body[0].tolist(),[],faces.tolist());exact.update()
    collider=bpy.data.objects.new('Jiggle_身体碰撞_含头手臂腕部',exact)
    coll.objects.link(collider);collider.hide_render=True;collider.display_type='WIRE'
    bodycache=cache/'animated_body_collider.pc2';write_pc2(bodycache,body,1/factor)
    cm=collider.modifiers.new('已修正身体动作 / 标准PC2重放','MESH_CACHE');cm.cache_format='PC2';cm.filepath=str(bodycache);cm.frame_start=1;cm.frame_scale=1
    cm.play_mode='CUSTOM';cm.time_mode='FRAME';cm.driver_add('eval_frame').driver.expression=f'(frame - 1) * {factor}'
    replay_errors=[]
    for frame in range(1,a.last+1):
        s.frame_set(frame);bpy.context.view_layer.update();replay_errors.append(float(np.abs(coords(collider)-body[(frame-1)*factor]).max()))
    assert max(replay_errors)<5e-6,('Body collider playback mismatch',max(replay_errors))
    (out/'body_cache_replay.json').write_text(json.dumps(dict(frames=a.last,max_error_m=max(replay_errors),sample_step=1/factor),indent=2),'utf8')
    s.frame_set(1);bpy.context.view_layer.update()
    collider_rows=[]
    # Standard ellipsoid empties are supported and recommended by upstream.
    # Dimensions come from the current skin and bone segments, not motion edits.
    major=['頭','首','上半身','上半身2','上半身3','下半身','左腕','左ひじ','左手首','右腕','右ひじ','右手首','左足','左ひざ','右足','右ひざ','左足D','左ひざD','右足D','右ひざD','左足首','右足首','左足首D','右足首D']
    major=[n for n in major if n in arm.pose.bones]
    nearest={}
    for bn in arm.data.bones:
        cur=bn
        while cur and cur.name not in major:cur=cur.parent
        nearest[bn.name]=cur.name if cur else None
    bins={n:[] for n in major}
    for j,i in enumerate(skin_ids):
        score={}
        for g in m.data.vertices[int(i)].groups:
            n=nearest.get(groups[g.group])
            if n:score[n]=score.get(n,0)+g.weight
        if score:
            n=max(score,key=score.get)
            if score[n]>.4:bins[n].append(j)
    if a.colliders in ['ellipsoids','both']:
        for n,selected in bins.items():
            if len(selected)<15:continue
            mat=arm.matrix_world@arm.pose.bones[n].matrix;inv=np.linalg.inv(np.array(mat))
            pts=body[0,selected].astype(float)@inv[:3,:3].T+inv[:3,3]
            lo=np.quantile(pts,.005,axis=0);hi=np.quantile(pts,.995,axis=0)
            center=(lo+hi)*.5;radii=np.maximum((hi-lo)*.5,.012)
            fit_factor=float(np.quantile(np.linalg.norm((pts-center)/radii,axis=1),.98))
            radii*=max(1.,fit_factor)*.96
            if max(radii)>.22:continue  # A merged lower-body bin is not a valid local collider.
            ob=bpy.data.objects.new('Jiggle_Ellipsoid_'+n,None);coll.objects.link(ob)
            ob.empty_display_type='SPHERE';ob.empty_display_size=1.;ob.hide_render=True
            ob.matrix_world=mat@Matrix.Translation(Vector(center))@Matrix.Diagonal(Vector((*radii,1.)))
            c=ob.constraints.new('CHILD_OF');c.target=arm;c.subtarget=n;c.inverse_matrix=mat.inverted()
            collider_rows.append(dict(object=ob.name,bone=n,center=center.tolist(),radii=radii.tolist(),skin_points=len(selected)))
            if a.arm_capsules and n in ['左腕','左ひじ','右腕','右ひじ','左手首','右手首']:
                # A row of upstream-supported sphere empties represents a
                # conventional capsule, retaining full radius at the joints.
                radius=float(max(radii[0],radii[2])+a.arm_padding)
                length=arm.pose.bones[n].length;count=max(3,int(np.ceil(length/radius))+1)
                for j,y in enumerate(np.linspace(0,length,count)):
                    ball=bpy.data.objects.new(f'Jiggle_Capsule_{n}_{j:02d}',None);coll.objects.link(ball)
                    ball.empty_display_type='SPHERE';ball.empty_display_size=1.;ball.hide_render=True
                    ball.matrix_world=mat@Matrix.Translation((0,float(y),0))@Matrix.Diagonal((radius,radius,radius,1.))
                    link=ball.constraints.new('CHILD_OF');link.target=arm;link.subtarget=n;link.inverse_matrix=mat.inverted()
                collider_rows.append(dict(type='capsule_spheres',bone=n,count=count,radius=radius,length=length))
    if a.colliders=='ellipsoids':
        s.collection.objects.link(collider);coll.objects.unlink(collider)
    # Load exactly the downloaded upstream file: no patches or replacements.
    provfile=Path(a.plugin_provenance) if a.plugin_provenance else research/'plugin_provenance.json'
    prov=json.loads(provfile.read_text('utf8'));pluginpath=Path(prov['source_dir'])/'__init__.py'
    spec=importlib.util.spec_from_file_location('jiggle_official',pluginpath,submodule_search_locations=[str(pluginpath.parent)])
    plugin=importlib.util.module_from_spec(spec);sys.modules[spec.name]=plugin;spec.loader.exec_module(plugin);plugin.register()
    bpy.ops.object.select_all(action='DESELECT');arm.hide_set(False);arm.hide_viewport=False;arm.select_set(True);bpy.context.view_layer.objects.active=arm
    for b in hair:
        b.bone.hide=False;b.bone.hide_select=False
        b.rotation_mode='QUATERNION';b.location=(0,0,0);b.rotation_quaternion=(1,0,0,0);b.scale=(1,1,1)
        for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(data_path=prop,frame=1,group=b.name)
    arm.animation_data.action.name='Jiggle_RestPose_独立初态'
    for b in hair:
        # Published spring-bone workflow: fixed attachment segments, freely
        # simulated children. This is a rig setting, not keyed collision repair.
        root=b.parent.name not in hair_names
        frontroot=b.name.startswith('FrontHair') and (root or (a.front_root_count==2 and b.parent.parent and b.parent.parent.name not in hair_names))
        depth=0;ancestor=b.parent
        while ancestor and ancestor.name in hair_names:depth+=1;ancestor=ancestor.parent
        pinned=(a.pin_root_segments and (depth<a.root_segment_count or frontroot)) or (a.pin_front_segments and frontroot)
        b.jiggle.enable=not pinned
        # Upstream Hair.py preset, with explicit no-stretch anchoring and
        # collision radius fitted to the visible weighted hair geometry.
        b.jiggle_root_elasticity=a.root_elasticity;b.jiggle_length_elasticity=a.length_elasticity
        b.jiggle_angle_elasticity=a.angle;b.jiggle_elasticity_soften=.6
        b.jiggle_gravity=.25;b.jiggle_blend=1.;b.jiggle_air_drag=.2;b.jiggle_friction=.5
        b.jiggle.collider_type='Collection';b.jiggle.collider_collection=coll
        radius=.004 if b.name.startswith('FrontHair') else .015
        if a.fit_radius:
            gi=m.vertex_groups[b.name].index;selected=[j for j,i in enumerate(ids) if any(g.group==gi and g.weight>.2 for g in m.data.vertices[int(i)].groups)]
            if selected:
                start=np.array(arm.matrix_world@b.head);end=np.array(arm.matrix_world@b.tail);seg=end-start
                points=target[selected];t=np.clip(((points-start)@seg)/np.dot(seg,seg),0,1)
                distance=np.linalg.norm(points-start-t[:,None]*seg,axis=1)
                radius=min(.045,max(.004,float(np.quantile(distance,.95))+.003))
        if b.name.startswith('FrontHair') and a.front_radius is not None:radius=a.front_radius
        if b.name.startswith('Sidehair') and a.side_radius is not None:radius=a.side_radius
        b.jiggle_collision_radius=radius*a.radius_scale
    arm.jiggle.enable=True;arm.jiggle.mute=False;arm.jiggle.freeze=False
    s.jiggle.enable=True;s.jiggle.preroll=a.preroll;s.jiggle.loop=False;s.jiggle.bake_overwrite=False;s.jiggle.bake_nla=False
    s.frame_set(1);bpy.context.view_layer.update()
    # All generated files remain inside this new candidate directory.
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'完整角色_Jiggle配置_未烘焙.blend'))
    config=dict(plugin=prov,source=str(src),removed_hair_motion_modifiers=removed,static_initial_error_m=initial_error,
                original_shape_keys=original_key_count,added_shape_keys=1,original_weights_edited=bool(weight_edits),head_attachment_weight_edits=weight_edits,
                frames=[1,a.last],fps=30,simulation_fps=a.simulation_fps,collider_mode=a.colliders,ellipsoids=collider_rows,retained_caches=retained,bone_rest_edits=bone_rest_edits,preroll=a.preroll,
                hair_bones=[dict(name=b.name,enabled=b.jiggle.enable,collision_radius=b.jiggle_collision_radius,angle=b.jiggle_angle_elasticity) for b in hair],
                root_elasticity=a.root_elasticity,length_elasticity=a.length_elasticity,arguments=vars(a),scene_gravity=list(s.gravity),plugin_source_sha256=__import__('hashlib').sha256(pluginpath.read_bytes()).hexdigest(),preset='upstream Hair.py properties with explicit root/length elasticity and collision radius; Blend=1; no old motion mixing')
    (out/'configuration.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),'utf8')
    # Standard oversampling: unfold the animation timeline to the requested
    # simulation FPS, let the unchanged plugin bake, then restore source time.
    # NLA strip scaling leaves source Actions untouched. Physical integration
    # remains exclusively inside the upstream plugin.
    def action_curves(action):
        curves=[]
        for layer in action.layers:
            for strip in layer.strips:
                for bag in getattr(strip,'channelbags',[]):curves.extend(bag.fcurves)
        return curves
    def retime_curve(curve,factor):
        for pt in curve.keyframe_points:
            pt.co.x=1+(pt.co.x-1)*factor
            pt.handle_left.x=1+(pt.handle_left.x-1)*factor
            pt.handle_right.x=1+(pt.handle_right.x-1)*factor
        curve.update()
    strip_snapshots=[];cache_snapshots=[];driver_snapshots=[]
    if factor!=1:
        for track in arm.animation_data.nla_tracks:
            for strip in track.strips:
                props={k:getattr(strip,k) for k in ['frame_start','frame_end','action_frame_start','action_frame_end','scale','blend_in','blend_out']}
                strip_snapshots.append((strip,props))
                strip.frame_start=1+(props['frame_start']-1)*factor;strip.scale=props['scale']*factor
                strip.blend_in=props['blend_in']*factor;strip.blend_out=props['blend_out']*factor
                for curve in strip.fcurves:retime_curve(curve,factor)
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.type=='MESH_CACHE':
                    cache_snapshots.append((mod,mod.frame_start,mod.frame_scale))
                    mod.frame_start=1+(mod.frame_start-1)*factor;mod.frame_scale*=factor
                    if mod.play_mode=='CUSTOM' and obj.animation_data:
                        data_path=mod.path_from_id('eval_frame')
                        for curve in obj.animation_data.drivers:
                            if curve.data_path==data_path:
                                driver_snapshots.append((curve.driver,curve.driver.expression))
                                curve.driver.expression=re.sub(r'\bframe\b',f'(1+(frame-1)/{factor})',curve.driver.expression)
        s.frame_end=simlast;s.render.fps=a.simulation_fps
        for frame,expected in before_body.items():
            s.frame_set(1+(frame-1)*factor);bpy.context.view_layer.update()
            actual=np.asarray([np.array(arm.pose.bones[n].matrix) for n in body_names])
            assert float(np.abs(actual-expected).max())<2e-5,'Retiming changed the body pose'
            assert float(np.abs(coords(collider)-body[(frame-1)*factor]).max())<5e-6,'Retiming changed the collider pose'
        s.frame_set(1)
    def progress(scene,*_):
        if scene.frame_current%a.simulation_fps==0:status('BAKING_UPSTREAM_PLUGIN',frame=scene.frame_current,last=scene.frame_end,source_frame=1+(scene.frame_current-1)/factor)
    bpy.app.handlers.frame_change_pre.append(progress)
    bpy.ops.object.mode_set(mode='POSE')
    status('BAKING_UPSTREAM_PLUGIN',frame=1,last=a.last)
    result=bpy.ops.armature.jiggle_bake();assert result=={'FINISHED'},result
    bpy.app.handlers.frame_change_pre.remove(progress)
    bpy.ops.object.mode_set(mode='OBJECT')
    action=arm.animation_data.action;action.name='JigglePhysics_整头_原版插件烘焙'
    s.jiggle.enable=False;arm.jiggle.freeze=True
    if factor!=1:
        for curve in action_curves(action):retime_curve(curve,1/factor)
        for strip,props in strip_snapshots:
            strip.frame_start=props['frame_start'];strip.scale=props['scale']
            strip.blend_in=props['blend_in'];strip.blend_out=props['blend_out']
            for curve in strip.fcurves:retime_curve(curve,1/factor)
        for mod,first,scale in cache_snapshots:mod.frame_start=first;mod.frame_scale=scale
        for driver,expression in driver_snapshots:driver.expression=expression
        s.frame_end=a.last;s.render.fps=30
    errs=[]
    for frame,expected in before_body.items():
        s.frame_set(frame);bpy.context.view_layer.update()
        actual=np.asarray([np.array(arm.pose.bones[n].matrix) for n in body_names]);errs.append(float(np.abs(actual-expected).max()))
    body_error=max(errs);assert body_error<2e-5,('Non-hair body animation changed',body_error)
    s.frame_set(1);bpy.context.view_layer.update()
    for obj in bpy.data.objects:
        for mod in obj.modifiers:
            if mod.type=='MESH_CACHE':
                mod.filepath=bpy.path.abspath(mod.filepath)
                assert Path(mod.filepath).is_file(),('Missing review cache',mod.filepath)
    candidate=out/f'完整角色_JigglePhysics原版_{a.last/30:g}秒.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(candidate))
    report=dict(status='UPSTREAM_PLUGIN_BAKED_NOT_VISUALLY_ACCEPTED',blend=str(candidate),action=action.name,
                plugin=prov,body_bone_max_error=body_error,static_initial_error_m=initial_error,hair_bones=len(hair),active_physics_bones=sum(b.jiggle.enable for b in hair),
                dynamic_hair_contact_audit_pending=True,frames=[1,a.last],elapsed_s=time.monotonic()-started)
    (out/'bake_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    status('BAKED_REQUIRES_GEOMETRY_AND_VISUAL_REVIEW',**report)
except BaseException as exc:
    status('FAILED',error=repr(exc),traceback=traceback.format_exc());raise
