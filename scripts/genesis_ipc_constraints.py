"""Version-pinned pin bridge for Genesis 1.4.5 and pyuipc 0.0.29.

The public FEM pin setter rejects IPC. This adapter acts on only one coupler
instance while its FEM geometries are created, before native world.init().
It uses libuipc's fixed-vertex attribute, leaves contacts enabled, and never
modifies vendor files. These are world-fixed test pins, not animated garment
attachments or an assertion that full MMD coupling is implemented.
"""
import importlib.metadata
import numpy as np


def install_persistent_hand_contact(scene, left, right, strength=1e6):
    """Preserve a declared hand-contact phase using a native relative pose joint.

    This is a known, persistent contact interval, not automatic gesture detection.
    Collision response remains enabled; the skeleton motors may yield instead.
    Creating/releasing contacts during an animation needs a separate phase API.
    """
    from uipc.constitution import AffineBodyFixedJoint
    if (importlib.metadata.version('genesis-world'),importlib.metadata.version('pyuipc'))!=('1.4.5','0.0.29'):
        raise RuntimeError('Hand-contact bridge requires runtime revalidation')
    coupler=scene.sim.coupler;original=coupler._add_objects_to_ipc
    report={'status':'PENDING_BUILD','kind':'declared persistent relative hand pose',
            'automatic_gesture_detection':False,'contact_exemptions':0,'strength_ratio':strength}
    def create_contact():
        try:
            original()
            joint=AffineBodyFixedJoint();coupler._ipc_constitution_tabular.insert(joint)
            left_slots=list(coupler._abd_slots_by_link[left]);right_slots=list(coupler._abd_slots_by_link[right])
            if len(left_slots)!=1 or len(right_slots)!=1:raise ValueError('Validate one environment first')
            geom=joint.create_geometry(left_slots,np.array([0],dtype=np.int32),right_slots,np.array([0],dtype=np.int32),np.array([strength],dtype=np.float64))
            coupler._ipc_objects.create('declared_hand_contact').geometries().create(geom)
            report['status']='INSTALLED_BEFORE_NATIVE_INIT'
        finally:coupler._add_objects_to_ipc=original
    coupler._add_objects_to_ipc=create_contact
    return report


def install_cloth_body_stitches(scene, selections, link, stiffness=1e6):
    """Attach explicit cloth vertices to native moving-body surface vertices.

    Each spring keeps its measured nonzero initial separation; body/cloth
    contacts remain enabled. Native constraints couple both ends in one solve,
    rather than chasing a previous-frame attachment target.
    """
    import uipc
    from uipc.backend import SceneVisitor
    from uipc.constitution import SoftVertexStitch
    from genesis.engine.couplers.ipc_coupler.utils import read_ipc_geometry_metadata
    if (importlib.metadata.version('genesis-world'),importlib.metadata.version('pyuipc'))!=('1.4.5','0.0.29'):
        raise RuntimeError('Stitch bridge requires runtime revalidation')
    coupler=scene.sim.coupler;entities=list(coupler.fem_solver.entities)
    by_index={entities.index(entity):np.asarray(ids,dtype=int) for entity,ids in selections.items()}
    original=coupler._add_objects_to_ipc
    report={'status':'PENDING_BUILD','kind':'native cloth-body spring stitches','contact_exemptions':0,'entries':[]}
    def create_stitches():
        try:
            original()
            stitch=SoftVertexStitch();coupler._ipc_constitution_tabular.insert(stitch)
            native_slots=coupler._abd_slots_by_link[link]
            # Creating stitch geometries grows the scene's underlying vector.
            # Snapshot slots before mutation so no native span is invalidated.
            for slot in list(SceneVisitor(coupler._ipc_scene).geometries()):
                mesh=slot.geometry();metadata=read_ipc_geometry_metadata(mesh)
                if metadata is None or metadata[0]!='cloth' or metadata[2] not in by_index:continue
                _,env,index=metadata;body_slot=native_slots[env];body=body_slot.geometry()
                co=np.asarray(body.positions().view()).reshape(-1,3);matrix=np.asarray(body.transforms().view())[0];co=co@matrix[:3,:3].T+matrix[:3,3]
                cloth=np.asarray(mesh.positions().view()).reshape(-1,3)
                for vertex in by_index[index]:
                    target=int(np.argmin(np.linalg.norm(co-cloth[vertex],axis=1)));length=float(np.linalg.norm(co[target]-cloth[vertex]))
                    if length<.002:raise ValueError('Attach outside contact thickness, not at intersecting coincident vertices')
                    geom=stitch.create_geometry((slot,body_slot),np.array([[vertex,target]],dtype=np.int32),kappa=stiffness,rest_length=length)
                    coupler._ipc_objects.create(f'cloth_body_attachment_{index}_{env}_{vertex}').geometries().create(geom)
                    report['entries'].append({'cloth_entity_index':index,'cloth_vertex':int(vertex),'body_vertex':target,'rest_length_m':length,'stiffness':stiffness})
            if len(report['entries'])!=scene.sim._B*sum(map(len,by_index.values())):raise RuntimeError('Not every attachment was created')
            report['status']='INSTALLED_BEFORE_NATIVE_INIT'
        finally:coupler._add_objects_to_ipc=original
    coupler._add_objects_to_ipc=create_stitches
    return report


