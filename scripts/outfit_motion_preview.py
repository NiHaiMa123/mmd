"""Render a reported VMD frame for visual review, without running physics."""
import argparse
from pathlib import Path
import sys
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json, write_json

parser = argparse.ArgumentParser()
parser.add_argument("--job", required=True)
parser.add_argument("--frame", type=int)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
job = Path(args.job)
request, result = read_json(job / "request.json"), read_json(job / "result.json")
motion = read_json(job / "motion/qa_report.json")["motion"]
frame = args.frame if args.frame is not None else motion["worst_frames"][0]["frame"]
ie = engine("import_export")
ie.ensure_mmd_tools()
ie.clear_scene()
objects = ie.import_pmx(result["pmx"])
armature = next(obj for obj in objects if obj.type == "ARMATURE")
for obj in bpy.context.selected_objects:
    obj.select_set(False)
armature.select_set(True)
bpy.context.view_layer.objects.active = armature
bpy.ops.mmd_tools.import_vmd(filepath=result.get('effective_motion') or request['motion'], scale=.08, rename_bones=True, log_level="ERROR")
bpy.context.scene.frame_set(frame)
bpy.context.view_layer.update()
out = job / "motion" / ("preview_frame_" + str(frame))
out.mkdir(parents=True, exist_ok=True)
profile = read_json(request["profile"])
mesh = ie.model_meshes(objects)[0]
garment_vertices = {i for face in mesh.data.polygons if mesh.data.materials[face.material_index].name in profile["selected_materials"] for i in face.vertices}
evaluated = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
evaluated_mesh = evaluated.to_mesh()
try:
    outliers = []
    for edge in mesh.data.edges:
        a, b = edge.vertices
        if a not in garment_vertices or b not in garment_vertices:
            continue
        original = (mesh.data.vertices[a].co - mesh.data.vertices[b].co).length
        current = (evaluated_mesh.vertices[a].co - evaluated_mesh.vertices[b].co).length
        if current > .1 and current > max(.001, original) * 4:
            outliers.append({"edge": [a, b], "rest_length": original, "posed_length": current,
                "groups": [[(mesh.vertex_groups[e.group].name, e.weight) for e in mesh.data.vertices[i].groups if e.weight > .01 and not mesh.vertex_groups[e.group].name.startswith("mmd_")] for i in (a, b)]})
    outliers.sort(key=lambda entry: -entry["posed_length"])
    write_json(out / "geometry.json", {"outliers": len(outliers), "largest_edges": outliers[:20]})
    implicated = {name for entry in outliers[:20] for groups in entry["groups"] for name, weight in groups}
    hierarchy = {}
    for name in implicated:
        bone = armature.pose.bones.get(name)
        for _ in range(8):
            if bone is None or bone.name in hierarchy:
                break
            hierarchy[bone.name] = {"parent": bone.parent.name if bone.parent else None,
                "location": list(bone.location), "rest_head": list(bone.bone.head_local),
                "posed_head": list(bone.head), "mmd_name": bone.mmd_bone.name_j}
            bone = bone.parent
    write_json(out / "bone_hierarchy.json", hierarchy)
finally:
    evaluated.to_mesh_clear()
images = engine("extraction").render_objects(ie.model_meshes(objects), out, width=600, height=800)
write_json(out / "review.json", {"frame": frame, "physics": False, "images": images,
    "scope": "VMD rig evaluation only; not MMD dynamics acceptance"})
print(out, flush=True)
