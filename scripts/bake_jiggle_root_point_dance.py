"""Bake the reviewed root-point recipe, optionally with upstream ellipsoid collisions."""
import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import time
import traceback
from pathlib import Path
import bpy
import numpy as np

REPO = Path(__file__).resolve().parents[1]
BASE = REPO.parent / 'work/headswap_xl_codex'
sys.path.insert(0,str(REPO/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
parser=argparse.ArgumentParser()
parser.add_argument('--out',required=True)
parser.add_argument('--collisions',choices=['off','ellipsoids','mesh'],default='off')
parser.add_argument('--collider-profile')
parser.add_argument('--collider-binding',choices=['child-of','bone-parent'],default='child-of')
parser.add_argument('--plugin-provenance')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
assert not (out/'bake_report.json').exists(),'Completed candidate preserved'
started=time.monotonic()


def write(name,value):
    (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def status(stage,**kwargs):
    value=dict(stage=stage,elapsed_s=time.monotonic()-started,**kwargs)
    write('status.json',value)
    print('DANCE_ROOT_POINT',json.dumps(value,ensure_ascii=False),flush=True)


try:
    status('PREPARING_ORIGINAL_DANCE')
    engine('import_export').ensure_mmd_tools()
    recipe=json.loads((BASE/'jiggle_root_point_20261102/configuration.json').read_text(encoding='utf-8'))
    source=Path(recipe['source'])
    preparation=json.loads((source.parent/'configuration.json').read_text(encoding='utf-8'))
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
    scene=bpy.context.scene
    actor=bpy.data.objects['东雪莲x达妮娅_素体']
    arm=actor.find_armature()
    plugin_provenance=json.loads(Path(args.plugin_provenance).read_text('utf8')) if args.plugin_provenance else preparation['plugin']
    plugin_path=Path(plugin_provenance['source_dir'])/'__init__.py'
    source_sha=hashlib.sha256(plugin_path.read_bytes()).hexdigest()
    if args.plugin_provenance:
        assert plugin_provenance['github_blob_sha_verified']
        assert plugin_provenance['base_commit']==preparation['plugin']['commit']
        assert source_sha==plugin_provenance['source_sha256']
    else:assert source_sha==recipe['plugin_source_sha256']
    spec=importlib.util.spec_from_file_location('jiggle_original_dance',plugin_path,submodule_search_locations=[str(plugin_path.parent)])
    plugin=importlib.util.module_from_spec(spec);sys.modules[spec.name]=plugin
    spec.loader.exec_module(plugin);plugin.register()
    scene.jiggle.enable=False;arm.jiggle.freeze=True
    scene.frame_start=1;scene.frame_end=450;scene.render.fps=30;scene.render.fps_base=1
    scene.use_preview_range=False;scene.tool_settings.use_keyframe_insert_auto=False
    if scene.rigidbody_world:scene.rigidbody_world.enabled=False
    assert not any(m.name=='Full head / continuous bundle physics and body contact' for m in actor.modifiers)
    cache=out/'cache';cache.mkdir(exist_ok=True)
    cache_paths=[]
    for obj in bpy.data.objects:
        for modifier in obj.modifiers:
            if modifier.type=='MESH_CACHE':
                old=Path(bpy.path.abspath(modifier.filepath));target=cache/old.name
                if not target.exists():shutil.copy2(old,target)
                modifier.filepath=str(target)
                cache_paths.append(dict(object=obj.name,path=str(target),play_mode=modifier.play_mode))
    names=[r['name'] for r in recipe['settings']]
    collision_on=args.collisions!='off'
    colliders=bpy.data.collections['Jiggle_Physics_Colliders']
    assert len(colliders.objects)==14 and all(o.type=='EMPTY' for o in colliders.objects)
    mesh_collider=None
    if args.collisions=='mesh':
        assert not args.collider_profile,'One explicit collider backend at a time'
        mesh_collider=bpy.data.objects['Jiggle_身体碰撞_含头手臂腕部']
        assert np.abs(np.array(mesh_collider.matrix_world)-np.eye(4)).max()<1e-9
        assert not mesh_collider.parent and not mesh_collider.constraints
        for obj in list(colliders.objects):colliders.objects.unlink(obj)
        colliders.objects.link(mesh_collider)
    collider_profile=None
    if args.collider_profile:
        assert collision_on,'A collider profile requires native collisions'
        from mathutils import Matrix,Vector
        collider_profile=json.loads(Path(args.collider_profile).read_text('utf8'))
        assert collider_profile['source']==str(source)
        assert collider_profile['existing_hair_collision_radii_retained']
        for obj in list(colliders.objects):colliders.objects.unlink(obj)
        for row in collider_profile['primitives']:
            mat=arm.matrix_world@arm.pose.bones[row['bone']].matrix
            obj=bpy.data.objects.new(row['name'],None);colliders.objects.link(obj)
            obj.empty_display_type='SPHERE';obj.empty_display_size=1.;obj.hide_render=True
            obj.matrix_world=mat@Matrix.Translation(Vector(row['center']))@Matrix.Diagonal((*([row['radius_m']]*3),1.))
            constraint=obj.constraints.new('CHILD_OF');constraint.target=arm;constraint.subtarget=row['bone']
            constraint.inverse_matrix=mat.inverted()
        bpy.context.view_layer.update()
        write('collider_profile.json',collider_profile)
    if args.collisions=='ellipsoids' and args.collider_binding=='bone-parent':
        from mathutils import Matrix
        for obj in colliders.objects:
            world=obj.matrix_world.copy()
            target=obj.constraints[0].subtarget
            for constraint in list(obj.constraints):obj.constraints.remove(constraint)
            obj.parent=arm;obj.parent_type='BONE';obj.parent_bone=target
            obj.matrix_parent_inverse=Matrix.Identity(4);obj.matrix_basis=Matrix.Identity(4)
            bpy.context.view_layer.update()
            parent_transform=obj.matrix_world.copy()
            obj.matrix_parent_inverse=parent_transform.inverted();obj.matrix_basis=world
            bpy.context.view_layer.update()
            assert np.abs(np.array(obj.matrix_world)-np.array(world)).max()<2e-6,('Bone parent moved collider',obj.name)
        assert all(not obj.constraints and obj.parent_type=='BONE' for obj in colliders.objects)
    for settings in recipe['settings']:
        bone=arm.pose.bones[settings['name']]
        bone.jiggle.enable=settings['enabled']
        for key,value in settings.items():
            if key not in ['name','enabled']:setattr(bone,'jiggle_'+key,value)
        bone.jiggle.collider_type='Collection' if collision_on else 'Object'
        bone.jiggle.collider=None
        bone.jiggle.collider_collection=colliders if collision_on else None
    active=sum(arm.pose.bones[n].jiggle.enable for n in names)
    assert len(names)==144 and active==126
    meta=json.loads((BASE/'standard_proxy_20261031/inspection/inputs.json').read_text(encoding='utf-8'))
    data=np.load(BASE/'standard_proxy_20261031/inspection/inputs.npz')
    ids,labels,edges=data['ids'],data['chain_labels'],data['edges']
    root_names=[c['bones'][0] for c in meta['chains'] if c['name'] in recipe['freed_root_chains']]
    assert len(root_names)==18
    body_names=[b.name for b in arm.pose.bones if b.name not in names and not any(p.name in names for p in b.parent_recursive)]
    expected_body=[];expected_roots=[];expected_colliders=[]
    expected_skin_export=np.load(BASE/'fullhair_repro_20261030/input_body_aware/body.npy',mmap_mode='r') if mesh_collider else None
    mesh_cache_setup_error=0.
    for f in range(1,451):
        scene.frame_set(f);bpy.context.view_layer.update()
        expected_body.append(np.array([np.array(arm.pose.bones[n].matrix) for n in body_names]))
        expected_roots.append(np.array([arm.matrix_world@arm.pose.bones[n].head for n in root_names]))
        if collision_on:expected_colliders.append(np.array([np.array(obj.matrix_world) for obj in colliders.objects]))
        if mesh_collider:
            error=float(np.abs(coords(mesh_collider)-expected_skin_export[(f-1)*8]).max())
            mesh_cache_setup_error=max(mesh_cache_setup_error,error)
            assert error<5e-6,('Mesh collider replay differs from actual skin',f,error)
    scene.frame_set(1);bpy.context.view_layer.update()
    initial=coords(actor)
    rest=np.linalg.norm(initial[ids[edges[:,0]]]-initial[ids[edges[:,1]]],axis=1)
    valid=rest>.001
    chain_edges=[np.flatnonzero((labels[edges[:,0]]==j)&(labels[edges[:,1]]==j)&valid) for j in range(27)]
    origin=np.array(arm.matrix_world@arm.pose.bones['頭'].head)
    tips=[]
    for j in range(27):
        selected=ids[labels==j];radii=np.linalg.norm(initial[selected]-origin,axis=1)
        tips.append(selected[radii>=np.quantile(radii,.8)])
    actual_settings=[dict(name=n,enabled=arm.pose.bones[n].jiggle.enable,
        **{key:float(getattr(arm.pose.bones[n],'jiggle_'+key)) for key in ['root_elasticity','length_elasticity','angle_elasticity','elasticity_soften','gravity','blend','air_drag','friction','collision_radius']}) for n in names]
    arm.jiggle.enable=True;arm.jiggle.mute=False;arm.jiggle.freeze=False
    scene.jiggle.enable=True;scene.jiggle.preroll=15;scene.jiggle.loop=False
    scene.jiggle.bake_overwrite=False;scene.jiggle.bake_nla=False
    bpy.ops.object.select_all(action='DESELECT');arm.hide_set(False);arm.select_set(True)
    bpy.context.view_layer.objects.active=arm
    collision_mode='COMMUNITY_PR47_ACTUAL_SKIN_MESH' if mesh_collider else 'NATIVE_SKIN_INSET_SPHERES' if collider_profile else 'NATIVE_14_ELLIPSOIDS' if collision_on else 'OFF'
    suffix='_社区网格碰撞' if mesh_collider else '_骨骼父级碰撞' if collision_on and args.collider_binding=='bone-parent' else '_贴合内缩碰撞' if collider_profile else '_原生碰撞' if collision_on else ''
    prepared=out/f'完整角色_原舞蹈_根部点锚定{suffix}_未烘焙.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(prepared))
    write('configuration.json',dict(source=str(source),recipe_source=str(BASE/'jiggle_root_point_20261102/configuration.json'),
        source_file_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),plugin_source_sha256=source_sha,
        plugin_provenance=plugin_provenance,
        frames=[1,450],fps=30,preroll_seconds=.5,full_head_chains=27,hair_bones=144,active_bones=active,
        settings=actual_settings,root_chains=recipe['freed_root_chains'],
        collision_mode=collision_mode,
        mesh_collider_setup_replay_error_m=mesh_cache_setup_error if mesh_collider else None,
        collider_profile_source=args.collider_profile,
        collider_binding='WORLD_SPACE_PC2' if mesh_collider else args.collider_binding if collision_on else None,
        collision_objects=[o.name for o in colliders.objects] if collision_on else [],
        body_animation='Original prepared dance NLA, not controlled-head test',cache_paths=cache_paths,
        vertex_count=len(actor.data.vertices),shape_key_count=len(actor.data.shape_keys.key_blocks),weights_edited=False,
        controlled_head_action_added=False,shutdown_forbidden=True))
    records=[];collision_responses={};collision_steps=[];collider_timing=[]
    def observer(frame,event,arg):
        if collision_on and event=='call' and frame.f_code is plugin.jiggle_simulate.__code__:
            current=np.array([np.array(obj.matrix_world) for obj in colliders.objects])
            error=float(np.abs(current-expected_colliders[int(scene.frame_current)-1]).max())
            sample=dict(frame=int(scene.frame_current),maximum_matrix_error=error)
            if mesh_collider:
                sample['actual_mesh_replay_error_m']=float(np.abs(coords(mesh_collider)-expected_skin_export[(int(scene.frame_current)-1)*8]).max())
                assert sample['actual_mesh_replay_error_m']<5e-6,('Mesh collider out of sync at native solve',sample)
            collider_timing.append(sample)
            assert error<2e-5,('Collider not at its evaluated current-frame position',scene.frame_current,error)
        if collision_on and event=='return' and frame.f_code is plugin.VirtualParticle.empty_collide.__code__:
            correction=(arg-frame.f_locals['position']).length
            if correction>1e-8:
                f=int(scene.frame_current);row=collision_responses.setdefault(f,dict(count=0,maximum_projection_m=0.))
                row['count']+=1;row['maximum_projection_m']=max(row['maximum_projection_m'],correction)
        if mesh_collider and event=='return' and frame.f_code is plugin.VirtualParticle.mesh_collide.__code__:
            original=frame.f_locals.get('pos',frame.f_locals.get('position'))
            correction=(arg-original).length
            if correction>1e-8:
                f=int(scene.frame_current);row=collision_responses.setdefault(f,dict(count=0,maximum_projection_m=0.))
                row['count']+=1;row['maximum_projection_m']=max(row['maximum_projection_m'],correction)
        if event=='return' and frame.f_code is plugin.jiggle_simulate.__code__:
            particles=frame.f_locals['virtual_particles']
            count=sum(p.needs_collision for p in particles)
            assert (count>0)==collision_on,('Collision state mismatch',count,collision_on)
            collision_steps.append(dict(frame=int(scene.frame_current),particles_with_collision=count))
            points=np.array([p.position[:] for p in particles],dtype=np.float32)
            assert np.isfinite(points).all(),('Nonfinite particle',scene.frame_current)
            records.append((int(scene.frame_current),points))
            if scene.frame_current%60==0:print('DANCE_BAKE_PROGRESS',scene.frame_current,flush=True)
    bpy.ops.object.mode_set(mode='POSE');status('BAKING_ORIGINAL_PLUGIN_CONTINUOUSLY',first=1,last=450)
    previous_profile=sys.getprofile();sys.setprofile(observer)
    try:result=bpy.ops.armature.jiggle_bake()
    finally:sys.setprofile(previous_profile)
    assert result=={'FINISHED'}
    scene.jiggle.enable=False;arm.jiggle.freeze=True
    bpy.ops.object.mode_set(mode='OBJECT')
    action=arm.animation_data.action;action.name=f'Jiggle原版_原舞蹈_根部点锚定{suffix}_450帧'
    skin=np.load(BASE/'fullhair_repro_20261030/input_body_aware/skin_ids.npy')
    expected_skin=np.load(BASE/'fullhair_repro_20261030/input_body_aware/body.npy',mmap_mode='r')
    body_error=0.;skin_error=0.;root_error=0.;strain=[];motion=[];head_world=[]
    status('VERIFYING_ORIGINAL_BODY_AND_DISPLAY_HAIR')
    for f in range(1,451):
        scene.frame_set(f);bpy.context.view_layer.update()
        berror=float(np.abs(np.array([np.array(arm.pose.bones[n].matrix) for n in body_names])-expected_body[f-1]).max())
        co=coords(actor);assert np.isfinite(co).all(),(f,'Nonfinite display geometry')
        serror=float(np.abs(co[skin]-expected_skin[(f-1)*8]).max())
        rerror=float(np.linalg.norm(np.array([arm.matrix_world@arm.pose.bones[n].head for n in root_names])-expected_roots[f-1],axis=1).max())
        body_error=max(body_error,berror);skin_error=max(skin_error,serror);root_error=max(root_error,rerror)
        assert berror<2e-5 and serror<5e-6 and rerror<2e-5,(f,berror,serror,rerror)
        motion.append(np.array([co[t].mean(0) for t in tips]));head_world.append(np.array(arm.matrix_world@arm.pose.bones['頭'].matrix))
        length=np.linalg.norm(co[ids[edges[:,0]]]-co[ids[edges[:,1]]],axis=1)
        ratio=np.ones(len(rest));ratio[valid]=length[valid]/rest[valid]
        flags=[dict(chain=meta['chains'][j]['name'],p99=float(np.quantile(ratio[e],.99)),growth_cm=float((length[e]-rest[e]).max()*100))
            for j,e in enumerate(chain_edges) if len(e) and np.quantile(ratio[e],.99)>1.5 and (length[e]-rest[e]).max()>.02]
        if flags:strain.append(dict(frame=f,chains=flags))
    unique={f:p for f,p in records}
    np.savez_compressed(out/'motion.npz',frames=np.arange(1,451),physical_tip_world=motion,head_world=head_world,
        raw_frames=sorted(unique),raw_particles=[unique[f] for f in sorted(unique)])
    assert hashlib.sha256(plugin_path.read_bytes()).hexdigest()==source_sha
    scene.frame_set(1);bpy.context.view_layer.update()
    blend=out/f'完整角色_原舞蹈_根部点锚定{suffix}_15秒.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report=dict(status='BAKED_ORIGINAL_DANCE_REQUIRES_VISUAL_REVIEW',blend=str(blend),action=action.name,frames=[1,450],
        fps=30,active_bones=active,full_head_chains=27,body_bone_max_error=body_error,body_skin_max_error_m=skin_error,
        root_point_anchor_error_m=root_error,strain_flags=strain,
        collisions=collision_on,collision_mode=collision_mode,
        plugin_provenance=plugin_provenance,
        no_collision_confirmed_in_every_observed_step=not collision_on,
        collision_confirmed_in_every_observed_step=collision_on and all(r['particles_with_collision']>0 for r in collision_steps),
        plugin_source_sha256=source_sha,source_animation_preserved=True,new_per_frame_corrective_motion=False,
        elapsed_s=time.monotonic()-started)
    if collision_on:
        write('collision_observation.json',dict(steps=collision_steps,responses=collision_responses,
              observed_upstream_solver_only=True,per_projection_is_not_final_surface_penetration_depth=True))
        write('collider_timing.json',dict(binding='WORLD_SPACE_PC2' if mesh_collider else args.collider_binding,samples=collider_timing,
              maximum_matrix_error=max(r['maximum_matrix_error'] for r in collider_timing),
              method='Collider matrix sampled at entry to every upstream jiggle_simulate call, compared with pre-evaluated body-only current-frame transform'))
    write('bake_report.json',report);status('BAKED_REQUIRES_VISUAL_REVIEW',strain_flag_frames=len(strain),blend=str(blend))
except BaseException as exc:
    sys.setprofile(None);status('FAILED',error=repr(exc),traceback=traceback.format_exc());raise
