"""Bounded full-head binding calibration with stock Blender deformations.

No simulation, mesh repair, binding parameter sweep or production correction.
Native Transform Geometry / Simple Deform drive both the existing cage and a
direct reference. The reference includes the cage bounding-box corner markers
so the native bend uses the same limits; markers have no faces and never render.
"""
import argparse,json,sys,time,hashlib,itertools
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);candidate=Path(a.candidate);out=Path(a.out)
out.mkdir(parents=True,exist_ok=True);assert not (out/'result.json').exists(),'Use a fresh benchmark directory'
config=json.loads((candidate/'configuration.json').read_text('utf8'));start=time.monotonic()
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=config['blend'],load_ui=False,use_scripts=False)
s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update()
proxy=bpy.data.objects['HairProxy_全头共享几何体积'];display=bpy.data.objects[s['HairDisplayObject']]
target=bpy.data.objects[config['physics_binding_target']];actor=bpy.data.objects['东雪莲x达妮娅_素体']
# Runtime Cloth is removed before any frame changes. The original files and
# caches are never edited, freed or rebaked.
for md in list(proxy.modifiers):
    if md.type=='CLOTH':proxy.modifiers.remove(md)
bpy.context.view_layer.update()
sd=next(md for md in display.modifiers if md.type=='SURFACE_DEFORM');assert sd.is_bound
binding_settings=dict(target=sd.target.name,strength=sd.strength,falloff=sd.falloff,
    vertex_group=sd.vertex_group,invert_vertex_group=sd.invert_vertex_group)
body_before=coords(actor).copy();base=coords(display).copy();cage0=coords(target).copy();T0=np.array(target.matrix_world)
inv0=np.linalg.inv(T0);cage_local=cage0@inv0[:3,:3].T+inv0[:3,3]
base_local=base@inv0[:3,:3].T+inv0[:3,3];n=len(base)
source_ids=np.array([v.value for v in display.data.attributes['SourceVertexID'].data],np.int32)
base_dir=ROOT.parent/'work/headswap_xl_codex'
hair=np.load(base_dir/'hair_initial_repair_20261030/DELIVER_INITIAL/InitialHairRest.npz')
inspection=np.load(base_dir/'standard_proxy_20261031/inspection/inputs.npz')
source_map={int(v):i for i,v in enumerate(source_ids)}
order=np.array([source_map[int(i)] for i in hair['ids']]);assert n==len(order)==24207
edges=order[hair['edges']];valid=hair['source_edge_lengths']>.0005
hard=np.zeros(n,bool);hard[order[hair['same_true_hard_root_mask']]]=True
labels=np.full(n,-2,np.int32);labels[order]=inspection['chain_labels']
group=display.vertex_groups.get(sd.vertex_group)
weights=np.ones(n) if group is None else np.array([next((g.weight for g in v.groups if g.group==group.index),0.) for v in display.data.vertices])
if sd.invert_vertex_group:weights=1-weights
weights*=sd.strength
assert np.max(weights[hard])<1e-6,'Original fixed roots must remain excluded from binding'
restlength=np.linalg.norm(base[edges[:,0]]-base[edges[:,1]],axis=1)
rest=np.load(candidate/'clump_proxy_rest.npz');pf=rest['triangles']
pe=np.unique(np.sort(np.concatenate([pf[:,[0,1]],pf[:,[1,2]],pf[:,[2,0]]]),axis=1),axis=0)
pl0=np.linalg.norm(cage0[pe[:,0]]-cage0[pe[:,1]],axis=1);pvalid=pl0>.0005
normal0=np.cross(cage_local[pf[:,1]]-cage_local[pf[:,0]],cage_local[pf[:,2]]-cage_local[pf[:,0]])
normal0/=np.linalg.norm(normal0,axis=1)[:,None]
# Native direct-deformation reference, hidden from renders. It has exactly the
# same coordinate frame and bounds as the cage. It never drives the real hair.
ev=display.evaluated_get(bpy.context.evaluated_depsgraph_get())
reference_mesh=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get())
reference=bpy.data.objects.new('Benchmark_DirectReference_AllHair',reference_mesh);s.collection.objects.link(reference)
reference.matrix_world=target.matrix_world.copy();reference.hide_render=True
reference_mesh.vertices.foreach_set('co',base_local.astype(np.float32).ravel())
lo,hi=cage_local.min(0),cage_local.max(0)
assert np.all(base_local.min(0)>=lo-1e-6) and np.all(base_local.max(0)<=hi+1e-6),'Reference hair exceeds common bend bounds'
corners=np.array(list(itertools.product(*zip(lo,hi))))
reference_mesh.vertices.add(8)
all_ref=np.concatenate([base_local,corners]);reference_mesh.vertices.foreach_set('co',all_ref.astype(np.float32).ravel());reference_mesh.update()
def transform_modifier(obj):
    ng=bpy.data.node_groups.new('Benchmark_NativeTransform_'+obj.name,'GeometryNodeTree')
    ng.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    ng.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    inp=ng.nodes.new('NodeGroupInput');tr=ng.nodes.new('GeometryNodeTransform');output=ng.nodes.new('NodeGroupOutput')
    ng.links.new(inp.outputs['Geometry'],tr.inputs['Geometry']);ng.links.new(tr.outputs['Geometry'],output.inputs['Geometry'])
    md=obj.modifiers.new('Benchmark_NativeTransform','NODES');md.node_group=ng
    bend=obj.modifiers.new('Benchmark_NativeBend','SIMPLE_DEFORM');bend.deform_method='BEND';bend.deform_axis='Y';bend.angle=0.
    bend.show_viewport=False;bend.show_render=False
    return tr,bend
