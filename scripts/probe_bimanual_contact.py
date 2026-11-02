"""Six-joint planar arms: preserve a declared hand contact against motor drift.

No fingers or MMD skin: tests the contact policy independently of geometry repair.
Both control and constrained modes retain every native collision pair.
"""
import argparse,hashlib,json,time,traceback
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--contact',action='store_true');p.add_argument('--steps',type=int,default=120);p.add_argument('--motor-scale',type=float,default=10.);a=p.parse_args()
out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
report={'status':'PREPARING','scope':'Six revolute joints, persistent declared palm contact; not a real clasp/finger repair','contact_requested':a.contact,'motor_scale':a.motor_scale,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
def save():(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
save()
try:
    import genesis as gs
    import uipc
    from genesis_ipc_constraints import install_revolute_axis_adapter,install_native_revolute_feedback,install_persistent_hand_contact
    parts=['<mujoco model="bimanual_contact"><compiler angle="radian"/><option gravity="0 0 0"/><worldbody><body name="torso" pos="0 0 0.7"><geom type="box" pos="0 -0.20 0" size="0.12 0.07 0.06"/>']
    names=[]
    for side,x,angles in [('left',-.39,[np.pi/4,-np.pi/2,np.pi/4]),('right',.39,[3*np.pi/4,np.pi/2,3*np.pi/4])]:
        for j,part in enumerate(('upper','fore','hand')):
            name=side+'_'+part;names.append(name)
            pos=f'{x} 0 0' if j==0 else '.25 0 0'
            geom=['<geom type="box" pos=".12 0 0" size=".105 .0125 .0125" density="500"/>',
                  '<geom type="box" pos=".1075 0 0" size=".0925 .0125 .0125" density="500"/>',
                  '<geom type="box" size=".0354 .02 .022" density="500"/>'][j]
            parts.append(f'<body name="{name}" pos="{pos}" euler="0 0 {angles[j]}"><joint name="{name}_joint" type="hinge" axis="0 0 1" limited="true" range="-.8 .8" damping=".02"/>{geom}')
        parts.append('</body></body></body>')
    parts.append('</body></worldbody></mujoco>');xml=out/'bimanual.xml';xml.write_text(''.join(parts),encoding='utf-8')
    gs.init(backend=gs.cpu,precision='64',logging_level='warning');dt=.01
    scene=gs.Scene(sim_options=gs.options.SimOptions(dt=dt,gravity=(0,0,0)),coupler_options=gs.options.IPCCouplerOptions(contact_enable=True,contact_friction_enable=True,contact_d_hat=.001,contact_resistance=1e8,newton_semi_implicit_enable=False,enable_rigid_rigid_contact=True,enable_rigid_dofs_sync=True),show_viewer=False)
    arm=scene.add_entity(gs.morphs.MJCF(file=str(xml)),material=gs.materials.Rigid(coup_type='external_articulation'))
    links=[arm.get_link(name) for name in names]
    if a.contact:report['hand_contact']=install_persistent_hand_contact(scene,links[2],links[5])
    report['axis_adapter']=install_revolute_axis_adapter(scene);save();scene.build(n_envs=1)
    report['feedback']=install_native_revolute_feedback(scene)
    arm.set_dofs_kp(np.array([3.,2.,1.5]*2)*a.motor_scale);arm.set_dofs_kv(np.array([.5,.3,.2]*2)*np.sqrt(a.motor_scale));arm.set_dofs_force_range(np.full(6,-6.),np.full(6,6.))
    cp=scene.sim.coupler;native_links=list(cp._abd_slots_by_link)
    def array(v):return v.detach().cpu().numpy() if hasattr(v,'detach') else np.asarray(v)
    def transform(link):
        w,x,y,z=array(link.get_quat(relative=False)).reshape(-1,4)[0];t=np.eye(4);t[:3,:3]=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]];t[:3,3]=array(link.get_pos(relative=False)).reshape(-1,3)[0];return t
    def surface(link):
        geometry=cp._abd_slots_by_link[link][0].geometry();co=np.asarray(geometry.positions().view()).reshape(-1,3).copy();faces=np.asarray(geometry.triangles().topo().view()).reshape(-1,3);mask=geometry.triangles().find(uipc.builtin.is_surf)
        return co,(faces[np.asarray(mask.view()).reshape(-1)>0] if mask is not None else faces).copy()
    initial=[transform(link) for link in links];local=[];faces=[];native_local=[]
    for link,t in zip(links,initial):
        native_co,face=surface(link);native_t=np.asarray(cp._abd_slots_by_link[link][0].geometry().transforms().view())[0];world=native_co@native_t[:3,:3].T+native_t[:3,3];local.append((world-t[:3,3])@t[:3,:3]);faces.append(face);native_local.append(native_co)
    root_co,root_faces=surface(arm.base_link);root_t=transform(arm.base_link);root_geo_t=np.asarray(cp._abd_slots_by_link[arm.base_link][0].geometry().transforms().view())[0];root_co=root_co@root_geo_t[:3,:3].T+root_geo_t[:3,3]
    q=[];trans=[];body=[[] for _ in links];native=[[] for _ in links];root_positions=[]
    def record():
        q.append(array(arm.get_dofs_position()).reshape(-1).copy());ts=np.array([transform(link) for link in links]);trans.append(ts);root_positions.append(transform(arm.base_link)[:3,3])
        nts=np.asarray(cp._abd_state_geom.instances().find(uipc.builtin.transform).view()) if len(q)>1 else None
        for i,(link,t) in enumerate(zip(links,ts)):
            body[i].append(local[i]@t[:3,:3].T+t[:3,3]);nt=nts[native_links.index(link)] if nts is not None else np.asarray(cp._abd_slots_by_link[link][0].geometry().transforms().view())[0];native[i].append(native_local[i]@nt[:3,:3].T+nt[:3,3])
    times=np.arange(a.steps+1)*dt;s=np.clip(times/.9,0,1);s=s*s*(3-2*s)
    # Shared feasible motion plus deliberately inconsistent per-arm tracking.
    dx=.25*np.sqrt(2);dy=.08*s;radius=np.hypot(dx,dy);beta=np.arccos(radius/.5)
    alpha_left=np.arctan2(dy,dx);alpha_right=np.arctan2(dy,-dx)
    reference=np.stack((alpha_left+beta-np.pi/4,-2*beta+np.pi/2,beta-alpha_left-np.pi/4,
                        alpha_right-beta-3*np.pi/4,2*beta-np.pi/2,2*np.pi-alpha_right-beta-3*np.pi/4),axis=1)
    target=reference+s[:,None]*np.array([.15,-.22,.07,-.15,.22,-.07])
    record();report['status']='RUNNING';save();start=time.perf_counter()
    for frame in range(a.steps):
        arm.control_dofs_position(target[frame+1]);scene.step();record()
        if (frame+1)%30==0:print('BIMANUAL_STEP',frame+1,q[-1],flush=True)
    result={'q':np.array(q),'target':target,'reference':reference,'time_s':times,'transforms':np.array(trans),'root':root_co,'root_faces':root_faces,'root_positions':np.array(root_positions),'names':np.array(names),'parents':np.array([-1,0,1,-1,3,4])}
    for i in range(len(links)):result[f'body_{i}']=np.array(body[i]);result[f'native_{i}']=np.array(native[i]);result[f'faces_{i}']=faces[i]
    left=result['transforms'][:,2];right=result['transforms'][:,5];relative=np.linalg.inv(left)@right;delta=np.linalg.inv(relative[0])@relative
    distance=np.linalg.norm(delta[:,:3,3],axis=1);angle=np.arccos(np.clip((np.trace(delta[:,:3,:3],axis1=1,axis2=2)-1)*.5,-1,1))
    if not all(np.isfinite(v).all() for k,v in result.items() if k!='names'):raise RuntimeError('Nonfinite output')
    np.savez_compressed(out/'trajectory.npz',**result)
    report.update(status='RUN_COMPLETE_REQUIRES_AUDIT',seconds=time.perf_counter()-start,samples=len(q),max_relative_hand_position_error_m=float(distance.max()),max_relative_hand_rotation_error_rad=float(angle.max()),hand_center_max_motion_m=float(np.linalg.norm((left[:,:3,3]+right[:,:3,3])*.5-(left[0,:3,3]+right[0,:3,3])*.5,axis=1).max()),root_translation_m=float(np.linalg.norm(result['root_positions']-result['root_positions'][0],axis=1).max()),max_native_actual_error_m=max(float(np.linalg.norm(result[f'body_{i}']-result[f'native_{i}'],axis=-1).max()) for i in range(6)),joint_limit_violations=int(np.sum(np.abs(result['q'])>.8)),max_motor_target_deviation_rad=float(np.abs(result['q']-target).max()))
except BaseException as exc:report.update(status='FAILED',error=repr(exc),traceback=traceback.format_exc());save();raise
finally:save()
