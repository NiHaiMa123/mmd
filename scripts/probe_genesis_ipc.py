"""Measured joint/cloth coupling probe, independent of the character assets.

Run each mode in a separate process. A simulation completing is not a contact
or motion-quality acceptance; compare modes and audit the exported surfaces.
"""
import argparse
import importlib.metadata
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--mode',choices=('free','one_way','two_way'),required=True)
parser.add_argument('--coupling',choices=('two_way_soft_constraint','external_articulation'),default='two_way_soft_constraint')
parser.add_argument('--steps',type=int,default=90)
parser.add_argument('--dt',type=float,default=.01)
parser.add_argument('--layers',type=int,default=1)
parser.add_argument('--pin-top',action='store_true')
parser.add_argument('--margin',type=float,default=.001)
parser.add_argument('--axis-fix',action='store_true')
parser.add_argument('--sync-reference',action='store_true')
parser.add_argument('--native-feedback',action='store_true')
parser.add_argument('--attach-to-arm',action='store_true')
parser.add_argument('--output',default=str(ROOT/'outputs/contact_stack/hinge_cloth'))
args=parser.parse_args()
out=Path(args.output).resolve()/args.mode
out.mkdir(parents=True,exist_ok=True)
runtime=ROOT/'tools/contact_stack/cache'
runtime.mkdir(parents=True,exist_ok=True)
os.environ.setdefault('HF_HOME',str(runtime/'huggingface'))
os.environ.setdefault('TORCH_HOME',str(runtime/'torch'))
os.environ.setdefault('XDG_CACHE_HOME',str(runtime))
report={'status':'PREPARING','mode':args.mode,'coupling_type':args.coupling,'steps_requested':args.steps,'dt_s':args.dt,'layers':0 if args.mode=='free' else args.layers,'scope':'Numerical joint/cloth coupling probe; not MMD or full-system acceptance'}
report['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
def save_report():
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
save_report()

def assets():
    arm=out/'hinge.xml'
    arm.write_text('''<mujoco model="contact_probe"><compiler angle="radian"/><option gravity="0 0 0"/><worldbody>
<body name="base" pos="0 0 0.6"><geom type="box" size="0.035 0.035 0.035" pos="-0.08 0 0"/>
<body name="arm"><joint name="shoulder" type="hinge" axis="0 0 1" range="-0.2 1.3" limited="true" damping="0.05"/>
<geom name="arm_surface" type="box" size="0.30 0.035 0.035" pos="0.30 0 0" density="500"/></body></body>
</worldbody></mujoco>''',encoding='utf-8')
    n=13;vertices=[];faces=[]
    for row in range(n):
        for col in range(n):vertices.append([.6*col/(n-1),.04,.24+.4*row/(n-1)] if args.attach_to_arm else [.12+.54*col/(n-1),.19,.33+.54*row/(n-1)])
    for row in range(n-1):
        for col in range(n-1):
            a=row*n+col;b=a+1;c=a+n;d=c+1
            faces.extend(((a,c,b),(b,c,d)))
    mesh=out/'cloth.obj'
    mesh.write_text('\n'.join(['v '+' '.join(map(str,v)) for v in vertices]+['f '+' '.join(str(i+1) for i in f) for f in faces])+'\n',encoding='utf-8')
    return arm,mesh

try:
    import numpy as np
    import genesis as gs
    import uipc
    if args.mode=='one_way' and args.coupling=='external_articulation':
        raise ValueError('two_way_coupling does not disable joint-state feedback for external_articulation; use a no-cloth control')
    report['versions']={name:importlib.metadata.version(name) for name in ('genesis-world','pyuipc','torch','numpy','quadrants')}
    armfile,meshfile=assets()
    gs.init(backend=gs.cpu,logging_level='warning',precision='64')
    scene=gs.Scene(
        sim_options=gs.options.SimOptions(dt=args.dt,gravity=(0,0,0)),
        coupler_options=gs.options.IPCCouplerOptions(
            two_way_coupling=args.mode!='one_way',
            contact_enable=True,contact_friction_enable=True,
            contact_d_hat=args.margin,contact_resistance=1e8,
            newton_semi_implicit_enable=False,
            constraint_strength_translation=100.,constraint_strength_rotation=100.,
            enable_rigid_rigid_contact=True,sanity_check_enable=True,enable_rigid_dofs_sync=args.sync_reference),
        show_viewer=False)
    material=dict(coup_type=args.coupling)
    if args.coupling=='two_way_soft_constraint':material['coup_links']=('arm',)
    # An MJCF root without a free joint is already fixed to the world.
    arm=scene.add_entity(gs.morphs.MJCF(file=str(armfile)),material=gs.materials.Rigid(**material))
    fabrics=[]
    if args.mode!='free':
        for layer in range(args.layers):
            fabrics.append(scene.add_entity(
                gs.morphs.Mesh(file=str(meshfile),pos=(0,(.008 if args.attach_to_arm else .025)*layer,0)),
                material=gs.materials.FEM.Cloth(E=2e5,nu=.45,rho=800.,thickness=.002,bending_stiffness=2.,friction_mu=.5)))
    pin_ids=[]
    if args.pin_top and fabrics:
        from genesis_ipc_constraints import install_fixed_cloth_pins
        selections={}
        for fabric in fabrics:
            initial=np.asarray(fabric.init_positions)
            selected=np.flatnonzero(initial[:,2]>initial[:,2].max()-1e-6)
            selections[fabric]=selected;pin_ids.append(selected)
        report['pin_adapter']=install_fixed_cloth_pins(scene,selections)
    else:pin_ids=[np.empty(0,dtype=int) for _ in fabrics]
    if args.attach_to_arm and fabrics:
        if args.pin_top:raise ValueError('Moving stitches and world-fixed pins are different constraints')
        from genesis_ipc_constraints import install_cloth_body_stitches
        selections={}
        for fabric in fabrics:
            initial=np.asarray(fabric.init_positions);top=np.flatnonzero(initial[:,2]>initial[:,2].max()-1e-6)
            selections[fabric]=np.array([top[np.argmin(initial[top,0])],top[np.argmax(initial[top,0])]])
        report['moving_attachments']=install_cloth_body_stitches(scene,selections,arm.get_link('arm'))
    if args.axis_fix:
        from genesis_ipc_constraints import install_revolute_axis_adapter
        report['axis_adapter']=install_revolute_axis_adapter(scene)
    report['reference_sync']=args.sync_reference
    report['status']='BUILDING';save_report()
    begin=time.perf_counter();scene.build(n_envs=1)
    report['build_seconds']=time.perf_counter()-begin
    if arm.n_dofs!=1:raise RuntimeError(f'Probe expected one hinge DOF, got {arm.n_dofs}')
    if args.native_feedback:
        from genesis_ipc_constraints import install_native_revolute_feedback
        report['native_feedback_adapter']=install_native_revolute_feedback(scene)
    arm.set_dofs_kp(np.array([3.]));arm.set_dofs_kv(np.array([.3]));arm.set_dofs_force_range(np.array([-2.]),np.array([2.]))
    link=arm.get_link('arm')
    def array(value):
        if hasattr(value,'detach'):value=value.detach().cpu().numpy()
        return np.asarray(value)
    corners=np.array([[x,y,z] for x in (0.,.6) for y in (-.035,.035) for z in (-.035,.035)])
    # Local corner numbering is stable across all three modes.
    arm_faces=np.array([(0,1,3),(0,3,2),(4,6,7),(4,7,5),(0,4,5),(0,5,1),(2,3,7),(2,7,6),(0,2,6),(0,6,4),(1,5,7),(1,7,3)],dtype=np.int32)
    def skin():
        p=array(link.get_pos()).reshape(-1,3)[0];w,x,y,z=array(link.get_quat()).reshape(-1,4)[0]
        rot=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
        return corners@rot.T+p
    native_slot=scene.sim.coupler._abd_slots_by_link[link][0]
    native_geom=native_slot.geometry()
    native_faces=np.asarray(native_geom.triangles().topo().view()).reshape(-1,3).copy()
    surface_mask=native_geom.triangles().find(uipc.builtin.is_surf)
    if surface_mask is not None:native_faces=native_faces[np.asarray(surface_mask.view()).reshape(-1)>0]
    def native_skin():
        co=np.asarray(native_geom.positions().view()).reshape(-1,3)
        # Scene instance transforms can be stale after an ABD step. Read the
        # backend state accessor used by the Genesis coupler itself instead.
        coupler=scene.sim.coupler
        if len(q)>1:
            index=list(coupler._abd_slots_by_link).index(link)
            transform=np.asarray(coupler._abd_state_geom.instances().find(uipc.builtin.transform).view())[index]
        else:transform=np.asarray(native_geom.transforms().view()).reshape(-1,4,4)[0]
        return co@transform[:3,:3].T+transform[:3,3]
    q=[];targets=[];arm_coords=[];native_coords=[];cloth_coords=[[] for _ in fabrics];feedback_forces=[];feedback_torques=[]
    def record(target):
        q.append(float(array(arm.get_dofs_position()).reshape(-1)[0]));targets.append(target);arm_coords.append(skin());native_coords.append(native_skin().copy())
        for j,fabric in enumerate(fabrics):cloth_coords[j].append(array(fabric.get_state().pos).reshape(-1,3).copy())
        # Version-pinned diagnostic adapter, not a public Genesis interface.
        # Arrays are initialized by the first coupling step, not at frame 0.
        data=scene.sim.coupler._coupling_data
        if args.mode!='one_way' and len(q)>1 and data is not None and link in data.link_to_idx_local:
            index=data.link_to_idx_local[link]
            feedback_forces.append(data.out_forces[0,index].copy());feedback_torques.append(data.out_torques[0,index].copy())
        else:feedback_forces.append(np.zeros(3));feedback_torques.append(np.zeros(3))
    report.update(status='RUNNING',cloth_vertices=[f.n_vertices for f in fabrics],cloth_pins=sum(map(len,pin_ids)),cloth_is_free=not(args.pin_top or args.attach_to_arm),contact_enabled=True,friction_enabled=True,contact_margin_m=args.margin,feedback_mechanism='joint_state' if args.coupling=='external_articulation' else 'force_torque',native_state_source='AffineBodyStateAccessorFeature')
    save_report();record(0.);begin=time.perf_counter()
    for step in range(args.steps):
        t=min((step+1)*args.dt/.65,1.);target=.95*t*t*(3-2*t)
        arm.control_dofs_position(np.array([target]));scene.step();record(target)
        if (step+1)%15==0:print('GENESIS_IPC_STEP',args.mode,step+1,q[-1],flush=True)
    saved=dict(q_rad=np.asarray(q),target_rad=np.asarray(targets),arm=np.asarray(arm_coords),arm_faces=arm_faces,ipc_arm=np.asarray(native_coords),ipc_arm_faces=native_faces,time_s=np.arange(len(q))*args.dt,feedback_force_n=np.asarray(feedback_forces),feedback_torque_nm=np.asarray(feedback_torques))
    for j,fabric in enumerate(fabrics):
        saved[f'cloth_{j}']=np.asarray(cloth_coords[j]);saved[f'cloth_faces_{j}']=np.asarray(fabric.surface_triangles);saved[f'cloth_pins_{j}']=pin_ids[j]
    if not all(np.isfinite(v).all() for v in saved.values()):raise RuntimeError('Nonfinite simulation output')
    np.savez_compressed(out/'trajectory.npz',**saved)
    report.update(status='NUMERICAL_RUN_COMPLETE_REQUIRES_CONTACT_AUDIT',seconds=time.perf_counter()-begin,frames=len(q),q_final_rad=q[-1],q_max_rad=max(q),target_final_rad=targets[-1],max_target_error_rad=float(np.max(np.abs(np.array(q)-targets))))
    print('GENESIS_IPC_RUN_COMPLETE',args.mode,report['seconds'],q[-1],flush=True)
except BaseException as exc:
    report.update(status='FAILED',error=repr(exc),traceback=traceback.format_exc())
    save_report()
    raise
finally:
    save_report()
