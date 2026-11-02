"""Retarget original hair proxies/joints to the legal display rest, once.

Body collision primitives are fitted inside the actual current unclothed skin.
No body pose, source action, collision mask, or spring parameter is relaxed.
"""
import bpy,json,sys,traceback,time,importlib
from pathlib import Path
import numpy as np
from mathutils import Matrix,Vector
ROOT=Path(r'E:\project\mmd\mmd_repo');PARENT=ROOT.parent/'work/headswap_xl_codex/native_mmd_bridge_20261030';OLD=PARENT/'blender_native_units';JOB=PARENT/'calibrated_proxy_chain';JOB.mkdir(parents=True,exist_ok=True)
OLDKEY='MMD_NATIVE_UNITS_LEGACY_20261030';KEY='MMD_CALIBRATED_NATIVE_CHAIN_20261030';old=bpy.app.driver_namespace[OLDKEY]
assert KEY not in bpy.app.driver_namespace,'Calibration already queued; inspect it instead of repeating'
state=dict(old,job_directory=str(JOB),stage='CALIBRATION_QUEUED',started=time.time());state.pop('error',None);state.pop('traceback',None);bpy.app.driver_namespace[KEY]=state
def status(stage,**extra):
    state.update(stage=stage,**extra);tmp=JOB/'status.tmp.json';tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),'utf8');tmp.replace(JOB/'status.json')
