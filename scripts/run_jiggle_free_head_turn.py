"""Full-head inertia/gravity diagnostic with upstream Jiggle and no collision targets."""
import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import sys
import time
import traceback
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Quaternion

REPO = Path(__file__).resolve().parents[1]
BASE = REPO.parent / 'work/headswap_xl_codex'
parser = argparse.ArgumentParser()
parser.add_argument('--out')
parser.add_argument('--gravity', type=float)
parser.add_argument('--free-root-chains', help='JSON list of existing hair chains to simulate from their first bone')
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT = Path(args.out) if args.out else BASE / 'jiggle_free_motion_20261102'
OUT.mkdir(exist_ok=True, parents=True)
assert not (OUT / 'bake_report.json').exists(), 'Completed diagnostic preserved'
sys.path.insert(0, str(REPO / 'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
started = time.monotonic()


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def status(stage, **kwargs):
    value = dict(stage=stage, elapsed_s=time.monotonic()-started, **kwargs)
    write('status.json', value)
    print('FREE_HEAD_TURN', json.dumps(value, ensure_ascii=False), flush=True)


try:
    status('PREPARING_NO_COLLISION_CONTROL')
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
    spec = importlib.util.spec_from_file_location('jiggle_free_observed', plugin_path,
                                                submodule_search_locations=[str(plugin_path.parent)])
    plugin = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = plugin
    spec.loader.exec_module(plugin)
    plugin.register()
    scene.jiggle.enable = False
    arm.jiggle.freeze = True
    scene.frame_start, scene.frame_end, scene.render.fps, scene.render.fps_base = 1, 91, 30, 1
    scene.use_preview_range = False
    if scene.rigidbody_world:
        scene.rigidbody_world.enabled = False
    scene.frame_set(1)
    bpy.context.view_layer.update()
    before = coords(actor)
    basis = {b.name: b.matrix_basis.copy() for b in arm.pose.bones}
    for track in arm.animation_data.nla_tracks:
        track.mute = True
    control = bpy.data.actions.new('TEST_ONLY_身体静止_转头停住回正')
    arm.animation_data.action = control
    for b in arm.pose.bones:
        b.rotation_mode = 'QUATERNION'
        b.matrix_basis = basis[b.name]
        for prop in ['location', 'rotation_quaternion', 'scale']:
            b.keyframe_insert(data_path=prop, frame=1, group=b.name)
    cache = OUT / 'cache'
    cache.mkdir(exist_ok=True)
    for obj in bpy.data.objects:
        for modifier in obj.modifiers:
            if modifier.type == 'MESH_CACHE':
                path = Path(bpy.path.abspath(modifier.filepath))
                target = cache / path.name
                if not target.exists():
                    shutil.copy2(path, target)
                modifier.filepath = str(target)
                if obj.animation_data:
                    dp = modifier.path_from_id('eval_frame')
                    for curve in list(obj.animation_data.drivers):
                        if curve.data_path == dp:
                            obj.driver_remove(dp)
                modifier.play_mode = 'CUSTOM'
                modifier.time_mode = 'FRAME'
                modifier.eval_frame = 0
    scene.frame_set(1)
    bpy.context.view_layer.update()
    initial_error = float(np.max(np.abs(coords(actor)-before)))
    assert initial_error < 5e-6, ('Holding the body changed initial pose', initial_error)
    head = arm.pose.bones['頭']
    assert not head.constraints, 'Head control requires direct deform bone'
    base_world = arm.matrix_world @ head.matrix
    rotation = base_world.copy()
    rotation.translation = (0, 0, 0)
    for f, amount in [(1, 0), (16, 1), (31, 1), (46, 0), (91, 0)]:
        delta = Quaternion((0, 0, 1), math.radians(25)*amount) @ Quaternion((0, 1, 0), math.radians(15)*amount)
        desired = Matrix.Translation(base_world.translation) @ delta.to_matrix().to_4x4() @ rotation
        head.matrix = arm.matrix_world.inverted() @ desired
        for prop in ['location', 'rotation_quaternion', 'scale']:
            head.keyframe_insert(data_path=prop, frame=f, group=head.name)
    for layer in control.layers:
        for strip in layer.strips:
            for bag in getattr(strip, 'channelbags', []):
                for curve in bag.fcurves:
                    for point in curve.keyframe_points:
                        point.interpolation = 'BEZIER'
                        point.handle_left_type = point.handle_right_type = 'AUTO_CLAMPED'
    control_track = arm.animation_data.nla_tracks.new()
    control_track.name = 'TEST_ONLY_头部标准输入'
    control_track.strips.new(control.name, 1, control)
    arm.animation_data.action = bpy.data.actions.new('TEST_ONLY_头发静置覆盖')
    names = [r['name'] for r in config['hair_bones']]
    meta = json.loads((BASE / 'standard_proxy_20261031/inspection/inputs.json').read_text(encoding='utf-8'))
    requested_chains = set(json.loads(Path(args.free_root_chains).read_text(encoding='utf-8'))) if args.free_root_chains else set()
    selected_chains = [c for c in meta['chains'] if c['name'] in requested_chains]
    assert len(selected_chains) == len(requested_chains), 'Unknown chain in root policy'
    freed_bones = {n for c in selected_chains for n in c['bones']}
    root_names = [c['bones'][0] for c in selected_chains]
    formerly_disabled = {r['name'] for r in config['hair_bones'] if not r['enabled']}
    scene.frame_set(1)
    bpy.context.view_layer.update()
    for n in names:
        b = arm.pose.bones[n]
        for prop in ['location', 'rotation_quaternion', 'scale']:
            b.keyframe_insert(data_path=prop, frame=1, group=n)
        b.jiggle.collider_type = 'Object'
        b.jiggle.collider = None
        b.jiggle.collider_collection = None
        if args.gravity is not None:
            b.jiggle_gravity = args.gravity
        if n in freed_bones:
            b.jiggle.enable = True
            assert b.jiggle_root_elasticity == 1, 'Root-point comparison retains existing anchor strength'
    active_bones = sum(arm.pose.bones[n].jiggle.enable for n in names)
    assert active_bones == 90 + len(freed_bones & formerly_disabled)
    input_settings = [dict(name=n, enabled=arm.pose.bones[n].jiggle.enable,
                          **{p: float(getattr(arm.pose.bones[n], 'jiggle_'+p)) for p in ['root_elasticity', 'length_elasticity', 'angle_elasticity', 'gravity', 'air_drag', 'friction']}) for n in names]
    inspection = np.load(BASE / 'standard_proxy_20261031/inspection/inputs.npz')
    ids, labels, edges = inspection['ids'], inspection['chain_labels'], inspection['edges']
    initial = coords(actor)
    origin = np.array(arm.matrix_world @ head.head)
    tips = []
    for i in range(27):
        selected = ids[labels == i]
        radii = np.linalg.norm(initial[selected]-origin, axis=1)
        tips.append(selected[radii >= np.quantile(radii, .8)])
    body_names = [b.name for b in arm.pose.bones if b.name != '頭' and b.name not in names
                  and not any(p.name == '頭' or p.name in names for p in b.parent_recursive)]
    expected_body, heads, rigid_tips, expected_roots = [], [], [], []
    for f in range(1, 92):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        expected_body.append(np.array([np.array(arm.pose.bones[n].matrix) for n in body_names]))
        heads.append(np.array(arm.matrix_world @ head.matrix))
        co = coords(actor)
        rigid_tips.append(np.array([co[t].mean(0) for t in tips]))
        expected_roots.append(np.array([arm.matrix_world @ arm.pose.bones[n].head for n in root_names]))
    expected_body = np.array(expected_body)
    assert np.max(np.abs(expected_body-expected_body[0])) < 2e-5, 'Body not held still'
    scene.frame_set(1)
    bpy.context.view_layer.update()
    scene.jiggle.enable = True
    arm.jiggle.enable = True
    arm.jiggle.freeze = False
    arm.jiggle.mute = False
    scene.jiggle.preroll = 15
    scene.jiggle.loop = False
    scene.jiggle.bake_overwrite = False
    scene.jiggle.bake_nla = False
    bpy.ops.object.select_all(action='DESELECT')
    arm.hide_set(False)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    records = []
    def profile(frame, event, arg):
        if event == 'return' and frame.f_code is plugin.jiggle_simulate.__code__:
            particles = frame.f_locals['virtual_particles']
            assert not any(p.needs_collision for p in particles), 'Unexpected collision enabled'
            points = np.array([p.position[:] for p in particles], dtype=np.float32)
            assert np.isfinite(points).all()
            records.append((int(scene.frame_current), points))
    write('configuration.json', dict(source=str(source), mode='NO_COLLISION_INERTIA_GRAVITY_DIAGNOSTIC_ONLY',
        full_head_chains=27, hair_bones=144, active_bones=active_bones, settings=input_settings,
        root_policy='FIRST_BONE_DYNAMIC_ROOT_POINT_ANCHORED' if requested_chains else 'TWO_WHOLE_ROOT_BONES_FIXED',
        freed_root_chains=sorted(requested_chains), newly_enabled_bones=sorted(freed_bones & formerly_disabled),
        fps=30, frames=[1,91], preroll_seconds=.5, plugin_source_sha256=source_sha,
        controlled_motion='0..0.5s: yaw25deg + tilt15deg; 0.5..1s hold; 1..1.5s return;1.5..3s hold',
        initial_error_m=initial_error, original_dance_files_modified=False, contact_acceptance=False))
    status('BAKING_ORIGINAL_PLUGIN_WITHOUT_COLLISIONS')
    old_profile = sys.getprofile()
    sys.setprofile(profile)
    try:
        result = bpy.ops.armature.jiggle_bake()
    finally:
        sys.setprofile(old_profile)
    assert result == {'FINISHED'}
    scene.jiggle.enable = False
    arm.jiggle.freeze = True
    bpy.ops.object.mode_set(mode='OBJECT')
    action = arm.animation_data.action
    action.name = 'Jiggle原版_完整头发_无碰撞惯性短测'
    actual, body_error, head_error, root_error, strain = [], 0., 0., 0., []
    actual_roots, root_axes = [], []
    rest = np.linalg.norm(initial[ids[edges[:, 0]]]-initial[ids[edges[:, 1]]], axis=1)
    valid = rest > .001
    chain_edges = [np.flatnonzero((labels[edges[:,0]]==j)&(labels[edges[:,1]]==j)&valid) for j in range(27)]
    for f in range(1, 92):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        body_error = max(body_error, float(np.abs(np.array([np.array(arm.pose.bones[n].matrix) for n in body_names])-expected_body[f-1]).max()))
        head_error = max(head_error, float(np.abs(np.array(arm.matrix_world @ head.matrix)-heads[f-1]).max()))
        if root_names:
            positions = np.array([arm.matrix_world @ arm.pose.bones[n].head for n in root_names])
            root_error = max(root_error, float(np.linalg.norm(positions-expected_roots[f-1],axis=1).max()))
            actual_roots.append(positions)
            ih = np.linalg.inv(np.array(arm.matrix_world @ head.matrix))
            axes = np.array([(arm.matrix_world @ arm.pose.bones[n].matrix).col[1][:3] for n in root_names]) @ ih[:3,:3].T
            axes /= np.maximum(np.linalg.norm(axes,axis=1,keepdims=True),1e-12)
            root_axes.append(axes)
        co = coords(actor)
        assert np.isfinite(co).all()
        actual.append(np.array([co[t].mean(0) for t in tips]))
        length = np.linalg.norm(co[ids[edges[:,0]]]-co[ids[edges[:,1]]], axis=1)
        ratio = np.ones(len(rest))
        ratio[valid] = length[valid]/rest[valid]
        flags = [dict(chain=meta['chains'][j]['name'], p99=float(np.quantile(ratio[e],.99)), growth_cm=float((length[e]-rest[e]).max()*100)) for j,e in enumerate(chain_edges) if len(e) and np.quantile(ratio[e],.99)>1.5 and (length[e]-rest[e]).max()>.02]
        if flags:
            strain.append(dict(frame=f,chains=flags))
    assert body_error < 2e-5 and head_error < 2e-5, (body_error, head_error)
    assert root_error < 2e-5, ('Root anchor numerical replay mismatch',root_error)
    assert hashlib.sha256(plugin_path.read_bytes()).hexdigest() == source_sha
    unique = {f: p for f,p in records}
    np.savez_compressed(OUT / 'motion.npz', frames=np.arange(1,92), head_world=heads, rigid_tip_world=rigid_tips,
                        physical_tip_world=actual, raw_frames=sorted(unique), raw_particles=[unique[f] for f in sorted(unique)],
                        root_bone_names=root_names, root_expected_world=expected_roots, root_actual_world=actual_roots,
                        root_axes_head_local=root_axes)
    scene.frame_set(1)
    blend = OUT / ('完整角色_根部点锚定_无碰撞惯性_3秒.blend' if requested_chains else '完整角色_无碰撞惯性重力_3秒.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    write('bake_report.json', dict(status='NO_COLLISION_TEST_BAKED_REQUIRES_VISUAL_REVIEW', blend=str(blend), action=action.name,
        frames=[1,91], fps=30, body_control_error=body_error, head_control_error=head_error, strain_flags=strain,
        root_point_anchor_error_m=root_error, active_bones=active_bones, root_policy='POINT_ANCHOR_LONG_HAIR' if requested_chains else 'TWO_FIXED_SEGMENTS',
        no_collision_confirmed_in_every_observed_step=True, plugin_source_sha256=source_sha))
    status('BAKED_NO_COLLISION_REVIEW_PENDING', blend=str(blend), strain_flag_frames=len(strain))
except BaseException as exc:
    sys.setprofile(None)
    status('FAILED', error=repr(exc), traceback=traceback.format_exc())
    raise
