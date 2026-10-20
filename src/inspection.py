"""Close-up inspection of the outfit (runs inside Blender).

The full body render is too small to judge a glove or a shoe.  This module
frames a body region - located by the bones that drive it - and renders it
from several directions, so every part of the outfit can be checked on its
own.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector

# region -> bones that locate it, plus how much of the body to show.
# Left and right are separate: in an A-pose the hands hang beside the hips,
# so framing the midpoint of both hands would show the skirt instead.
REGIONS: dict[str, dict[str, Any]] = {
    "hand_l": {"bones": ["手首.L"], "span": 0.15, "note": "左手套"},
    "hand_r": {"bones": ["手首.R"], "span": 0.15, "note": "右手套"},
    "foot_l": {"bones": ["足首.L"], "span": 0.17, "note": "左鞋"},
    "foot_r": {"bones": ["足首.R"], "span": 0.17, "note": "右鞋"},
    "head": {"bones": ["頭"], "span": 0.30, "note": "头部 / 发饰"},
    "neck": {"bones": ["首"], "span": 0.24, "note": "领口 / 脖子"},
    "shoulder_l": {"bones": ["肩.L"], "span": 0.22, "note": "左护肩"},
    "shoulder_r": {"bones": ["肩.R"], "span": 0.22, "note": "右护肩"},
    "sleeve_l": {"bones": ["腕.L"], "span": 0.30, "note": "左袖"},
    "sleeve_r": {"bones": ["腕.R"], "span": 0.30, "note": "右袖"},
    "bodice": {"bones": ["上半身2"], "span": 0.40, "note": "上衣胸口"},
    "waist": {"bones": ["腰"], "span": 0.40, "note": "腰部 / 裙腰"},
}

VIEWS = {
    "front": (0.0, -1.0, 0.0),
    "back": (0.0, 1.0, 0.0),
    "left": (-1.0, 0.0, 0.0),
    "right": (1.0, 0.0, 0.0),
    "top": (0.0, -0.35, 1.0),
    "bottom": (0.0, -0.35, -1.0),
    "q_left": (-0.8, -0.8, 0.35),
    "q_right": (0.8, -0.8, 0.35),
}


def _region_center(objects: list[bpy.types.Object], names: list[str]):
    """Centre of the region, taken from the bones that drive it."""
    points = []
    for o in objects:
        if o.type != 'ARMATURE':
            continue
        for n in names:
            b = o.data.bones.get(n)
            if b is not None:
                points.append(o.matrix_world @ b.head_local)
        break
    if not points:
        return None
    center = Vector((0.0, 0.0, 0.0))
    for p in points:
        center += p
    return center / len(points)


def _setup_render(scene, width, height):
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    try:
        scene.view_settings.view_transform = 'Standard'
    except Exception:
        pass


def _setup_lights(scene):
    for ob in list(bpy.data.objects):
        if ob.name.startswith("CloseupLight_"):
            bpy.data.objects.remove(ob, do_unlink=True)
    for name, loc, energy in (("Key", (1.5, -2.0, 2.0), 220.0),
                              ("Fill", (-1.8, -1.2, 0.8), 90.0),
                              ("Rim", (0.0, 2.5, 1.6), 140.0)):
        ld = bpy.data.lights.new(f"CloseupLight_{name}", type='AREA')
        ld.energy = energy
        ld.size = 1.5
        lo = bpy.data.objects.new(f"CloseupLight_{name}", ld)
        lo.location = loc
        scene.collection.objects.link(lo)
        direction = (Vector((0, 0, 1.0)) - Vector(loc)).normalized()
        lo.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


def _make_camera(scene, center: Vector, direction: Vector, ortho: float):
    cam_data = bpy.data.cameras.new("CloseupCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = ortho
    cam = bpy.data.objects.new("CloseupCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = center + direction.normalized() * (ortho * 4 + 1.0)
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    return cam


def render_closeups(objects: list[bpy.types.Object], out_dir: str,
                    regions: list[str] | None = None,
                    views: list[str] | None = None,
                    width: int = 760, height: int = 760) -> dict[str, Any]:
    """Render every region from several directions."""
    from . import extraction

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    _setup_render(scene, width, height)
    _setup_lights(scene)

    # only the model itself, no rigid body proxies
    hidden = [o for o in objects if o.type == 'MESH' and o.get("mmd_rigid")]
    for o in hidden:
        o.hide_render = True

    regions = regions or list(REGIONS)
    views = views or ["front", "left", "right", "back", "q_left", "q_right"]
    written = []
    missing = []
    for name in regions:
        spec = REGIONS.get(name)
        if spec is None:
            continue
        center = _region_center(objects, spec["bones"])
        if center is None:
            missing.append(name)
            continue
        for view in views:
            cam = _make_camera(scene, center, Vector(VIEWS[view]),
                               spec["span"])
            scene.render.filepath = str(out / f"{name}_{view}.png")
            bpy.ops.render.render(write_still=True)
            written.append(scene.render.filepath)
            bpy.data.objects.remove(cam, do_unlink=True)

    for o in hidden:
        o.hide_render = False
    return {"images": written, "missing_regions": missing,
            "regions": regions, "views": views}
