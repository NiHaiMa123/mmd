"""Blender-side closeups to separate body clipping, clothing geometry and texture."""
import argparse
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from mmd_outfit.service import engine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=args.blend)
    ie, render = engine("import_export"), engine("extraction")
    meshes = ie.model_meshes()
    cloth = next(obj for obj in meshes if obj.get("mmd_garment"))
    bodies = [obj for obj in meshes if obj is not cloth]
    scene = bpy.context.scene
    render._setup_render(scene, 800, 800)
    render._setup_lights(scene)
    camera_data = bpy.data.cameras.new("DiagnosticCamera")
    camera_data.type = "ORTHO"
    camera = bpy.data.objects.new("DiagnosticCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    def shot(name, center, size, direction=(0, -1, 0)):
        center = Vector(center)
        camera.location = center + Vector(direction) * 3
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera_data.ortho_scale = size
        scene.render.filepath = str(output / (name + ".png"))
        bpy.ops.render.render(write_still=True)

    shot("torso_textured", (0, -0.02, 1.19), 0.38)
    shot("ankle_textured", (0, 0, 0.17), 0.36)
    shot("hand_textured", (0.405, 0.0, 0.96), 0.24)
    for body in bodies:
        body.hide_render = True
    shot("torso_cloth_only", (0, -0.02, 1.19), 0.38)
    material = bpy.data.materials.new("DiagnosticGray")
    material.diffuse_color = (0.35, 0.45, 0.6, 1)
    material.use_nodes = True
    material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.35, 0.45, 0.6, 1)
    for index in range(len(cloth.data.materials)):
        cloth.data.materials[index] = material
    shot("torso_neutral_cloth", (0, -0.02, 1.19), 0.38)
    shot("torso_neutral_oblique", (0, -0.02, 1.19), 0.38, (0.5, -1, 0.1))
    print("DIAGNOSTICS", output, flush=True)


if __name__ == "__main__":
    main()