def install_native_revolute_feedback(scene):
    """Recover fixed-base revolute chains from the same native state as cloth.

    No mesh vertices or bone lengths are modified. Joint limits are not
    post-clamped (which could introduce collisions); verify feasibility after
    simulation. Unsupported joint topologies fail explicitly.
    """
    import genesis as gs
    import uipc
    from genesis.utils.misc import qd_to_numpy
    from genesis.engine.couplers.ipc_coupler.utils import find_target_link_for_fixed_merge
    if (importlib.metadata.version('genesis-world'),importlib.metadata.version('pyuipc'))!=('1.4.5','0.0.29'):
        raise RuntimeError('Native feedback bridge requires runtime revalidation')
    coupler=scene.sim.coupler
    if not coupler._articulation_data_by_entity:raise ValueError('Build an external articulation before installing native feedback')
    if scene.sim._B!=1:raise ValueError('Feedback bridge currently validates one environment')
    if scene.sim._requires_grad:raise ValueError('The reordered step has no validated backward implementation')
    if any(entity.n_dofs and entity not in coupler._articulation_data_by_entity for entity in coupler.rigid_solver.entities):
        raise ValueError('Every dynamic rigid entity must use external articulation in this stepper')
    links=list(coupler._abd_slots_by_link)
    initial={link:np.array(coupler._abd_slots_by_link[link][0].geometry().transforms().view()[0]) for link in links}
    axes=qd_to_numpy(coupler.rigid_solver.dyn_state.joints.xaxis,transpose=True)
    def array(tensor):return tensor.detach().cpu().numpy() if hasattr(tensor,'detach') else np.asarray(tensor)
    plans=[]
    for entity,articulation in coupler._articulation_data_by_entity.items():
        if not entity.base_link.is_fixed:raise ValueError('Floating bases require a separately validated bridge')
        rest=array(entity.get_qpos()).reshape(-1).copy();joints=[]
        for joint in entity.joints:
            if joint.type==gs.JOINT_TYPE.FIXED:continue
            if joint.type!=gs.JOINT_TYPE.REVOLUTE:raise ValueError('Only revolute joints are supported')
            child=joint.link;parent=entity.links[max(child.parent_idx,0)-entity.link_start];parent=find_target_link_for_fixed_merge(parent)
            if parent not in initial or child not in initial:raise ValueError('Every joint parent/child needs native geometry')
            axis=initial[parent][:3,:3].T@axes[0,joint.idx];axis/=np.linalg.norm(axis)
            relative=initial[parent][:3,:3].T@initial[child][:3,:3]
            joints.append((parent,child,int(joint.qs_idx_local[0]),axis,relative))
        plans.append((entity,articulation,rest,joints,rest.copy()))
    report={'status':'INSTALLED','supported':'one environment, fixed-base revolute chains','joints':sum(len(p[3]) for p in plans),'steps':0,'max_rotation_axis_residual':0.,'step_order':'motor prediction -> native contact -> same-time joint state; no post-contact second integration'}
    def rotation(matrix):
        u,_,vt=np.linalg.svd(matrix);r=u@vt
        if np.linalg.det(r)<0:u[:,-1]*=-1;r=u@vt
        return r
    def apply_feedback():
        transforms=np.asarray(coupler._abd_state_geom.instances().find(uipc.builtin.transform).view())
        native={link:transforms[i].copy() for i,link in enumerate(links)}
        for entity,ad,rest,joints,previous in plans:
            q=rest.copy()
            for parent,child,index,axis,relative0 in joints:
                relative=rotation(native[parent][:3,:3]).T@rotation(native[child][:3,:3])
                delta=relative@relative0.T
                skew=np.array([delta[2,1]-delta[1,2],delta[0,2]-delta[2,0],delta[1,0]-delta[0,1]])*.5
                angle=float(np.arctan2(np.dot(axis,skew),np.clip((np.trace(delta)-1)*.5,-1,1)))
                value=rest[index]+angle;value+=2*np.pi*round((previous[index]-value)/(2*np.pi));q[index]=value
                report['max_rotation_axis_residual']=max(report['max_rotation_axis_residual'],float(np.linalg.norm(skew-axis*np.dot(axis,skew))))
            velocity=(q-previous)/scene.sim.substep_dt
            coupler.rigid_solver.set_qpos(q[None] if scene.n_envs>0 else q,qs_idx=slice(entity.q_start,entity.q_end),skip_forward=False)
            coupler.rigid_solver.set_dofs_velocity(velocity[None] if scene.n_envs>0 else velocity,dofs_idx=slice(entity.dof_start,entity.dof_end),skip_forward=False)
            ad.qpos_new[:]=q;ad.ref_dof_prev[:]=q;previous[:]=q
            for child,history in zip(ad.joints_child_link,ad.prev_links_transform):history[0]=native[child].copy()
        report['steps']+=1
    coupler._post_advance_external_articulation=apply_feedback
    # The upstream IPC path advances the rigid solver AFTER IPC, so the
    # exposed rigid pose is already the next prediction while cloth is current.
    # For this all-articulated scene predict before IPC, then keep its result.
    def predict_before_contact(frame):
        coupler.rigid_solver.substep(frame)
        coupler.rigid_solver.update_forward_pos()
    def keep_contact_result(frame):
        pass
    coupler.rigid_solver.substep_pre_coupling=predict_before_contact
    coupler.rigid_solver.substep_post_coupling=keep_contact_result
    return report


