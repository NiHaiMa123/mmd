"""Read actual full-head meshes and render normal keyframes from the two baked traces."""
import json
import runpy
import sys
from pathlib import Path
import bpy
import numpy as np

REPO = Path(__file__).resolve().parents[1]
BASE = REPO.parent / 'work/headswap_xl_codex'
ROOT = BASE / 'jiggle_timing_trace_20261102'
sys.path.insert(0, str(REPO / 'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
engine('import_export').ensure_mmd_tools()
meta = json.loads((BASE / 'standard_proxy_20261031/inspection/inputs.json').read_text(encoding='utf-8'))
data = np.load(BASE / 'standard_proxy_20261031/inspection/inputs.npz')
ids, edges, labels = data['ids'], data['edges'], data['chain_labels']
bpy.ops.wm.open_mainfile(filepath=str(BASE / 'jiggle_naturalness_fix_20261102/B_smaller_radius/完整角色_Jiggle配置_未烘焙.blend'), load_ui=False, use_scripts=False)
scene = bpy.context.scene
scene.frame_set(1)
bpy.context.view_layer.update()
actor = bpy.data.objects['东雪莲x达妮娅_素体']
initial = coords(actor)
origin = np.array(actor.find_armature().matrix_world @ actor.find_armature().pose.bones['頭'].head)
tips = []
for label in range(27):
    selected = ids[labels == label]
    radii = np.linalg.norm(initial[selected] - origin, axis=1)
    tips.append(selected[radii >= np.quantile(radii, .8)])
rest = np.linalg.norm(initial[ids[edges[:, 0]]] - initial[ids[edges[:, 1]]], axis=1)
valid = rest > .001
chain_edges = [np.flatnonzero((labels[edges[:, 0]] == j) & (labels[edges[:, 1]] == j) & valid) for j in range(27)]
results = []
for fps in [30, 120]:
    folder = ROOT / f'{fps}Hz'
    source = json.loads((folder / 'bake_report.json').read_text(encoding='utf-8'))['blend']
    bpy.ops.wm.open_mainfile(filepath=source, load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    actor = bpy.data.objects['东雪莲x达妮娅_素体']
    arm = actor.find_armature()
    motion, strain = [], []
    for f in range(1, 392):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        co = coords(actor)
        assert np.isfinite(co).all(), (fps, f, 'Nonfinite geometry')
        h = np.linalg.inv(np.array(arm.matrix_world @ arm.pose.bones['頭'].matrix))
        world = np.array([co[t].mean(0) for t in tips])
        motion.append(world @ h[:3, :3].T + h[:3, 3])
        length = np.linalg.norm(co[ids[edges[:, 0]]] - co[ids[edges[:, 1]]], axis=1)
        ratio = np.ones(len(rest))
        ratio[valid] = length[valid] / rest[valid]
        flags = [dict(chain=meta['chains'][j]['name'], p99=float(np.quantile(ratio[e], .99)),
                      maximum_edge_growth_cm=float((length[e] - rest[e]).max()*100))
                 for j, e in enumerate(chain_edges) if len(e) and np.quantile(ratio[e], .99) > 1.5 and (length[e] - rest[e]).max() > .02]
        if flags:
            strain.append(dict(frame=f, chains=flags))
    motion = np.array(motion)
    q = motion[300:391]
    steps = np.linalg.norm(np.diff(q, axis=0), axis=2)*100
    i, j = np.unravel_index(np.argmax(steps), steps.shape)
    rear = list(range(7, 23)) + [25, 26]
    rms = np.sqrt(np.mean(np.sum((q - q.mean(0))**2, axis=2), axis=0))*100
    result = dict(fps=fps, full_head_chains=27, actual_mesh_frames=[1, 391], largest_tip_step_cm=float(steps[i, j]),
                  largest_tip_step_frames=[301+int(i), 302+int(i)], chain=meta['chains'][j]['name'],
                  rear_tip_rms_cm_median=float(np.median(rms[rear])), strain_flags=strain,
                  strain_flag_frame_count=len(strain), motion_is_not_intrusion_depth=True)
    (folder / 'mesh_review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    np.savez_compressed(folder / 'actual_tip_motion.npz', source_frames=np.arange(1, 392), tip_head_local=motion)
    results.append(result)
    print('ACTUAL_MESH_REVIEW', json.dumps(result, ensure_ascii=False), flush=True)
(ROOT / 'mesh_review.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
for fps, frames in [(30, '331,362,363,376'), (120, '331,343,344,376')]:
    folder = ROOT / f'{fps}Hz'
    source = json.loads((folder / 'bake_report.json').read_text(encoding='utf-8'))['blend']
    sys.argv = [str(REPO / 'scripts/render_full_hair_showcase.py'), '--', '--source', source,
                '--out', str(folder / 'keyframes'), '--frames', frames, '--samples', '24', '--device', 'GPU']
    runpy.run_path(str(REPO / 'scripts/render_full_hair_showcase.py'), run_name='__main__')
