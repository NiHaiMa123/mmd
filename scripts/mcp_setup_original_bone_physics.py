"""Schedule original MMD bone physics in the user's Blender MCP, without UI input."""
import bpy,json,sys,os,traceback,time
from pathlib import Path
ROOT=Path(r'E:\project\mmd\mmd_repo')
JOB=ROOT.parent/'work/headswap_xl_codex/native_mmd_bridge_20261030/blender_native_units'
SOURCE=JOB.parent/'input';JOB.mkdir(parents=True,exist_ok=True)
KEY='MMD_NATIVE_UNITS_LEGACY_20261030'
if KEY in bpy.app.driver_namespace:raise RuntimeError('Native MMD job already exists; inspect status instead of starting twice')
state=dict(stage='QUEUED',pid=os.getpid(),started=time.time());bpy.app.driver_namespace[KEY]=state
def status(stage,**extra):
    state.update(stage=stage,**extra);tmp=JOB/'status.tmp.json';tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),'utf8');tmp.replace(JOB/'status.json')
def setup():
    try:
        import numpy as np
        from mathutils.kdtree import KDTree
        sys.path.insert(0,str(ROOT/'addon'))
        from mmd_outfit.service import engine
        from animation_contact_tools.physics_world import ensure_world_members
        from animation_contact_tools.surface import coords
        status('IMPORTING_ORIGINAL_PMX')
        if not bpy.data.filepath:bpy.ops.wm.save_as_mainfile(filepath=str(JOB/'user_scene_before_native_mmd.blend'),copy=True)
        scene=bpy.data.scenes.new('MMD_NativeUnits_LegacySpring1');bpy.context.window.scene=scene
        engine('import_export').ensure_mmd_tools()
        before=set(bpy.data.objects);bpy.ops.mmd_tools.import_model(filepath=str(SOURCE/'character_physics.pmx'),scale=1.)
        imported=[o for o in bpy.data.objects if o not in before];arm=next(o for o in imported if o.type=='ARMATURE');root=arm
        while root and getattr(root,'mmd_type','')!='ROOT':root=root.parent
        assert root
        mesh=max((o for o in imported if o.type=='MESH' and getattr(o,'mmd_type','')!='RIGID_BODY'),key=lambda o:len(o.data.vertices))
        for obj in bpy.context.selected_objects:obj.select_set(False)
        arm.select_set(True);bpy.context.view_layer.objects.active=arm;scene.frame_set(1)
        bpy.ops.mmd_tools.import_vmd(filepath=str(SOURCE/'corrected_fk_preroll.vmd'),scale=1.,margin=0,bone_mapper='PMX',rename_bones=False,update_scene_settings=False,create_new_action=True)
        if scene.rigidbody_world:scene.rigidbody_world.enabled=False
        scene.frame_set(31);bpy.context.view_layer.update();co=coords(mesh)*.08
        data=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input_body_aware';target=np.load(data/'hair_initial.npy');binding=np.load(ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/review_11s_20261030/hair_binding.npz');names=binding['names'].tolist();weights=binding['weights'];mapping=json.loads((SOURCE/'bone_name_map.json').read_text('utf8'));reverse={name:alias for alias,name in mapping.items()};vg={g.index:mapping.get(g.name,g.name) for g in mesh.vertex_groups};ni={n:i for i,n in enumerate(names)}
        tree=KDTree(len(co))
        for i,p in enumerate(co):tree.insert(p,i)
        tree.balance();mapped=[];distances=[];weight_errors=[]
        for i,p in enumerate(target):
            _,nearest,d=tree.find(p);candidates=tree.find_range(p,max(d+2e-5,2e-5));best=None
            for _,idx,distance in candidates:
                w=np.zeros(len(names))
                for g in mesh.data.vertices[idx].groups:
                    n=vg[g.group]
                    if n in ni:w[ni[n]]=g.weight
                error=float(np.abs(w-weights[i]).sum());score=(error,float(distance),idx)
                if best is None or score<best:best=score
            error,distance,idx=best;mapped.append(idx);distances.append(distance);weight_errors.append(error)
        assert max(distances)<.0003,(max(distances),'calibrated display map mismatch')
        assert max(weight_errors)<.0001,max(weight_errors)
        np.save(JOB/'native_vertex_map.npy',np.asarray(mapped,dtype=np.int32));np.save(JOB/'native_head_initial.npy',np.array(arm.matrix_world@next(b for b in arm.pose.bones if b.mmd_bone.name_j==reverse['頭']).matrix))
        state.update(scene=scene.name,armature=arm.name,mesh=mesh.name,root=root.name,head_bone=reverse['頭'],map_max_distance_m=max(distances),map_max_weight_error=max(weight_errors))
        status('BUILDING_ORIGINAL_RIGID_CHAINS')
        scene.frame_set(1)
        for obj in bpy.context.selected_objects:obj.select_set(False)
        root.select_set(True);bpy.context.view_layer.objects.active=root
        bpy.ops.mmd_tools.build_rig(non_collision_distance_scale=1e6,collision_margin=.04)
        rigids=[o for o in root.children_recursive if o.rigid_body];constraints=[o for o in root.children_recursive if o.rigid_body_constraint]
        members=ensure_world_members(rigids,constraints);springs=[]
        for obj in constraints:
            c=obj.rigid_body_constraint
            if c.type=='GENERIC_SPRING':c.spring_type='SPRING1';springs.append(obj.name)
        scene.render.fps=30;scene.frame_start=1;scene.frame_end=480;scene.gravity=(0,0,-9.8)
        world=scene.rigidbody_world;world.enabled=True;world.time_scale=1;world.substeps_per_frame=10;world.solver_iterations=50;world.point_cache.frame_start=1;world.point_cache.frame_end=480
        state.update(rigids=len(rigids),dynamic_rigids=sum(not o.rigid_body.kinematic for o in rigids),constraints=len(constraints),legacy_springs=len(springs),membership=members,units_to_m=.08,gravity_native_units=9.8,substeps_per_frame=10,solver_iterations=50)
        scene['NativeMMDJob']=str(JOB);scene['NativeMMDUnitsToMetres']=.08;scene['NativeMMDBackend']='MMD Tools/Bullet original PMX chains in native units; legacy SPRING1; requires full validation'
        bpy.ops.wm.save_as_mainfile(filepath=str(JOB/'original_bone_physics_ready.blend'),compress=True)
        status('READY_FOR_CONTINUOUS_PHYSICS')
    except BaseException as exc:status('FAILED',error=repr(exc),traceback=traceback.format_exc())
    return None
status('QUEUED');bpy.app.timers.register(setup,first_interval=.2)
print(json.dumps(dict(queued=True,status=str(JOB/'status.json'))))
