"""Render an existing original-dance bake at 24 fps, without running physics."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / 'addon'))
from mmd_outfit.service import engine

p = argparse.ArgumentParser()
p.add_argument('--physics', required=True)
p.add_argument('--out', required=True)
p.add_argument('--keyframes-only', action='store_true')
p.add_argument('--first-output', type=int, default=1)
p.add_argument('--last-output', type=int, default=180)
p.add_argument('--collisions', choices=['off', 'ellipsoids', 'mesh'], default='off')
p.add_argument('--key-outputs', default='1,85,121,180')
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
physics, out = Path(a.physics), Path(a.out)
out.mkdir(parents=True, exist_ok=True)
receipt = json.loads((physics / 'bake_report.json').read_text('utf8'))
assert receipt['frames'] == [1, 450] and receipt['active_bones'] == 126
assert receipt['full_head_chains'] == 27 and receipt['source_animation_preserved']
collision_on = a.collisions != 'off'
if a.collisions == 'mesh':assert receipt['collision_mode'] == 'COMMUNITY_PR47_ACTUAL_SKIN_MESH'
assert bool(receipt.get('collisions', False)) == collision_on
assert receipt['collision_confirmed_in_every_observed_step'] if collision_on else receipt['no_collision_confirmed_in_every_observed_step']
engine('import_export').ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=receipt['blend'], load_ui=False, use_scripts=False)
s = bpy.context.scene
assert s.render.fps == 30 and s.render.fps_base == 1
assert bpy.data.objects['东雪莲x达妮娅_骨架'].animation_data.action.name == receipt['action']
assert not s.rigidbody_world or not s.rigidbody_world.enabled
assert not any('jiggle' in getattr(f, '__module__', '').lower()
               for f in list(bpy.app.handlers.frame_change_pre) + list(bpy.app.handlers.frame_change_post))
assert s.camera and not s.camera.animation_data and not s.camera.constraints
for ob in bpy.data.objects:
    for md in ob.modifiers:
        if md.type == 'MESH_CACHE':
            assert Path(bpy.path.abspath(md.filepath)).is_file(), (ob.name, md.filepath)
        if md.type == 'CLOTH':
            assert not md.show_render, ob.name
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.get_devices()
for device in prefs.devices:
    device.use = device.type == 'OPTIX'
assert any(d.use for d in prefs.devices)
s.cycles.device = 'GPU'
s.cycles.samples = 24
s.cycles.use_denoising = True
s.render.use_persistent_data = True
s.render.use_sequencer = False
s.render.resolution_x, s.render.resolution_y, s.render.resolution_percentage = 1920, 1080, 100
s.render.image_settings.file_format = 'PNG'
s.render.image_settings.color_depth = '8'
s.render.image_settings.color_mode = 'RGB'
plan = dict(source_seconds=[7.5, 15], duration_seconds=7.5, source_fps=30,
            output_fps=24, output_frames=180, resolution=[1920, 1080], cycles_samples=24,
            png_bit_depth=8, source_blend=receipt['blend'],
            bake_report=str(physics / 'bake_report.json'),
            sampling='source_frame=226+(output_frame-1)*1.25; original motion speed',
            frames=[dict(output_frame=i + 1, source_frame=226 + i * 1.25,
                         source_seconds=7.5 + i / 24) for i in range(180)],
            collisions=collision_on, naturalness_accepted=False, shutdown_forbidden=True)
plan_path = out / 'render_plan.json'
if plan_path.exists():
    assert json.loads(plan_path.read_text('utf8')) == plan
else:
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), 'utf8')
assert 1 <= a.first_output <= a.last_output <= 180
frames = out / 'frames'
frames.mkdir(exist_ok=True)
camera = np.array(s.camera.matrix_world)
started, start_epoch, rows = time.monotonic(), time.time(), []
indices = [int(x) for x in a.key_outputs.split(',')] if a.keyframes_only else range(a.first_output, a.last_output + 1)
assert all(1 <= i <= 180 for i in indices)
for index in indices:
    row = plan['frames'][index - 1]
    f = row['source_frame']
    assert 1 <= f <= 450
    s.frame_set(math.floor(f), subframe=f % 1)
    bpy.context.view_layer.update()
    error = float(np.abs(np.array(s.camera.matrix_world) - camera).max())
    assert error < 1e-9
    target = frames / f'f{index:04d}.png'
    s.render.filepath = str(target)
    if not target.exists():
        bpy.ops.render.render(write_still=True)
    progress = dict(**row, elapsed_s=time.monotonic() - started, camera_error=error)
    rows.append(progress)
    name = 'keyframes_progress.json' if a.keyframes_only else f'render_progress_{a.first_output}.json'
    (out / name).write_text(json.dumps(progress, indent=2), 'utf8')
    print('DANCE_PREVIEW_RENDER', json.dumps(progress), flush=True)
report = dict(status='KEYFRAMES_COMPLETE' if a.keyframes_only else 'OUTPUT_FRAME_RANGE_COMPLETE',
              source_blend=receipt['blend'], resolution=[1920, 1080], fps=24, samples=24,
              elapsed_s=time.monotonic() - started, start_epoch=start_epoch, end_epoch=time.time(), frames=rows)
name = 'keyframes_report.json' if a.keyframes_only else f'render_chunk_{a.first_output}_{a.last_output}.json'
(out / name).write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
print('DANCE_PREVIEW_COMPLETE', report['status'], flush=True)
