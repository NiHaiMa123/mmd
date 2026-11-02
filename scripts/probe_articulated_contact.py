"""Two-link arm, fixed head surrogate and moving two-layer garment probe.

The optional SciPy constrained trajectory fit handles incidental collisions;
it is not a contact-semantic model and must not be used to split a clasp.
"""
import argparse,json,os,time,traceback,hashlib
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--plan',action='store_true');p.add_argument('--cloth',action='store_true');p.add_argument('--intent',choices=('incidental','intentional'),default='incidental');p.add_argument('--steps',type=int,default=150);a=p.parse_args();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
report={'status':'PREPARING','scope':'Planar two-link arm, fixed head surrogate, optional moving garment; not full MMD','motion_class':'incidental collision','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
save=lambda:(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
save()
HEAD=np.array([.43,.25,.7]);RADIUS=.10;DT=.01
BOXES=[(np.array([.005,-.03,-.03]),np.array([.305,.03,.03])),(np.array([.015,-.03,-.03]),np.array([.315,.03,.03]))]
FACES=np.array([(0,1,3),(0,3,2),(4,6,7),(4,7,5),(0,4,5),(0,5,1),(2,3,7),(2,7,6),(0,2,6),(0,6,4),(1,5,7),(1,7,3)],dtype=np.int32)
def transforms(q):
    angles=np.stack((q[...,0],q.sum(axis=-1)),axis=-1);c=np.cos(angles);s=np.sin(angles)
    origins=np.zeros(q.shape[:-1]+(2,3));origins[...,0,2]=.7;origins[...,1,0]=.32*c[...,0];origins[...,1,1]=.32*s[...,0];origins[...,1,2]=.7
    return angles,origins
def clearance(q):
    angles,origins=transforms(q);v=HEAD-origins;c=np.cos(angles);s=np.sin(angles);local=np.stack((c*v[...,0]+s*v[...,1],-s*v[...,0]+c*v[...,1],v[...,2]),axis=-1)
    centres=np.array([(lo+hi)/2 for lo,hi in BOXES]);halves=np.array([(hi-lo)/2 for lo,hi in BOXES]);d=np.abs(local-centres)-halves
    return np.linalg.norm(np.maximum(d,0),axis=-1)+np.minimum(d.max(axis=-1),0)-RADIUS
def source_track(times):
    t=np.clip(times/.9,0,1);s=t*t*(3-2*t);return s[:,None]*np.array([.95,-.40])
times=np.arange(a.steps+1)*DT;source=source_track(times);planned=source.copy()
try:
    if a.intent=='intentional':raise ValueError('This planner cannot preserve an intentional clasp; supply a contact-preserving solver instead')
    if a.plan:
        control_times=np.linspace(0,times[-1],41);reference=source_track(control_times)
        def objective(x):
            q=x.reshape(-1,2);d=q-reference
            return float(np.sum(d*d)+20*np.sum(np.diff(d,n=2,axis=0)**2)+2*np.sum(np.diff(d,axis=0)**2))
        def constraints(x):return (clearance(x.reshape(-1,2))-.008).ravel()
        seed=reference.copy();seed[:,1]-=.8*np.clip(control_times/.9,0,1)
        bounds=[(-.2,1.4),(-1.7,.1)]*len(reference);bounds[:2]=[(0,0),(0,0)]
        start=time.perf_counter();solution=minimize(objective,seed.ravel(),method='SLSQP',bounds=bounds,constraints={'type':'ineq','fun':constraints},options={'maxiter':250,'ftol':1e-8})
        control=solution.x.reshape(-1,2);planned=np.stack([np.interp(times,control_times,control[:,i]) for i in range(2)],axis=1)
        report['planner']={'status':str(solution.message),'success':bool(solution.success),'seconds':time.perf_counter()-start,'source_min_clearance_m':float(clearance(source).min()),'planned_dense_min_clearance_m':float(clearance(planned).min()),'max_joint_target_change_rad':float(np.abs(planned-source).max()),'keeps_fixed_head':True,'preserves_intentional_hand_contacts':False}
        save()
        if not solution.success or clearance(planned).min()<.004:raise RuntimeError('Constrained path did not pass dense clearance')
    import genesis as gs
    import uipc
    from genesis_ipc_constraints import install_revolute_axis_adapter,install_native_revolute_feedback,install_cloth_body_stitches
    xml=out/'arm.xml';xml.write_text('''<mujoco model="two_link_contact"><compiler angle="radian"/><option gravity="0 0 0"/><worldbody>
<body name="torso" pos="0 0 0.7"><geom type="box" pos="-0.12 0 -0.1" size="0.075 0.08 0.15"/>
<body name="upper"><joint name="shoulder" type="hinge" axis="0 0 1" limited="true" range="-0.2 1.4" damping="0.04"/><geom type="box" pos="0.155 0 0" size="0.15 0.03 0.03" density="500"/>
<body name="fore" pos="0.32 0 0"><joint name="elbow" type="hinge" axis="0 0 1" limited="true" range="-1.7 0.1" damping="0.04"/><geom type="box" pos="0.165 0 0" size="0.15 0.03 0.03" density="500"/></body></body></body>
</worldbody></mujoco>''',encoding='utf-8')
    gs.init(backend=gs.cpu,logging_level='warning',precision='64')
    scene=gs.Scene(sim_options=gs.options.SimOptions(dt=DT,gravity=(0,0,0)),coupler_options=gs.options.IPCCouplerOptions(contact_enable=True,contact_friction_enable=True,contact_d_hat=.002,contact_resistance=1e8,newton_semi_implicit_enable=False,enable_rigid_rigid_contact=True,enable_rigid_dofs_sync=True),show_viewer=False)
    arm=scene.add_entity(gs.morphs.MJCF(file=str(xml)),material=gs.materials.Rigid(coup_type='external_articulation'))
    head=scene.add_entity(gs.morphs.Sphere(pos=tuple(HEAD),radius=RADIUS,fixed=True),material=gs.materials.Rigid(coup_type='ipc_only'))
    fabrics=[]
    if a.cloth:
        n=11;verts=np.array([[.335+.30*i/(n-1),.036,.435+.3*j/(n-1)] for j in range(n) for i in range(n)]);faces=[]
        for j in range(n-1):
            for i in range(n-1):v=j*n+i;faces.extend(((v,v+n,v+1),(v+1,v+n,v+n+1)))
        mesh=out/'sleeve.obj';mesh.write_text('\n'.join(['v '+' '.join(map(str,v)) for v in verts]+['f '+' '.join(str(v+1) for v in f) for f in faces])+'\n')
        for layer in range(2):fabrics.append(scene.add_entity(gs.morphs.Mesh(file=str(mesh),pos=(0,.01*layer,0)),material=gs.materials.FEM.Cloth(E=1e5,nu=.45,rho=400,thickness=.001,bending_stiffness=.5,friction_mu=.4)))
        selections={}
        for fabric in fabrics:
            co=np.asarray(fabric.init_positions);top=np.flatnonzero(co[:,2]>co[:,2].max()-1e-6);selections[fabric]=np.array([top[np.argmin(co[top,0])],top[np.argmax(co[top,0])]])
        report['attachments']=install_cloth_body_stitches(scene,selections,arm.get_link('fore'))
    report['axis_adapter']=install_revolute_axis_adapter(scene);report['status']='BUILDING';save();scene.build(n_envs=1)
    report['feedback']=install_native_revolute_feedback(scene)
    arm.set_dofs_kp(np.array([8.,5.]));arm.set_dofs_kv(np.array([1.,.6]));arm.set_dofs_force_range(np.array([-3.,-2.]),np.array([3.,2.]))
    links=[arm.get_link('upper'),arm.get_link('fore')];coupler=scene.sim.coupler;all_links=list(coupler._abd_slots_by_link)
    def array(x):return x.detach().cpu().numpy() if hasattr(x,'detach') else np.asarray(x)
    def world_co(link):
        w,x,y,z=array(link.get_quat(relative=False)).reshape(-1,4)[0];r=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]);return array(link.get_pos(relative=False)).reshape(-1,3)[0],r
    corners=[np.array([[x,y,z] for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])]) for lo,hi in BOXES]
    q=[];body=[[],[]];cloth=[[] for _ in fabrics];head_positions=[];torso_positions=[];native=[[],[]];native_faces=[]
    for link in links:
        g=coupler._abd_slots_by_link[link][0].geometry();f=np.asarray(g.triangles().topo().view()).reshape(-1,3);mask=g.triangles().find(uipc.builtin.is_surf);native_faces.append(f[np.asarray(mask.view()).reshape(-1)>0].copy() if mask is not None else f.copy())
    hg=coupler._abd_slots_by_link[head.base_link][0].geometry();hc=np.asarray(hg.positions().view()).reshape(-1,3);ht=np.asarray(hg.transforms().view())[0];head_co=hc@ht[:3,:3].T+ht[:3,3];hf=np.asarray(hg.triangles().topo().view()).reshape(-1,3);mask=hg.triangles().find(uipc.builtin.is_surf);hf=hf[np.asarray(mask.view()).reshape(-1)>0] if mask is not None else hf
    tg=coupler._abd_slots_by_link[arm.base_link][0].geometry();tc=np.asarray(tg.positions().view()).reshape(-1,3);tt=np.asarray(tg.transforms().view())[0];torso_co=tc@tt[:3,:3].T+tt[:3,3];tf=np.asarray(tg.triangles().topo().view()).reshape(-1,3);mask=tg.triangles().find(uipc.builtin.is_surf);tf=tf[np.asarray(mask.view()).reshape(-1)>0] if mask is not None else tf
    def record():
        q.append(array(arm.get_dofs_position()).reshape(-1).copy());head_positions.append(array(head.base_link.get_pos()).reshape(-1,3)[0].copy());torso_positions.append(array(arm.base_link.get_pos()).reshape(-1,3)[0].copy())
        for i,link in enumerate(links):
            pos,r=world_co(link);body[i].append(corners[i]@r.T+pos)
            g=coupler._abd_slots_by_link[link][0].geometry();co=np.asarray(g.positions().view()).reshape(-1,3);t=np.asarray(coupler._abd_state_geom.instances().find(uipc.builtin.transform).view())[all_links.index(link)] if len(q)>1 else np.asarray(g.transforms().view())[0];native[i].append((co@t[:3,:3].T+t[:3,3]).copy())
        for i,fabric in enumerate(fabrics):cloth[i].append(array(fabric.get_state().pos).reshape(-1,3).copy())
    report['status']='RUNNING';save();record();start=time.perf_counter()
    for frame in range(a.steps):
        arm.control_dofs_position(planned[frame+1]);scene.step();record()
        if (frame+1)%30==0:print('ARTICULATED_CONTACT_STEP',frame+1,q[-1],flush=True)
    result=dict(q=np.array(q),target=planned,source=source,time_s=times,head=head_co,head_faces=hf,head_positions=np.array(head_positions),torso=torso_co,torso_faces=tf,torso_positions=np.array(torso_positions),body_faces=FACES)
    for i in range(2):result[f'body_{i}']=np.array(body[i]);result[f'native_{i}']=np.array(native[i]);result[f'native_faces_{i}']=native_faces[i]
    angles,origins=transforms(source)
    for i in range(2):
        source_co=[]
        for angle,origin in zip(angles[:,i],origins[:,i]):
            c,s=np.cos(angle),np.sin(angle);rotation=np.array([[c,-s,0],[s,c,0],[0,0,1]]);source_co.append(corners[i]@rotation.T+origin)
        result[f'source_body_{i}']=np.asarray(source_co)
    for i,fabric in enumerate(fabrics):result[f'cloth_{i}']=np.array(cloth[i]);result[f'cloth_faces_{i}']=np.asarray(fabric.surface_triangles)
    if not all(np.isfinite(v).all() for v in result.values()):raise RuntimeError('Nonfinite output')
    np.savez_compressed(out/'trajectory.npz',**result)
    report.update(status='RUN_COMPLETE_REQUIRES_AUDIT',seconds=time.perf_counter()-start,samples=len(q),head_max_translation_m=float(np.linalg.norm(result['head_positions']-result['head_positions'][0],axis=1).max()),torso_max_translation_m=float(np.linalg.norm(result['torso_positions']-result['torso_positions'][0],axis=1).max()),min_actual_analytic_head_clearance_m=float(clearance(result['q']).min()),max_tracking_error_rad=float(np.abs(result['q']-planned).max()),joint_limit_violations=int(np.sum((result['q']<[-.2,-1.7])|(result['q']>[1.4,.1]))))
except BaseException as exc:report.update(status='FAILED',error=repr(exc),traceback=traceback.format_exc());save();raise
finally:save()
