"""Observe the unmodified upstream bake at a specified FPS, without changing its solve."""
import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import time
import traceback
from pathlib import Path

import bpy
import numpy as np

REPO = Path(__file__).resolve().parents[1]
BASE = REPO.parent / 'work/headswap_xl_codex'
sys.path.insert(0, str(REPO / 'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords

parser = argparse.ArgumentParser()
parser.add_argument('--out', required=True)
parser.add_argument('--fps', type=int, choices=[30, 120], required=True)
parser.add_argument('--last', type=int, default=391)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
assert not (out / 'trace_result.json').exists(), 'Existing result preserved'
started = time.monotonic()


def write(name, value):
    (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def status(stage, **kwargs):
    row = dict(stage=stage, elapsed_s=time.monotonic() - started, **kwargs)
    write('status.json', row)
    print('TIMING_TRACE', json.dumps(row, ensure_ascii=False), flush=True)


def curves(action):
    return [c for layer in action.layers for strip in layer.strips
            for bag in getattr(strip, 'channelbags', []) for c in bag.fcurves]


def retime(curve, factor):
    for point in curve.keyframe_points:
        point.co.x = 1 + (point.co.x - 1) * factor
        point.handle_left.x = 1 + (point.handle_left.x - 1) * factor
        point.handle_right.x = 1 + (point.handle_right.x - 1) * factor
    curve.update()


try:
    status('LOADING_IDENTICAL_PREPARED_FULL_HEAD')
    engine('import_export').ensure_mmd_tools()
    source_dir = BASE / 'jiggle_naturalness_fix_20261102/B_smaller_radius'
    config = json.loads((source_dir / 'configuration.json').read_text(encoding='utf-8'))
    source = source_dir / '完整角色_Jiggle配置_未烘焙.blend'
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    actor = bpy.data.objects['东雪莲x达妮娅_素体']
    arm = actor.find_armature()
    plugin_path = Path(config['plugin']['source_dir']) / '__init__.py'
    source_sha = hashlib.sha256(plugin_path.read_bytes()).hexdigest()
    assert source_sha == config['plugin_source_sha256']
    spec = importlib.util.spec_from_file_location('jiggle_timing_observed', plugin_path,
                                                submodule_search_locations=[str(plugin_path.parent)])
    plugin = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = plugin
    spec.loader.exec_module(plugin)
    plugin.register()
    scene.jiggle.enable = False
    arm.jiggle.freeze = True
    scene.frame_start, scene.frame_end, scene.render.fps = 1, args.last, 30
    scene.use_preview_range = False
    factor = args.fps // 30
    names = [row['name'] for row in config['hair_bones']]
    params = ['root_elasticity', 'length_elasticity', 'angle_elasticity', 'elasticity_soften',
              'gravity', 'blend', 'air_drag', 'friction', 'collision_radius']
    actual_settings = [dict(name=n, enabled=arm.pose.bones[n].jiggle.enable,
                           **{p: float(getattr(arm.pose.bones[n], 'jiggle_' + p)) for p in params}) for n in names]
    coll = bpy.data.collections['Jiggle_Physics_Colliders']
    assert len(coll.objects) == 14 and all(o.type == 'EMPTY' for o in coll.objects)
    assert sum(r['enabled'] for r in actual_settings) == 90 and len(names) == 144
    for old, now in zip(config['hair_bones'], actual_settings):
        assert old['name'] == now['name'] and old['enabled'] == now['enabled']
        assert abs(old['collision_radius'] - now['collision_radius']) < 1e-8
    cache_dir = out / 'cache'
    cache_dir.mkdir(exist_ok=True)
    for obj in bpy.data.objects:
        for modifier in obj.modifiers:
            if modifier.type == 'MESH_CACHE':
                src = Path(bpy.path.abspath(modifier.filepath))
                target = cache_dir / src.name
                if not target.exists():
                    shutil.copy2(src, target)
                modifier.filepath = str(target)
    # Snapshot body and collider poses before changing time; no solver is active.
    body_names = [b.name for b in arm.pose.bones if b.name not in names
                  and not any(p.name in names for p in b.parent_recursive)]
    check_frames = sorted(set([1, 151, 242, 256, 280, 300, 321, 331, 343, 344, 352, args.last]))
    expected_body = {}
    collider_matrices = {}
    for f in check_frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        expected_body[f] = np.array([np.array(arm.pose.bones[n].matrix) for n in body_names])
        collider_matrices[f] = np.array([np.array(o.matrix_world) for o in coll.objects])
    scene.frame_set(1)
    settings_hash = hashlib.sha256(json.dumps(actual_settings, sort_keys=True).encode()).hexdigest()
    colliders_hash = hashlib.sha256(collider_matrices[1].tobytes()).hexdigest()
    nla_snapshots, cache_snapshots, driver_snapshots = [], [], []
    if factor != 1:
        import re
        for track in arm.animation_data.nla_tracks:
            for strip in track.strips:
                snap = {k: getattr(strip, k) for k in ('frame_start', 'scale', 'blend_in', 'blend_out')}
                nla_snapshots.append((strip, snap))
                strip.frame_start = 1 + (snap['frame_start'] - 1) * factor
                strip.scale = snap['scale'] * factor
                strip.blend_in, strip.blend_out = snap['blend_in'] * factor, snap['blend_out'] * factor
                for curve in strip.fcurves:
                    retime(curve, factor)
        for obj in bpy.data.objects:
            for modifier in obj.modifiers:
                if modifier.type == 'MESH_CACHE':
                    cache_snapshots.append((modifier, modifier.frame_start, modifier.frame_scale))
                    modifier.frame_start = 1 + (modifier.frame_start - 1) * factor
                    modifier.frame_scale *= factor
                    if modifier.play_mode == 'CUSTOM' and obj.animation_data:
                        path = modifier.path_from_id('eval_frame')
                        for curve in obj.animation_data.drivers:
                            if curve.data_path == path:
                                driver_snapshots.append((curve.driver, curve.driver.expression))
                                curve.driver.expression = re.sub(r'\bframe\b', f'(1+(frame-1)/{factor})', curve.driver.expression)
    scene.frame_end = 1 + (args.last - 1) * factor
    scene.render.fps = args.fps
    for f in check_frames:
        scene.frame_set(1 + (f - 1) * factor)
        bpy.context.view_layer.update()
        assert np.max(np.abs(np.array([np.array(arm.pose.bones[n].matrix) for n in body_names]) - expected_body[f])) < 2e-5
        assert np.max(np.abs(np.array([np.array(o.matrix_world) for o in coll.objects]) - collider_matrices[f])) < 2e-5
    scene.frame_set(1)
    arm.jiggle.freeze = False
    arm.jiggle.mute = False
    arm.jiggle.enable = True
    scene.jiggle.enable = True
    scene.jiggle.preroll = round(.5 * args.fps)
    scene.jiggle.loop = False
    scene.jiggle.bake_overwrite = False
    scene.jiggle.bake_nla = False
    bpy.ops.object.select_all(action='DESELECT')
    arm.hide_set(False)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    write('input_fingerprint.json', dict(source=str(source), source_file_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        plugin_source_sha256=source_sha, hair_settings=actual_settings, settings_sha256=settings_hash,
        collider_count=14, collider_names=[o.name for o in coll.objects], collider_initial_matrices_sha256=colliders_hash,
        source_frames=[1, args.last], source_fps=30, simulation_fps=args.fps, preroll_seconds=.5,
        preroll_steps=scene.jiggle.preroll, body_poses_and_collider_timing_checked=check_frames,
        observer='sys.setprofile reads locals/positions; no plugin function or solver source replaced'))

    events, post_events = [], []
    active = None
    particle_meta = None
    sim_code = plugin.jiggle_simulate.__code__
    apply_code = plugin.VirtualParticle.apply_pose.__code__
    post_code = plugin.jiggle_post.__code__

    def bone_state():
        h = np.array(arm.matrix_world @ arm.pose.bones['頭'].matrix)
        inv = np.linalg.inv(h)
        matrices = [np.array(arm.matrix_world @ arm.pose.bones[n].matrix) for n in names]
        axes = np.array([v[:3, 1] for v in matrices]) @ inv[:3, :3].T
        axes /= np.maximum(np.linalg.norm(axes, axis=1, keepdims=True), 1e-12)
        return h, axes.astype(np.float32), np.array([v[:3, 3] for v in matrices], dtype=np.float32)

    def profiler(frame, event, arg):
        global active, particle_meta
        code = frame.f_code
        if code is sim_code:
            if event == 'call':
                active = dict(frame=int(scene.frame_current), steps=int(frame.f_locals['framecount']),
                              particles=frame.f_locals['virtual_particles'], raw=None)
            elif event == 'return' and active is not None:
                h, axes, positions = bone_state()
                active.update(head_world=h.astype(np.float32), immediate_axes=axes, immediate_heads=positions)
                active.pop('particles')
                events.append(active)
                active = None
                if scene.frame_current % args.fps == 0:
                    print('TRACE_PROGRESS', args.fps, scene.frame_current, flush=True)
        elif code is apply_code and event == 'call' and active is not None and active['raw'] is None:
            particles = active['particles']
            if particle_meta is None:
                indices = {id(p): i for i, p in enumerate(particles)}
                particle_meta = [dict(bone=p.bone_name, kind=p.particleType, static=p.static,
                                     children=[indices[id(c)] for c in p.children]) for p in particles]
            active['raw'] = np.array([p.working_position[:] for p in particles], dtype=np.float32)
            active['animated'] = np.array([p.pose[:] for p in particles], dtype=np.float32)
        elif code is post_code and event == 'return' and plugin._jiggle_globals.jiggle_baking:
            h, axes, positions = bone_state()
            post_events.append(dict(frame=int(scene.frame_current), head_world=h.astype(np.float32), axes=axes, heads=positions))

    status('BAKING_WITH_READ_ONLY_OBSERVER', fps=args.fps, source_last=args.last)
    previous_profile = sys.getprofile()
    sys.setprofile(profiler)
    try:
        result = bpy.ops.armature.jiggle_bake()
    finally:
        sys.setprofile(previous_profile)
    assert result == {'FINISHED'}
    scene.jiggle.enable = False
    arm.jiggle.freeze = True
    bpy.ops.object.mode_set(mode='OBJECT')
    # No observation mutates particle state; the source hash must still match.
    assert hashlib.sha256(plugin_path.read_bytes()).hexdigest() == source_sha
    action = arm.animation_data.action
    action.name = f'Jiggle原版_时间流程核验_{args.fps}Hz'
    if factor != 1:
        for curve in curves(action):
            retime(curve, 1 / factor)
        for strip, snap in nla_snapshots:
            strip.frame_start, strip.scale = snap['frame_start'], snap['scale']
            strip.blend_in, strip.blend_out = snap['blend_in'], snap['blend_out']
            for curve in strip.fcurves:
                retime(curve, 1 / factor)
        for modifier, first, scale in cache_snapshots:
            modifier.frame_start, modifier.frame_scale = first, scale
        for driver, expression in driver_snapshots:
            driver.expression = expression
    scene.frame_end, scene.render.fps = args.last, 30
    status('COMPARING_REPLAY_WITH_OBSERVED_POSES', events=len(events), post_events=len(post_events))
    assert events and all(e['raw'] is not None for e in events)
    frame_records = {e['frame']: e for e in events}
    sim_frames = sorted(frame_records)
    replay_axes, replay_heads, replay_head_world = [], [], []
    for sf in sim_frames:
        value = 1 + (sf - 1) / factor
        scene.frame_set(int(value), subframe=value % 1)
        bpy.context.view_layer.update()
        h, axes, positions = bone_state()
        replay_axes.append(axes)
        replay_heads.append(positions)
        replay_head_world.append(h)
    np.savez_compressed(out / 'pipeline_trace.npz', simulation_frames=sim_frames,
        source_frames=1 + (np.array(sim_frames) - 1) / factor,
        particle_world=np.array([frame_records[f]['raw'] for f in sim_frames]),
        animated_particle_world=np.array([frame_records[f]['animated'] for f in sim_frames]),
        immediate_axes=np.array([frame_records[f]['immediate_axes'] for f in sim_frames]),
        immediate_heads=np.array([frame_records[f]['immediate_heads'] for f in sim_frames]),
        immediate_head_world=np.array([frame_records[f]['head_world'] for f in sim_frames]),
        replay_axes=replay_axes, replay_heads=replay_heads, replay_head_world=replay_head_world,
        post_frames=[e['frame'] for e in post_events], post_axes=[e['axes'] for e in post_events],
        post_heads=[e['heads'] for e in post_events], post_head_world=[e['head_world'] for e in post_events])
    write('trace_mapping.json', dict(bone_names=names, particles=particle_meta,
        event_frames=[e['frame'] for e in events], event_steps=[e['steps'] for e in events],
        instant='particle_world captured after constrain/finish_step and before first apply_pose; immediate after jiggle_simulate; post after handler; replay after baking and time restoration'))
    skin = np.load(BASE / 'fullhair_repro_20261030/input_body_aware/skin_ids.npy')
    expected_skin = np.load(BASE / 'fullhair_repro_20261030/input_body_aware/body.npy', mmap_mode='r')
    body_error = 0.
    for f in range(1, args.last + 1):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        error = float(np.abs(coords(actor)[skin] - expected_skin[(f - 1) * 8]).max())
        body_error = max(body_error, error)
        assert error < 5e-6, (f, 'Body/intentional contact changed', error)
    scene.frame_set(1)
    blend = out / f'完整角色_Jiggle时间核验_{args.fps}Hz_13秒.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    write('bake_report.json', dict(status='OBSERVED_UPSTREAM_BAKE_NOT_VISUALLY_ACCEPTED', blend=str(blend),
          action=action.name, body_bone_max_error=body_error, frames=[1, args.last],
          plugin_source_sha256=source_sha, simulation_fps=args.fps))
    write('trace_result.json', dict(status='TRACE_CAPTURED_REQUIRES_ANALYSIS', blend=str(blend),
          body_error_m=body_error, frames=[1, args.last], simulation_fps=args.fps,
          particle_count=len(particle_meta), simulation_events=len(events), unique_simulation_frames=len(sim_frames),
          frame_change_post_events=len(post_events), elapsed_s=time.monotonic() - started))
    status('TRACE_COMPLETE', fps=args.fps, blend=str(blend), body_error_m=body_error)
except BaseException as exc:
    sys.setprofile(None)
    status('FAILED', error=repr(exc), traceback=traceback.format_exc())
    raise