controls=[transform_modifier(target),transform_modifier(reference)]
def control(translation=(0,0,0),rotation=(0,0,0),angle=None):
    for tr,bend in controls:
        tr.inputs['Translation'].default_value=translation;tr.inputs['Rotation'].default_value=rotation
        tr.inputs['Scale'].default_value=(1.,1.,1.)
        bend.show_viewport=angle is not None;bend.show_render=angle is not None
        if angle is not None:bend.angle=angle
    bpy.context.view_layer.update()
def summary(x):
    return dict(min=float(np.min(x)),p01=float(np.quantile(x,.01)),p50=float(np.median(x)),
        p99=float(np.quantile(x,.99)),max=float(np.max(x)))
def geometry_metrics(actual,expected,cage):
    lengths=np.linalg.norm(actual[edges[:,0]]-actual[edges[:,1]],axis=1)
    proxy_ratio=np.linalg.norm(cage[pe[:,0]]-cage[pe[:,1]],axis=1)[pvalid]/pl0[pvalid]
    local=cage@inv0[:3,:3].T+inv0[:3,3]
    normals=np.cross(local[pf[:,1]]-local[pf[:,0]],local[pf[:,2]]-local[pf[:,0]])
    normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-30)
    angle=np.rad2deg(np.arccos(np.clip(np.einsum('ij,ij->i',normal0,normals),-1,1)))
    result=dict(display_edge_ratio_from_rest=summary((lengths/restlength)[valid]),
        proxy_edge_ratio_from_rest=summary(proxy_ratio),proxy_face_normal_rotation_deg=summary(angle),
        fixed_root_error_m=float(np.linalg.norm(actual[hard]-base[hard],axis=1).max()))
    if expected is not None:
        error=np.linalg.norm(actual-expected,axis=1);el=np.linalg.norm(expected[edges[:,0]]-expected[edges[:,1]],axis=1)
        excess=lengths/np.maximum(el,1e-20)
        result.update(position_transfer_error_m=summary(error),edge_ratio_to_native_reference=summary(excess[valid]),
            expected_display_edge_ratio_from_rest=summary((el/restlength)[valid]),
            per_clump=[dict(name=c['name'],position_error_m=summary(error[labels==i]),
                edges_above_1_5_reference=int(((excess>1.5)&valid&(labels[edges[:,0]]==i)&(labels[edges[:,1]]==i)).sum()))
                for i,c in enumerate(config['clumps'])])
    return result
rows=[];failure=None
cases=[dict(name='identity'),dict(name='translate_2mm_x',translation=(.002,0,0)),
    dict(name='rotate_3deg_y',rotation=(0,np.deg2rad(3),0)),
    dict(name='bend_plus_5deg',angle=np.deg2rad(5)),dict(name='bend_minus_5deg',angle=np.deg2rad(-5))]
