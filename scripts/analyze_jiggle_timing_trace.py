"""Compare captured raw points, direct bone writes and replay, without running Blender."""
import json
from pathlib import Path
import numpy as np

ROOT = Path(r'E:\project\mmd\work\headswap_xl_codex\jiggle_timing_trace_20261102')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def unit(value):
    return value / np.maximum(np.linalg.norm(value, axis=-1, keepdims=True), 1e-12)


def angle(a, b):
    return np.degrees(np.arccos(np.clip(np.sum(unit(a) * unit(b), axis=-1), -1, 1)))


results = []
for fps in [30, 120]:
    directory = ROOT / f'{fps}Hz'
    if not (directory / 'trace_result.json').exists():
        print('NOT_READY', fps)
        continue
    mapping = read(directory / 'trace_mapping.json')
    z = np.load(directory / 'pipeline_trace.npz')
    names, particles = mapping['bone_names'], mapping['particles']
    index = {p['bone']: i for i, p in enumerate(particles) if p['kind'] == 'normal'}
    valid = [j for j, n in enumerate(names) if n in index and particles[index[n]]['children']]
    raw = np.full_like(z['immediate_axes'], np.nan)
    positions = z['particle_world']
    rotation = np.linalg.inv(z['immediate_head_world'][:, :3, :3])
    for j in valid:
        i = index[names[j]]
        directions = unit(positions[:, particles[i]['children']] - positions[:, i:i+1])
        raw[:, j] = unit(np.einsum('fij,fj->fi', rotation, directions.mean(axis=1)))
    common = np.flatnonzero(np.abs(z['source_frames'] - np.round(z['source_frames'])) < 1e-6)
    target = common[(z['source_frames'][common] >= 301) & (z['source_frames'][common] <= 391)]
    sample_stages = dict(raw=raw[target], replay=z['replay_axes'][target])
    stages = {}
    for label, axes in sample_stages.items():
        changes = angle(axes[:-1, valid], axes[1:, valid])
        f, j = np.unravel_index(np.argmax(changes), changes.shape)
        stages[label] = dict(largest_axis_swing_deg=float(changes[f, j]), bone=names[valid[j]],
                             source_frames=[float(z['source_frames'][target[f]]), float(z['source_frames'][target[f+1]])],
                             p95_axis_swing_deg=float(np.quantile(changes, .95)))
    # Examine the replay's largest jump at all three stages, plus native-step jumps.
    peak_f, peak_n = stages['replay']['source_frames'], stages['replay']['bone']
    f0, f1 = [int(np.flatnonzero(np.abs(z['source_frames'] - f) < 1e-6)[0]) for f in peak_f]
    j = names.index(peak_n)
    peak_pair = dict(bone=peak_n, source_frames=peak_f,
                     raw_swing_deg=float(angle(raw[f0, j], raw[f1, j])),
                     replay_swing_deg=float(angle(z['replay_axes'][f0, j], z['replay_axes'][f1, j])))
    raw_replay_delta = angle(raw[:, valid], z['replay_axes'][:, valid])
    raw_heads = np.array([positions[:, index[names[j]]] for j in valid]).transpose(1, 0, 2)
    head_error = np.linalg.norm(raw_heads - z['replay_heads'][:, valid], axis=-1)
    native = np.flatnonzero((z['source_frames'] >= 301) & (z['source_frames'] <= 391))
    native_raw_swing = angle(raw[native[:-1]][:, valid], raw[native[1:]][:, valid])
    ni, nj = np.unravel_index(np.argmax(native_raw_swing), native_raw_swing.shape)
    normal_j = valid[nj]
    native_peak = dict(bone=names[normal_j], source_frames=z['source_frames'][native[ni:ni+2]].tolist(),
                       degrees=float(native_raw_swing[ni, nj]))
    row = dict(fps=fps, result=read(directory / 'trace_result.json'), observed_bones=len(valid),
               stages=stages, replay_peak_pair=peak_pair, largest_native_step_raw_swing=native_peak,
               raw_to_replay_axis_error_max_deg=float(raw_replay_delta[1:].max()),
               raw_to_replay_axis_error_p99_deg=float(np.quantile(raw_replay_delta[1:], .99)),
               raw_to_replay_point_error_max_cm=float(head_error[1:].max()*100),
               deferred_pose_read_notice='Immediate/post callback matrices have not undergone Blender dependency evaluation and remain at the input pose; do not treat them as evaluated bone output or transfer errors. Raw points vs fully evaluated replay is the meaningful transfer check.',
               metrics_are_diagnostics_not_naturalness_acceptance=True)
    (directory / 'pipeline_analysis.json').write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding='utf-8')
    np.savez_compressed(directory / 'raw_axes.npz', source_frames=z['source_frames'], raw_axes=raw, valid_bone_indices=valid)
    results.append(row)
    print(json.dumps(row, ensure_ascii=False))
if len(results) == 2:
    fingerprints = [read(ROOT / f'{fps}Hz/input_fingerprint.json') for fps in [30, 120]]
    for key in ['source_file_sha256', 'plugin_source_sha256', 'settings_sha256', 'collider_initial_matrices_sha256']:
        assert fingerprints[0][key] == fingerprints[1][key], (key, 'Comparison is not matched')
    (ROOT / 'pipeline_analysis.json').write_text(json.dumps(dict(cases=results, identical_source_settings_colliders=True,
        no_third_trial_launched=True, scope='10..13s, every integer source frame; native-step raw points also examined'), ensure_ascii=False, indent=2), encoding='utf-8')