def calibrate():
    try:
        sys.path.insert(0,str(ROOT/'addon'))
        from animation_contact_tools.surface import coords
        from animation_contact_tools.closed_collider_field import ClosedColliderField
        from animation_contact_tools.physics_world import ensure_world_members
        scene=bpy.data.scenes[state['scene']];arm=bpy.data.objects[state['armature']];mesh=bpy.data.objects[state['mesh']];root=bpy.data.objects[state['root']]
        assert not root.get('CalibratedLegalHairProxyRest',False),'Do not apply rest warp twice'
        scene.rigidbody_world.enabled=False;scene.frame_set(1);bpy.context.view_layer.update()
        data=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input_body_aware';oldx=np.load(data/'hair_original.npy').astype(np.float64);newx=np.load(data/'hair_initial.npy').astype(np.float64);binding=np.load(ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/review_11s_20261030/hair_binding.npz');weights=binding['weights'];names=binding['names'].tolist();mapping=json.loads((PARENT/'input/bone_name_map.json').read_text('utf8'));reverse={n:a for a,n in mapping.items()};hair={reverse[n] for n in names if n!='頭'}
        co_before=coords(mesh);mapped=np.load(OLD/'native_vertex_map.npy');assert np.linalg.norm(co_before[mapped]*.08-newx,axis=1).max()<.0003
        selected=np.zeros(len(mesh.data.vertices),dtype=bool);selected[mapped]=True;materials=[]
        for index in range(len(mesh.material_slots)):
            verts={v for f in mesh.data.polygons if f.material_index==index for v in f.vertices}
            if verts and float(selected[list(verts)].mean())>.25:materials.append(index)
        hairverts=np.asarray(sorted({v for f in mesh.data.polygons if f.material_index in materials for v in f.vertices}),dtype=np.int32);assert np.mean(np.isin(mapped,hairverts))>.99,(materials,len(hairverts))
        aw=arm.matrix_world.copy();ai=aw.inverted();head=arm.pose.bones[state['head_bone']];h=aw@head.matrix@(aw@head.bone.matrix_local).inverted();hi=h.inverted();oldpose={n:(aw@arm.pose.bones[n].matrix).copy() for n in hair};oldrest={n:(aw@arm.data.bones[n].matrix_local).copy() for n in hair}
        kin=[o for o in root.children_recursive if o.rigid_body and o.rigid_body.kinematic];bodypose={o.mmd_rigid.bone:np.array(arm.pose.bones[o.mmd_rigid.bone].matrix) for o in kin}
        status('FITTING_MATERIAL_REST_TO_BONE_FRAMES')
        transforms={};records=[]
        for j,name in enumerate(names):
            if name=='頭':continue
            w=weights[:,j].astype(np.float64);ids=np.flatnonzero(w>1e-6);ww=w[ids];ww/=ww.sum();a=oldx[ids];b=newx[ids];ca=np.sum(a*ww[:,None],axis=0);cb=np.sum(b*ww[:,None],axis=0);u,sv,vt=np.linalg.svd((a-ca).T@((b-cb)*ww[:,None]));rot=vt.T@np.diag([1,1,np.linalg.det(vt.T@u.T)])@u.T;trans=cb-rot@ca;world=np.eye(4);world[:3,:3]=rot;world[:3,3]=trans/.08;alias=reverse[name];desired=hi@Matrix(world)@oldpose[alias];transforms[alias]=desired@oldrest[alias].inverted();records.append(dict(bone=name,alias=alias,weighted_fit_rms_m=float(np.sqrt(np.sum(ww*np.sum(((a@rot.T+trans)-b)**2,axis=1)))),translation_m=trans.tolist(),rotation_degrees=float(np.degrees(np.arccos(np.clip((np.trace(rot)-1)/2,-1,1))))))
        module=next(m for n,m in sys.modules.items() if n=='mmd_tools' or n.endswith('.mmd_tools'));model=importlib.import_module(module.__name__+'.core.model').Model(root);model.clean()
        rigids=[o for o in root.children_recursive if getattr(o,'mmd_type','')=='RIGID_BODY'];joints=[o for o in root.children_recursive if getattr(o,'mmd_type','')=='JOINT'];rigidrest={o.name:o.matrix_world.copy() for o in rigids};jointrest={o.name:o.matrix_world.copy() for o in joints}
        for obj in bpy.context.selected_objects:obj.select_set(False)
        arm.select_set(True);bpy.context.view_layer.objects.active=arm;bpy.ops.object.mode_set(mode='EDIT')
        lengths={n:arm.data.edit_bones[n].length for n in hair}
        for n in hair:arm.data.edit_bones[n].use_connect=False
        for n in hair:arm.data.edit_bones[n].matrix=ai@transforms[n]@oldrest[n];arm.data.edit_bones[n].length=lengths[n]
        bpy.ops.object.mode_set(mode='OBJECT')
        action=arm.animation_data.action
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in list(bag.fcurves):
                        if any(curve.data_path.startswith('pose.bones["'+n+'"].') for n in hair):bag.fcurves.remove(curve)
        for n in hair:
            b=arm.pose.bones[n];b.location=(0,0,0);b.rotation_mode='QUATERNION';b.rotation_quaternion=(1,0,0,0);b.scale=(1,1,1)
        # Bake the original first-pose material into the new common head rest.
        mw=mesh.matrix_world;target=np.asarray([mw.inverted()@hi@Vector(v) for v in co_before[hairverts]],dtype=np.float32);base=np.empty((len(mesh.data.vertices),3),dtype=np.float32);mesh.data.shape_keys.key_blocks[0].data.foreach_get('co',base.ravel());delta=target-base[hairverts]
        for key in mesh.data.shape_keys.key_blocks:
            c=np.empty_like(base);key.data.foreach_get('co',c.ravel());c[hairverts]+=delta;key.data.foreach_set('co',c.ravel())
        mesh.data.update()
        for o in rigids:
            if o.mmd_rigid.bone in transforms:o.matrix_world=transforms[o.mmd_rigid.bone]@rigidrest[o.name]
        for o in joints:
            c=o.rigid_body_constraint;alias=c.object2.mmd_rigid.bone if c and c.object2 else ''
            if alias not in transforms:alias=c.object1.mmd_rigid.bone if c and c.object1 else ''
            if alias in transforms:o.matrix_world=transforms[alias]@jointrest[o.name]
        scene.frame_set(1);bpy.context.view_layer.update();err=max(float(np.abs(np.array(arm.pose.bones[n].matrix)-v).max()) for n,v in bodypose.items());assert err<1e-4,('Body bone changed',err)
        status('FITTING_BODY_PRIMITIVES_TO_ACTUAL_SKIN')
        field=ClosedColliderField(np.load(data/'body.npy',mmap_mode='r')[0],np.load(data/'body_faces.npy'));bodyfits=[]
        for o in rigids:
            if o.mmd_rigid.bone in hair:continue
            b=arm.pose.bones.get(o.mmd_rigid.bone)
            if b is None:continue
            dmat=np.array(aw@b.matrix@(aw@b.bone.matrix_local).inverted());restmat=np.array(o.matrix_world);posemat=dmat@restmat;local=np.asarray([v.co[:] for v in o.data.vertices]);o.data.calc_loop_triangles();tris=np.asarray([t.vertices[:] for t in o.data.loop_triangles]);samples=np.vstack([local,local[tris].mean(1)]);centre=posemat[:3,3]*.08;dc,nc=field(centre[None,:]);original_size=list(o.mmd_rigid.size)
            if dc[0]>-.001:
                candidates=[centre]
                bw=np.array(aw@b.matrix);tail=np.array(aw@b.matrix@Vector((0,b.bone.length,0)))
                candidates.extend([bw[:3,3]*.08,(bw[:3,3]*.75+tail*.25)*.08,(bw[:3,3]+tail)*.04])
                candidates.extend([centre-(float(dc[0])+inset)*nc[0] for inset in [.001,.002,.004,.008]])
                ds,_=field(np.asarray(candidates));centre=np.asarray(candidates[int(np.argmin(ds))]);assert ds.min()<-.0005,('Body proxy centre cannot be placed in skin',o.name,float(ds.min()))
                newrest=np.linalg.inv(dmat)@np.r_[centre/.08,1.];o.matrix_world.translation=Vector(newrest[:3]);restmat=np.array(o.matrix_world);posemat=dmat@restmat
            def clearance(alpha):
                points=(samples*alpha)@posemat[:3,:3].T+posemat[:3,3];dd,_=field(points*.08);return float(dd.max())
            low=0.;high=1.
            if clearance(1.)<=-.0005:low=1.
            else:
                for _ in range(16):
                    middle=(low+high)/2
                    if clearance(middle)<=-.0005:low=middle
                    else:high=middle
            assert low>.01,('Inscribed body proxy degenerate',o.name,low)
            o.mmd_rigid.size=tuple(x*low for x in original_size);bodyfits.append(dict(object=o.name,bone=mapping.get(b.name,b.name),uniform_scale=low,original_size=original_size,new_size=list(o.mmd_rigid.size),centre_first_pose_m=centre.tolist(),max_outside_sample_m=clearance(low)))
        root['CalibratedLegalHairProxyRest']=True
        for obj in bpy.context.selected_objects:obj.select_set(False)
        root.select_set(True);bpy.context.view_layer.objects.active=root
        bpy.ops.mmd_tools.build_rig(non_collision_distance_scale=1e6,collision_margin=.04)
        rig=[o for o in root.children_recursive if o.rigid_body];cons=[o for o in root.children_recursive if o.rigid_body_constraint];members=ensure_world_members(rig,cons)
        for o in cons:
            if o.rigid_body_constraint.type=='GENERIC_SPRING':o.rigid_body_constraint.spring_type='SPRING1'
        scene.rigidbody_world.enabled=False;scene.frame_set(1);bpy.context.view_layer.update();replay=float(np.linalg.norm(coords(mesh)[mapped]*.08-newx,axis=1).max());assert replay<.0003,replay
        for name in ['native_vertex_map.npy','native_head_initial.npy']:(JOB/name).write_bytes((OLD/name).read_bytes())
        report=dict(method='weighted rigid rest retarget + sampled inscribed body primitives',bone_fits=records,body_fits=bodyfits,initial_display_replay_m=replay,body_bone_matrix_change=err,materials=[mesh.material_slots[i].material.name for i in materials],hair_vertices_native=len(hairverts),original_springs_masses_limits_and_collision_masks_preserved=True)
        (JOB/'rest_proxy_calibration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');state.update(membership=members,initial_display_replay_m=replay,calibration_report=str(JOB/'rest_proxy_calibration.json'));bpy.app.driver_namespace['ACTIVE_NATIVE_MMD_JOB_KEY']=KEY
        bpy.ops.wm.save_as_mainfile(filepath=str(JOB/'calibrated_original_chain_ready.blend'),compress=True)
        status('CALIBRATED_REQUIRES_INITIAL_PROXY_AUDIT')
    except BaseException as exc:status('FAILED',error=repr(exc),traceback=traceback.format_exc())
    return None
status('CALIBRATION_QUEUED');bpy.app.timers.register(calibrate,first_interval=.1);print(json.dumps(dict(queued=True,status=str(JOB/'status.json'))))