for case in cases:
    control(**{k:v for k,v in case.items() if k!='name'})
    direct=coords(reference)[:n];expected=base+weights[:,None]*(direct-base)
    actual=coords(display);cage=coords(target);row=dict(case,**geometry_metrics(actual,expected,cage))
    # Predetermined diagnostic bounds, not tuned to a test result. Bend permits
    # finite surface interpolation error; affine controls should be exact.
    tolerance=.0001 if 'angle' in case else .000005
    er=row['edge_ratio_to_native_reference'];row['pass']=(row['position_transfer_error_m']['max']<=tolerance
        and er['min']>=.85 and er['max']<=1.15 and row['fixed_root_error_m']<.0001)
    row['position_error_limit_m']=tolerance;rows.append(row)
    np.savez_compressed(out/(case['name']+'.npz'),actual=actual,expected=expected,proxy=cage,source_vertex_ids=source_ids)
    print('BINDING_CONTROL',json.dumps({k:v for k,v in row.items() if k!='per_clump'},ensure_ascii=False),flush=True)
    if not row['pass']:failure=case['name'];break
replay=None
if failure is None:
    control()
    # Read already-computed frame-7 geometry, normalized into the original head
    # frame. Cloth has been removed; this does not compute a new physical frame.
    last=np.load(candidate/'native_last_frame.npz');frame=int(last['frame'])
    s.frame_set(frame);bpy.context.view_layer.update();T7=np.array(target.matrix_world);inv7=np.linalg.inv(T7)
    local7=last['proxy']@inv7[:3,:3].T+inv7[:3,3]
    frozen_order=last['hair'];expected_frozen=frozen_order@inv7[:3,:3].T+inv7[:3,3]
    expected_frozen=expected_frozen@T0[:3,:3].T+T0[:3,3]
    frozen_by_display=np.empty_like(base);frozen_by_display[order]=expected_frozen
    s.frame_set(1);bpy.context.view_layer.update()
    proxy.data.vertices.foreach_set('co',local7.astype(np.float32).ravel());proxy.data.update();bpy.context.view_layer.update()
    actual=coords(display);cage=coords(target)
    replay=dict(source_frame=frame,**geometry_metrics(actual,None,cage),
        cached_display_replay_error_m=float(np.linalg.norm(actual-frozen_by_display,axis=1).max()))
    np.savez_compressed(out/'cached_frame7_replay.npz',actual=actual,expected_cached=frozen_by_display,
        proxy=cage,source_vertex_ids=source_ids)
    print('FROZEN_GEOMETRY_REPLAY',json.dumps(replay,ensure_ascii=False),flush=True)
body_error=float(np.max(np.abs(coords(actor)-body_before)));assert body_error<1e-7
result=dict(status='STOPPED_BINDING_CONTROL_FAILURE' if failure else 'CONTROLS_COMPLETE_FROZEN_REPLAY_REQUIRES_REVIEW',
    failed_control=failure,source=config['blend'],binding_settings=binding_settings,all_27_groups_checked=True,
    displayed_hair_vertices=n,original_fixed_roots=int(hard.sum()),proxy_vertices=len(cage0),
    physics_computed=False,cloth_modifiers_removed_in_diagnostic_copy=True,frames_of_new_physics=0,
    no_binding_parameter_changes=True,body_error_m=body_error,cases=rows,frozen_replay=replay,
    scope='Synthetic full-head binding calibration; synthetic skin contact is not an MMD collision test',
    elapsed_s=time.monotonic()-start,shutdown_forbidden=True)
(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
# Save only the explicit diagnostic copy, never the prepared source or cache.
s['BindingCalibrationOnly']=True;s['BindingCalibrationFailure']=failure or 'known_cached_frame7_replay'
s.frame_end=1;bpy.ops.wm.save_as_mainfile(filepath=str(out/'完整角色_绑定验证_非物理成片.blend'))
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
s.cycles.device='GPU';s.cycles.samples=32;s.cycles.use_denoising=True
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.filepath=str(out/'完整角色_绑定验证画面.png')
bpy.ops.render.render(write_still=True)
print(json.dumps(dict(status=result['status'],failure=failure,normal_image=s.render.filepath),ensure_ascii=False),flush=True)
