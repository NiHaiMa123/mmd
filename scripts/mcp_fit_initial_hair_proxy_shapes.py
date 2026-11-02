"""Fit only conflicting hair collision primitives to a legal initial volume."""
import bpy,json,sys,time,traceback,importlib
from pathlib import Path
import numpy as np
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
ROOT=Path(r'E:\project\mmd\mmd_repo');P=ROOT.parent/'work/headswap_xl_codex/native_mmd_bridge_20261030';JOB=P/'calibrated_proxy_chain';state=bpy.app.driver_namespace['MMD_CALIBRATED_NATIVE_CHAIN_20261030']
sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.surface import coords,crosses
from animation_contact_tools.physics_world import ensure_world_members
def status(stage,**extra):
    state.update(stage=stage,**extra);tmp=JOB/'status.tmp.json';tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),'utf8');tmp.replace(JOB/'status.json')
def fit():
    try:
        scene=bpy.data.scenes[state['scene']];arm=bpy.data.objects[state['armature']];root=bpy.data.objects[state['root']];assert not root.get('HairProxyInitialShapesFitted',False) or state.get('initial_proxy_overlap_pairs',0)>0
        scene.rigidbody_world.enabled=False;scene.frame_set(1);bpy.context.view_layer.update()
        if not root.mmd_root.is_built:
            for obj in bpy.context.selected_objects:obj.select_set(False)
            root.select_set(True);bpy.context.view_layer.objects.active=root;bpy.ops.mmd_tools.build_rig(non_collision_distance_scale=1e6,collision_margin=.04)
            for obj in root.children_recursive:
                if obj.rigid_body_constraint and obj.rigid_body_constraint.type=='GENERIC_SPRING':obj.rigid_body_constraint.spring_type='SPRING1'
            scene.rigidbody_world.enabled=False;scene.frame_set(1);bpy.context.view_layer.update()
        audit=json.loads((JOB/'proxy_initial_audit.json').read_text('utf8'));(JOB/'proxy_initial_audit_before_hair_fit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),'utf8')
        affected={r['hair'] for r in audit['allowed_hair_body_proxy_overlap_pairs']};rigids=[o for o in root.children_recursive if o.rigid_body];body=[o for o in rigids if o.rigid_body.kinematic];excluded={frozenset((o.rigid_body_constraint.object1.name,o.rigid_body_constraint.object2.name)) for o in root.children_recursive if o.rigid_body_constraint and o.rigid_body_constraint.enabled and o.rigid_body_constraint.disable_collisions and o.rigid_body_constraint.object1 and o.rigid_body_constraint.object2}
        mapping=json.loads((P/'input/bone_name_map.json').read_text('utf8'));binding=np.load(ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/review_11s_20261030/hair_binding.npz');names=binding['names'].tolist();weights=binding['weights'];initial=np.load(ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input_body_aware/hair_initial.npy')
        fields={}
        for b in body:
            c=coords(b)*.08;b.data.calc_loop_triangles();t=np.asarray([q.vertices[:] for q in b.data.loop_triangles]);tree=BVHTree.FromPolygons(c.tolist(),t.tolist(),all_triangles=True);centre=Vector(c.mean(0));p,n,_,_=tree.find_nearest(centre);sign=1 if (centre-p).dot(n)<0 else -1;fields[b.name]=(c,t,tree,sign,c.min(0),c.max(0))
        captures={}
        for name in affected:
            o=bpy.data.objects[name];o.data.calc_loop_triangles();local=np.asarray([v.co[:] for v in o.data.vertices]);t=np.asarray([q.vertices[:] for q in o.data.loop_triangles]);captures[name]=(np.array(o.matrix_world),local,t,list(o.mmd_rigid.size),o.mmd_rigid.bone)
        module=next(m for n,m in sys.modules.items() if n=='mmd_tools' or n.endswith('.mmd_tools'));model=importlib.import_module(module.__name__+'.core.model').Model(root);model.clean();reports=[]
        for name,(pose,local,tris,size,alias) in captures.items():
            o=bpy.data.objects[name];bone=arm.pose.bones[alias];deform=np.array(arm.matrix_world@bone.matrix@(arm.matrix_world@bone.bone.matrix_local).inverted());j=names.index(mapping[alias]);ids=np.flatnonzero(weights[:,j]>.01);w=weights[ids,j];centre=np.average(initial[ids],axis=0,weights=w);order=np.argsort(np.linalg.norm(initial[ids]-centre,axis=1));candidates=np.vstack([pose[:3,3]*.08,centre,initial[ids[order[np.unique(np.linspace(0,len(order)-1,min(24,len(order))).astype(int))]]]])
            original_world=local@pose[:3,:3].T*.08+pose[:3,3]*.08;lo=np.minimum(original_world.min(0),candidates.min(0))-.005;hi=np.maximum(original_world.max(0),candidates.max(0))+.005
            active=[b for b,(_,_,_,_,bmin,bmax) in fields.items() if frozenset((name,b)) not in excluded and not np.any(hi<bmin) and not np.any(bmax<lo)]
            def distance(points):
                result=np.full(len(points),np.inf)
                for bn in active:
                    _,_,tree,sign,*_=fields[bn];d=[]
                    for v in points:
                        q=Vector(v);p,n,_,dd=tree.find_nearest(q);d.append(dd if (q-p).dot(n)*sign>=0 else -dd)
                    result=np.minimum(result,np.asarray(d))
                return result
            legal=distance(candidates)>=.0006;assert legal.any(),('No legal proxy centre in visible material',name)
            choices=np.flatnonzero(legal);idx=int(choices[np.argmin(np.linalg.norm(candidates[choices]-centre,axis=1))]);chosen=candidates[idx];posed=pose.copy();posed[:3,3]=chosen/.08;samples=np.vstack([local,local[tris].mean(1)])
            def allowed(alpha):
                c=(local*alpha)@posed[:3,:3].T*.08+chosen
                if distance((samples*alpha)@posed[:3,:3].T*.08+chosen).min()<.0003:return False
                ht=BVHTree.FromPolygons(c.tolist(),tris.tolist(),all_triangles=True);cc=Vector(c.mean(0));hp,hn,_,_=ht.find_nearest(cc);hsign=1 if (cc-hp).dot(hn)<0 else -1
                for bn in active:
                    bc,bf,bt,_,*_=fields[bn]
                    for v in bc:
                        q=Vector(v);hp,hn,_,hd=ht.find_nearest(q)
                        if (q-hp).dot(hn)*hsign<0 and hd>.00001:return False
                    for ha,ba in ht.overlap(bt):
                        if crosses([Vector(v) for v in c[tris[ha]]],[Vector(v) for v in bc[bf[ba]]],tolerance=.0000005):return False
                return True
            low=0.;high=1.
            if allowed(1):low=1.
            else:
                for _ in range(18):
                    mid=(low+high)/2
                    if allowed(mid):low=mid
                    else:high=mid
            low*=.999
            assert low>.015,('Proxy requires a different primitive decomposition',name,low)
            rest=np.linalg.inv(deform)@posed;o.matrix_world=Matrix(rest.tolist());o.mmd_rigid.size=tuple(v*low for v in size)
            reports.append(dict(object=name,bone=mapping[alias],scale=low,old_size=size,new_size=list(o.mmd_rigid.size),centre_shift_m=(chosen-pose[:3,3]*.08).tolist(),tested_body_proxies=active))
        root['HairProxyInitialShapesFitted']=True
        for obj in bpy.context.selected_objects:obj.select_set(False)
        root.select_set(True);bpy.context.view_layer.objects.active=root;bpy.ops.mmd_tools.build_rig(non_collision_distance_scale=1e6,collision_margin=.04)
        rigids=[o for o in root.children_recursive if o.rigid_body];cons=[o for o in root.children_recursive if o.rigid_body_constraint];ensure_world_members(rigids,cons)
        for o in cons:
            if o.rigid_body_constraint.type=='GENERIC_SPRING':o.rigid_body_constraint.spring_type='SPRING1'
        scene.rigidbody_world.enabled=False;scene.frame_set(1);bpy.context.view_layer.update()
        (JOB/'hair_proxy_shape_fit.json').write_text(json.dumps(dict(method='largest sampled non-overlapping primitive at a nearby material centre',fitted=reports,collision_pairs_disabled=False,springs_and_masses_changed=False),ensure_ascii=False,indent=2),'utf8')
        bpy.ops.wm.save_as_mainfile(filepath=str(JOB/'calibrated_proxy_shapes_ready.blend'),compress=True);status('CALIBRATED_REQUIRES_INITIAL_PROXY_AUDIT')
    except BaseException as exc:status('FAILED',error=repr(exc),traceback=traceback.format_exc())
    return None
state.pop('error',None);state.pop('traceback',None);status('FITTING_INITIAL_HAIR_PROXY_SHAPES');bpy.app.timers.register(fit,first_interval=.1);print(json.dumps(dict(queued=True,status=str(JOB/'status.json'))))