def install_revolute_axis_adapter(scene):
    """Prototype compatibility adapter for the measured opposite-axis case.

    Applies only to all-revolute/fixed test rigs with these pinned versions.
    Restore both the native factory and instance method immediately after
    scene construction. It is not a general joint-convention conversion.
    """
    import genesis as gs
    import uipc
    if (importlib.metadata.version('genesis-world'),importlib.metadata.version('pyuipc'))!=('1.4.5','0.0.29'):
        raise RuntimeError('Axis adapter requires runtime revalidation')
    coupler=scene.sim.coupler
    if any(joint.type not in (gs.JOINT_TYPE.FIXED,gs.JOINT_TYPE.REVOLUTE) for entity in coupler.rigid_solver.entities for joint in entity.joints):
        raise ValueError('Axis adapter currently supports fixed-base revolute-only probes')
    original=coupler._add_articulation_entities_to_ipc
    factory=uipc.geometry.linemesh
    report={'status':'PENDING_BUILD','reversed_revolute_axes':0,'scope':'version-pinned compatibility experiment'}
    def directed_axis(vertices,edges):
        vertices=np.asarray(vertices);edges=np.asarray(edges)
        if vertices.shape!=(2,3) or edges.shape!=(1,2):raise ValueError('Unexpected articulation axis geometry')
        report['reversed_revolute_axes']+=1
        return factory(vertices[::-1].copy(),edges)
    def build_axes():
        uipc.geometry.linemesh=directed_axis
        try:
            original();report['status']='INSTALLED_BEFORE_NATIVE_INIT'
        finally:
            uipc.geometry.linemesh=factory
            coupler._add_articulation_entities_to_ipc=original
    coupler._add_articulation_entities_to_ipc=build_axes
    return report


def install_fixed_cloth_pins(scene, selections):
    import uipc
    from uipc.backend import SceneVisitor
    from genesis.engine.couplers.ipc_coupler.utils import read_ipc_geometry_metadata
    if (importlib.metadata.version('genesis-world'),importlib.metadata.version('pyuipc'))!=('1.4.5','0.0.29'):
        raise RuntimeError('Pin bridge must be revalidated for this runtime version')
    coupler=scene.sim.coupler
    entities=list(coupler.fem_solver.entities)
    by_index={entities.index(entity):np.asarray(ids,dtype=int) for entity,ids in selections.items()}
    report={'status':'PENDING_BUILD','kind':'world-fixed vertices in the native IPC scene','entities':{}}
    original=coupler._add_fem_entities_to_ipc

    def build_with_pins():
        try:
            original()
            visitor=SceneVisitor(coupler._ipc_scene)
            touched=set()
            for which,slots in (('current',visitor.geometries()),('rest',visitor.rest_geometries())):
                for slot in slots:
                    geometry=slot.geometry();metadata=read_ipc_geometry_metadata(geometry)
                    if metadata is None or metadata[0]!='cloth' or metadata[2] not in by_index:continue
                    _,env,index=metadata;ids=by_index[index]
                    size=len(geometry.positions().view())
                    if not len(ids) or ids.min()<0 or ids.max()>=size:raise ValueError('Invalid IPC cloth fixed-vertex selection')
                    fixed=geometry.vertices().find(uipc.builtin.is_fixed)
                    if fixed is None:fixed=geometry.vertices().create(uipc.builtin.is_fixed,0)
                    uipc.view(fixed).reshape(-1)[ids]=1
                    touched.add((which,env,index))
                    report['entities'][str(index)]={'pins':len(ids),'ids':ids.tolist()}
            if len(touched)!=2*scene.sim._B*len(by_index):raise RuntimeError('Not every current/rest cloth geometry received its pins')
            report['status']='INSTALLED_BEFORE_NATIVE_INIT'
        finally:
            coupler._add_fem_entities_to_ipc=original
    coupler._add_fem_entities_to_ipc=build_with_pins
    return report
