"""Read-only geometric and skinning extent of the current fixed root segments."""
import json
import sys
from pathlib import Path
import bpy
import numpy as np

REPO = Path(__file__).resolve().parents[1]
BASE = REPO.parent / 'work/headswap_xl_codex'
OUT = BASE / 'jiggle_free_motion_20261102'
sys.path.insert(0, str(REPO / 'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
engine('import_export').ensure_mmd_tools()
config = json.loads((OUT / 'configuration.json').read_text(encoding='utf-8'))
enabled = {r['name']: r['enabled'] for r in config['settings']}
meta = json.loads((BASE / 'standard_proxy_20261031/inspection/inputs.json').read_text(encoding='utf-8'))
data = np.load(BASE / 'standard_proxy_20261031/inspection/inputs.npz')
bpy.ops.wm.open_mainfile(filepath=config['source'], load_ui=False, use_scripts=False)
assert not any('jiggle' in getattr(fn, '__module__', '').lower() for fn in bpy.app.handlers.frame_change_post)
scene = bpy.context.scene
scene.frame_set(1)
bpy.context.view_layer.update()
actor = bpy.data.objects['东雪莲x达妮娅_素体']
arm = actor.find_armature()
co = coords(actor)
group_names = {g.index: g.name for g in actor.vertex_groups}
deform = {b.name for b in arm.data.bones if b.use_deform}
dynamic = {n for n, value in enabled.items() if value}
rows = []
for j, chain in enumerate(meta['chains']):
    names = chain['bones']
    heads = np.array([arm.matrix_world @ arm.pose.bones[n].head for n in names])
    last_tail = np.array(arm.matrix_world @ arm.pose.bones[names[-1]].tail)
    path = np.concatenate([heads, last_tail[None]])
    lengths = np.linalg.norm(np.diff(path, axis=0), axis=1)
    first = next((i for i, n in enumerate(names) if enabled[n]), len(names))
    total = float(lengths.sum())
    fixed = float(lengths[:first].sum())
    selected = data['ids'][data['chain_labels'] == j]
    rigid_weights = []
    for i in selected:
        weights = [(group_names[g.group], g.weight) for g in actor.data.vertices[int(i)].groups if group_names[g.group] in deform]
        den = sum(w for _, w in weights)
        moving = sum(w for n, w in weights if n in dynamic)
        rigid_weights.append(1-moving/den if den else 1.)
    rigid_weights = np.array(rigid_weights)
    rows.append(dict(chain=chain['name'], bones=len(names), fixed_bones=names[:first],
                     first_dynamic_bone=names[first] if first < len(names) else None,
                     root_to_first_dynamic_head_cm=fixed*100, full_bone_path_cm=total*100,
                     fixed_path_fraction=fixed/total if total else None,
                     bone_path_segment_lengths_cm=(lengths*100).tolist(),
                     display_vertices=len(selected), nearly_rigid_vertex_fraction=float(np.mean(rigid_weights>.99)),
                     mean_fixed_deform_weight=float(rigid_weights.mean()),
                     fixed_segment_world_points=path[:first+1].tolist()))
rear = list(range(7,23))+[25,26]
summary = dict(
    mode='READ_ONLY_NO_SIMULATION_OR_RENDER', chains=rows, rear_chain_count=len(rear),
    rear_fixed_length_cm_range=[min(rows[j]['root_to_first_dynamic_head_cm'] for j in rear), max(rows[j]['root_to_first_dynamic_head_cm'] for j in rear)],
    rear_fixed_length_cm_median=float(np.median([rows[j]['root_to_first_dynamic_head_cm'] for j in rear])),
    rear_fixed_path_fraction_range=[min(rows[j]['fixed_path_fraction'] for j in rear), max(rows[j]['fixed_path_fraction'] for j in rear)],
    rear_fixed_path_fraction_median=float(np.median([rows[j]['fixed_path_fraction'] for j in rear])),
    note='Length follows posed deform-bone heads and last tail; skinning rigid fraction uses total non-dynamic deform weights. This measures fixed extent, not a causal naturalness pass.')
(OUT / 'fixed_root_extent.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print('FIXED_ROOT_EXTENT', json.dumps({k:v for k,v in summary.items() if k != 'chains'},ensure_ascii=False),flush=True)
