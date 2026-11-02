"""Reopen a surface-proxy candidate; audit actual geometry at denser subframes."""
import argparse, json, sys, time
from pathlib import Path
import bpy, numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords, regions, audit_frame
from animation_contact_tools.hair_bundle_profile import resolve_bundle
from animation_contact_tools.exact_skin_collider import build_exact_skin_topology
from animation_contact_tools.closed_collider_field import ClosedColliderField
p = argparse.ArgumentParser()
p.add_argument('--run', required=True)
p.add_argument('--first', type=float)
p.add_argument('--last', type=float)
p.add_argument('--step', type=float, default=.125)
p.add_argument('--containment', action='store_true')
a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
out = Path(a.run)
report = json.loads((out / 'report.json').read_text('utf8'))
motion = np.load(out / 'dense_motion.npz')
root_reference=np.load(out/'root_reference.npz') if (out/'root_reference.npz').exists() else None
config = report['setup']['bundle']
profile = json.loads(Path(config['source_profile']).read_text('utf8'))
profile['pairs'] = []
engine('import_export').ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=report['candidate'], load_ui=False, use_scripts=False)
mesh = bpy.data.objects[profile['mesh']]
arm = bpy.data.objects[profile['armature']]
scene = bpy.context.scene
bundle = resolve_bundle(mesh, arm, regions(mesh, arm, profile), config)
if a.containment: skin_ids,skin_faces,skin_meta=build_exact_skin_topology(mesh,arm,profile,triangulate=True)
ids = motion['ids']
np.testing.assert_array_equal(bundle['ids'], ids)
edges = motion['edges']
length = np.linalg.norm(motion['rest_coordinates'][edges[:,0]]-motion['rest_coordinates'][edges[:,1]], axis=1)
valid = length > .0005
inverse = np.linalg.inv(motion['anchor_matrices'])
local = np.einsum('fij,fvj->fvi', inverse[:,:3,:3], motion['coordinates']) + inverse[:,None,:3,3]
hard = motion['pinned']
first = report['frames'][0] if a.first is None else a.first
last = report['frames'][1] if a.last is None else a.last
if not report['frames'][0] <= first <= last <= report['frames'][1] or a.step <= 0:
    raise ValueError('Audit interval must lie within the generated cache')
rows = []
start = time.monotonic()
for k, frame in enumerate(np.arange(first, last+.00001, a.step)):
    scene.frame_set(int(frame), subframe=frame%1)
    bpy.context.view_layer.update()
    co = coords(mesh)
    audit = audit_frame(mesh, arm, profile, bundle['parts'], hair=True, cap=1000000, coordinates_m=co)
    ratio = np.linalg.norm(co[ids][edges[:,0]]-co[ids][edges[:,1]], axis=1)[valid]/length[valid]
    index = (frame-report['frames'][0])/report['step_frames']
    lo = int(np.floor(index+1e-7)); u = max(0., index-lo)
    expected_local = local[lo]*(1-u) + local[min(lo+1,len(local)-1)]*u
    head = np.array(arm.matrix_world @ arm.pose.bones[config['anchor_bone']].matrix)
    expected = expected_local @ head[:3,:3].T + head[:3,3]
    inside=0;minimum_distance=None
    if a.containment:
        distance,_=ClosedColliderField(co[skin_ids],skin_faces)(co[ids]);inside=int((distance<-.0001).sum());minimum_distance=float(distance.min())
    true_root_error=None
    if root_reference is not None:
        delta=head@np.linalg.inv(root_reference['anchor']);target=root_reference['coordinates'][hard]@delta[:3,:3].T+delta[:3,3]
        true_root_error=float(np.max(np.linalg.norm(co[ids][hard]-target,axis=1)))
    rows.append(dict(frame=float(frame), crossings=audit['ordinary_crossings'],
                     min_edge_ratio=float(ratio.min()), max_edge_ratio=float(ratio.max()),
                     cache_error_m=float(np.max(np.abs(co[ids]-expected))),
                     root_error_m=float(np.max(np.linalg.norm(co[ids][hard]-expected[hard],axis=1))),
                     true_root_error_m=true_root_error,inside_points=inside,min_signed_distance_m=minimum_distance,
                     pairs=[(r['pair'],r['triangle_crossings']) for r in audit['pairs'] if r['triangle_crossings']]))
    if k % 128 == 0:
        print('SURFACE_PROXY_REOPEN', frame, sum(r['crossings']>0 for r in rows), flush=True)
collisions = sum(r['crossings']>0 for r in rows)
strain = sum(r['min_edge_ratio']<.9 or r['max_edge_ratio']>1.1 for r in rows)
error = max(r['cache_error_m'] for r in rows)
contained=sum(r['inside_points']>0 for r in rows)
true_roots=[r['true_root_error_m'] for r in rows if r['true_root_error_m'] is not None]
true_root_error=max(true_roots) if true_roots else None
passed = collisions == strain == contained == 0 and error < 2e-6 and (true_root_error is None or true_root_error<1e-5)
result = dict(status='SELECTED_BUNDLE_REOPEN_SAMPLED_PASS' if passed else 'SURFACE_PROXY_UNRESOLVED',
              selected_bundle_sampled_pass=passed, accepted=False, frames=[first,last],
              step_frames=a.step, sample_count=len(rows), failed_collision_samples=collisions,
              failed_strain_samples=strain, cache_reload_peak_error_m=error,
              containment_checked=a.containment,failed_containment_samples=contained if a.containment else None,
              true_rigid_root_peak_error_m=true_root_error,
              root_peak_error_m=max(r['root_error_m'] for r in rows),
              min_edge_ratio=min(r['min_edge_ratio'] for r in rows),
              max_edge_ratio=max(r['max_edge_ratio'] for r in rows), samples=rows,
              seconds=time.monotonic()-start, ccd_proven=False, all_hair_solved=False,
              containment='actual visible triangles audited; open regions do not prove absence of full containment')
(out/'independent_validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
print('SURFACE_PROXY_REOPEN_COMPLETE', json.dumps({k:v for k,v in result.items() if k!='samples'}), flush=True)
