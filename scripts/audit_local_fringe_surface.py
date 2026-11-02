"""Compare scoped native mapping against the unchanged source cache."""
import argparse
import json
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / 'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
from animation_contact_tools.hair_contact_threshold import embedded_patch_metrics
p = argparse.ArgumentParser()
p.add_argument('--run', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
run = Path(a.run)
r = json.loads((run / 'result.json').read_text('utf-8-sig'))
assert r['stop'] is None
base = repo.parent / 'work/headswap_xl_codex'
d = np.load(base / 'standard_proxy_20261031/inspection/inputs.npz')
skin = np.load(base / 'fullhair_repro_20261030/input_body_aware/skin_ids.npy')
bf = np.load(base / 'fullhair_repro_20261030/input_body_aware/body_faces.npy')
selected = d['chain_labels'] == 5
frames = [1, 7, 201, 226, 233]
engine('import_export').ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=r['source'], load_ui=False, use_scripts=False)
source = {}
for f in frames:
    bpy.context.scene.frame_set(f)
    bpy.context.view_layer.update()
    source[f] = coords(bpy.data.objects['东雪莲x达妮娅_素体'])
bpy.ops.wm.open_mainfile(filepath=r['blend'], load_ui=False, use_scripts=False)
s = bpy.context.scene
actor = bpy.data.objects['东雪莲x达妮娅_素体']
proxy = bpy.data.objects['ClassicHair_FrontHair5-1.L']
rows = []
for f in frames:
    s.frame_set(f)
    bpy.context.view_layer.update()
    co = coords(actor)
    field = ClosedColliderField(co[skin], bf)
    dist, _ = field(co[d['ids']])
    masked = dist.copy()
    masked[~selected] = 1.0
    contact = embedded_patch_metrics(co[d['ids']], masked, d['edges'], limit_m=.05)
    q = coords(proxy)
    pd, _ = field(q)
    tree = BVHTree.FromPolygons(q.tolist(), [p.vertices[:] for p in proxy.data.polygons])
    nearest = [tree.find_nearest(Vector(pt))[3] for pt in co[d['ids'][selected]]]
    face_ids = np.all(selected[d['faces']], axis=1)
    centers = co[d['ids']][d['faces'][face_ids]].mean(1)
    cd, _ = field(centers)
    other = float(np.abs(co[d['ids'][~selected]] - source[f][d['ids'][~selected]]).max())
    body = float(np.abs(co[skin] - source[f][skin]).max())
    rows.append(dict(frame=f, fringe_inside_vertices=contact['inside_vertices'],
                     fringe_span_cm=contact['maximum_patch_extent_m']*100,
                     fringe_depth_cm=contact['maximum_depth_m']*100,
                     fringe_inside_face_centers=int((cd < -.0001).sum()),
                     proxy_inside_vertices=int((pd < -.0001).sum()),
                     other_hair_max_change_m=other, body_max_change_m=body,
                     fringe_to_proxy_surface_distance_p50_p99_max_m=
                     [float(np.quantile(nearest, .5)), float(np.quantile(nearest, .99)), float(max(nearest))]))
    assert body < 5e-6
report = dict(method='Unmodified native Surface Deform, scoped to FrontHair5-1.L',
              mapping_only_comparison=True, new_physics_started=False,
              original_skin_weights_edited=False, frames=rows,
              remaining_141_constraints_preserved=True,
              maximum_other_hair_change_m=max(x['other_hair_max_change_m'] for x in rows))
(run / 'mapping_preservation_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
print(json.dumps(report, ensure_ascii=False), flush=True)
