"""Landmark-based closeups returned alongside full-body views for agent review."""
from pathlib import Path
import bpy
from mathutils import Vector


def details(objects, output, render_engine):
    armature = next((obj for obj in objects if obj.type == "ARMATURE"), None)
    if armature is None:
        return []
    bones = armature.data.bones
    def point(name):
        return armature.matrix_world @ bones[name].head_local if name in bones else None
    shots = []
    lower, neck = point("下半身"), point("首")
    if lower is not None and neck is not None:
        center, size = lower.lerp(neck, .5), max(.35, (neck - lower).length * 1.35)
        shots.extend((("detail_torso", center, size, (0, -1, 0)),
                      ("detail_torso_oblique", center, size, (.6, -1, .05))))
    for side in ("L", "R"):
        wrist, finger = point("手首." + side), point("中指３." + side)
        if wrist is not None and finger is not None:
            shots.append(("detail_hand_" + side, wrist.lerp(finger, .5),
                          max(.20, (finger - wrist).length * 2.5), (0, -1, 0)))
    left, right = point("足首.L"), point("足首.R")
    if left is not None and right is not None:
        center = (left + right) * .5 - Vector((0, 0, .015))
        size = max(.36, (left - right).length * 2.5)
        shots.extend((("detail_feet", center, size, (0, -1, 0)),
                      ("detail_feet_oblique", center, size, (1, -1, .05))))
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    render_engine._setup_render(scene, 800, 800)
    render_engine._setup_lights(scene)
    camera_data = bpy.data.cameras.new("OutfitDetailCamera")
    camera_data.type = "ORTHO"
    camera = bpy.data.objects.new("OutfitDetailCamera", camera_data)
    scene.collection.objects.link(camera)
    previous_camera = scene.camera
    scene.camera = camera
    written = []
    try:
        for name, center, size, direction in shots:
            camera.location = center + Vector(direction).normalized() * 3
            camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
            camera_data.ortho_scale = size
            scene.render.filepath = str(directory / (name + ".png"))
            bpy.ops.render.render(write_still=True)
            written.append(scene.render.filepath)
    finally:
        scene.camera = previous_camera
        bpy.data.objects.remove(camera, do_unlink=True)
        bpy.data.cameras.remove(camera_data)
    return written
