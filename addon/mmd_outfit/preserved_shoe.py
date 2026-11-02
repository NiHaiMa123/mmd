"""Closed shoes: untouched source geometry, rigid binding and collar-based culling.

This mode deliberately substitutes the visible foot surface with a closed shoe.
It does not squeeze a bare foot into it or support open sandals/barefoot toggles.
"""
from collections import Counter
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector


class CollarField:
    def __init__(self, points, depth):
        self.points = np.asarray(points, dtype=float)
        if self.points.ndim != 2 or self.points.shape[1] != 3 or len(self.points) < 6:
            raise ValueError("At least six genuine collar boundary controls are required")
        basis = np.column_stack((self.points[:, :2], np.ones(len(self.points))))
        if np.linalg.matrix_rank(basis) != 3 or not np.isfinite(self.points).all():
            raise ValueError("Collar controls must be finite and span an opening")
        self.plane = np.linalg.lstsq(basis, self.points[:, 2], rcond=None)[0]
        self.residual = self.points[:, 2] - basis @ self.plane
        self.depth = depth

    def height(self, point):
        distance = np.sum((self.points[:, :2] - (point.x, point.y)) ** 2, axis=1)
        weights = 1 / (distance + .005 ** 2) ** 2
        return float(np.dot((point.x, point.y, 1), self.plane)
                     + np.dot(weights, self.residual) / weights.sum() - self.depth)


def replace_mesh(destination, replacement):
    names = [g.name for g in replacement.vertex_groups]
    destination.vertex_groups.clear()
    destination.data = replacement.data
    for name in names:
        if name not in destination.vertex_groups:
            destination.vertex_groups.new(name=name)
    bpy.data.objects.remove(replacement, do_unlink=True)


def lock_vertex_morphs(obj, vertex_ids):
    """Hard shoes keep one shape even when facial/body vertex morphs are used."""
    keys=obj.data.shape_keys
    if not keys: return {'changed_keys':0,'affected_vertices':0,'max_removed_delta_m':0.}
    basis=keys.key_blocks[0]
    ids=list(vertex_ids); changed=[]; affected=set(); maximum=0.
    for key in keys.key_blocks[1:]:
        count=0
        for i in ids:
            delta=(key.data[i].co-basis.data[i].co).length
            if delta>1e-8:
                count+=1; affected.add(i); maximum=max(maximum,delta)
            key.data[i].co=basis.data[i].co
        if count: changed.append({'name':key.name,'vertices':count})
    return {'changed_keys':len(changed),'affected_vertices':len(affected),'max_removed_delta_m':maximum,
            'keys':changed,'scope':'selected rigid-shoe vertices only; vertex-morph toe/shape changes are disabled'}


def exported_vertices(mesh,reference_points,materials):
    from mathutils.kdtree import KDTree
    if not reference_points: raise ValueError('Missing preserved-shoe reference positions')
    tree=KDTree(len(reference_points))
    for i,p in enumerate(reference_points): tree.insert(Vector(p),i)
    tree.balance()
    matches={v.index for v in mesh.data.vertices if tree.find(v.co)[2]<1e-5}
    ids=sorted({i for f in mesh.data.polygons if mesh.data.materials[f.material_index].name in materials
                and all(j in matches for j in f.vertices) for i in f.vertices})
    if len(ids)!=len(reference_points): raise ValueError('Preserved-shoe geometry provenance does not match the exported mesh')
    return ids


def vertex_morph_report(mesh,vertex_ids):
    keys=mesh.data.shape_keys
    if not keys: return {'checked_keys':0,'changed_keys':[],'max_delta_m':0.}
    basis=keys.key_blocks[0]; changed=[];maximum=0.
    for key in keys.key_blocks[1:]:
        delta=max(((key.data[i].co-basis.data[i].co).length for i in vertex_ids),default=0.)
        maximum=max(maximum,delta)
        if delta>1e-7: changed.append(key.name)
    return {'checked_keys':len(keys.key_blocks)-1,'changed_keys':changed,'max_delta_m':maximum}


def lift_model(objects, meshes, armature, amount, apply_positions):
    if not amount:
        return
    offset = Vector((0, 0, amount))
    matrices = {o: o.matrix_world.copy() for o in objects
                if getattr(o, "mmd_type", "NONE") in {"RIGID_BODY", "JOINT"}}
    for mesh in meshes:
        apply_positions(mesh.data, [v.co + offset for v in mesh.data.vertices])
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    armature.hide_set(False)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in armature.data.edit_bones:
        bone.head += offset
        bone.tail += offset
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()
    for obj, matrix in matrices.items():
        matrix.translation += offset
        obj.matrix_world = matrix


def _boundary(source, material, ceiling):
    def key(point):
        return tuple(round(float(c), 6) for c in point)
    counts = Counter(tuple(sorted((key(source.data.vertices[f.vertices[j]].co),
        key(source.data.vertices[f.vertices[(j + 1) % len(f.vertices)]].co))))
        for f in source.data.polygons if source.data.materials[f.material_index].name == material
        for j in range(len(f.vertices)))
    return {point for edge, count in counts.items() if count == 1
            and all(p[2] < ceiling for p in edge) for point in edge}


def _horizontal_axis(points):
    values = np.asarray([p.y for p in points])
    if len(values) < 6 or np.ptp(values) < .01:
        raise ValueError("Missing reliable shoe/foot direction")
    front = [p for p in points if p.y <= np.quantile(values, .15)]
    back = [p for p in points if p.y >= np.quantile(values, .85)]
    direction = sum(front, Vector()) / len(front) - sum(back, Vector()) / len(back)
    return math.atan2(direction.y, direction.x)


def rim_position(point, ankle, scale):
    result = point.copy()
    if abs(point.x - ankle.x) >= .12 or abs(point.y - ankle.y) >= .25:
        return result
    weight = max(0., min(1., (ankle.z + .045 - point.z) / .065))
    factor = 1 - (1 - scale) * weight * weight * (3 - 2 * weight)
    result.x = ankle.x + (point.x - ankle.x) * factor
    result.y = ankle.y + (point.y - ankle.y) * factor
    return result


def prepare(source, source_arm, target, target_arm, target_objects, settings,
            model_meshes, copy_subset, apply_positions):
    materials = set(settings["materials"])
    source_height = max(source_arm.data.bones["足首." + s].head_local.z for s in ("L", "R")) + .06
    faces = [f.index for f in source.data.polygons
             if source.data.materials[f.material_index].name in materials
             and all(source.data.vertices[i].co.z < source_height for i in f.vertices)]
    if not faces:
        raise ValueError("No original closed shoe faces below the source ankles")
    boundary = _boundary(source, settings["collar_material"], source_height)
    shoes, original_ids = copy_subset(source, faces, "PreservedClosedShoes")
    morph_lock=lock_vertex_morphs(shoes,range(len(shoes.data.vertices)))
    original = [v.co.copy() for v in shoes.data.vertices]
    lift_model(target_objects, model_meshes(target_objects), target_arm, settings["body_lift"], apply_positions)
    matrices, sides, fields, reports = {}, {}, {}, {}
    allowed_skin = {i for face in target.data.polygons
                    if target.data.materials[face.material_index].name in settings["skin_materials"]
                    for i in face.vertices}
    for side, sign in (("L", 1), ("R", -1)):
        anchor = source_arm.data.bones["足首." + side].head_local
        destination = target_arm.data.bones["足首." + side].head_local
        ids = [i for i, p in enumerate(original) if p.x * sign > 0]
        feet = [v.co for v in target.data.vertices if v.index in allowed_skin
                and v.co.x * sign > 0 and v.co.z <= destination.z + .02]
        yaw = _horizontal_axis(feet) - _horizontal_axis([original[i] for i in ids])
        matrix = (Matrix.Translation(destination) @ Matrix.Rotation(yaw, 4, 'Z') @
                  Matrix.Scale(settings["scale"], 4) @ Matrix.Translation(-anchor))
        matrices[side], sides[side] = matrix, ids
        controls = [matrix @ Vector(p) for p in boundary if p[0] * sign > 0]
        fields[side] = CollarField(controls, settings["mask_depth"])
        reports[side] = {"scale": settings["scale"], "yaw_degrees": math.degrees(yaw),
                         "matrix": [list(row) for row in matrix],
                         "boundary_controls": [list(p) for p in controls]}
    for i, vertex in enumerate(shoes.data.vertices):
        vertex.co = matrices["L" if original[i].x > 0 else "R"] @ original[i]
    if shoes.data.shape_keys:
        for shape in shoes.data.shape_keys.key_blocks:
            for i, point in enumerate(shape.data):
                point.co = matrices["L" if original[i].x > 0 else "R"] @ point.co
    ratios = []
    for edge in shoes.data.edges:
        a, b = edge.vertices
        length = (original[a] - original[b]).length
        if length > 1e-7:
            ratios.append((shoes.data.vertices[a].co - shoes.data.vertices[b].co).length / length)
    error = max(abs(value / settings["scale"] - 1) for value in ratios)
    if error > 1e-4:
        raise ValueError("Original shoe shape preservation check failed")
    # One deform bone per shoe: even toe IK cannot stretch its sole or ornaments.
    shoes.vertex_groups.clear()
    for side in ("L", "R"):
        name = "足首D." + side
        if name not in target_arm.data.bones:
            raise ValueError(f"Missing closed-shoe deform bone {name}")
        shoes.vertex_groups.new(name=name).add(sides[side], 1, 'REPLACE')
    edge = shoes.vertex_groups.new(name="mmd_edge_scale")
    edge.add(list(range(len(shoes.data.vertices))), 1, 'REPLACE')
    # Mask only actual foot skin; the extrapolated field must never reach hands.
    removed = []
    for face in target.data.polygons:
        if target.data.materials[face.material_index].name not in settings["skin_materials"]:
            continue
        points = [target.data.vertices[i].co for i in face.vertices]
        side = "L" if sum(p.x for p in points) > 0 else "R"
        ankle = target_arm.data.bones["足首." + side].head_local
        if all(p.z < ankle.z + .06 and abs(p.x - ankle.x) < .12
               and abs(p.y - ankle.y) < .25 and p.z < fields[side].height(p) for p in points):
            removed.append(face.index)
    if not removed:
        raise ValueError("Closed-shoe mask found no foot surface; inspect the collar")
    backup_faces = set(removed)
    for face in target.data.polygons:
        if target.data.materials[face.material_index].name not in settings["skin_materials"]:
            continue
        for i in face.vertices:
            point = target.data.vertices[i].co
            ankle = target_arm.data.bones["足首." + ("L" if point.x > 0 else "R")].head_local
            if (rim_position(point, ankle, settings["ankle_rim_scale"]) - point).length > 1e-8:
                backup_faces.add(face.index)
                break
    backup, _ = copy_subset(target, sorted(backup_faces), "ClosedShoe_FootBackup")
    backup["mmd_garment"] = False
    backup["outfit_backup"] = True
    backup.hide_render = True
    backup.hide_set(True)
    removed_set = set(removed)
    retained, _ = copy_subset(target, [f.index for f in target.data.polygons if f.index not in removed_set], "RetainedTarget")
    replace_mesh(target, retained)
    skin_ids = {i for face in target.data.polygons
                if target.data.materials[face.material_index].name in settings["skin_materials"] for i in face.vertices}
    updated = [v.co.copy() for v in target.data.vertices]
    rim_changes = []
    for i in skin_ids:
        point = updated[i]
        ankle = target_arm.data.bones["足首." + ("L" if point.x > 0 else "R")].head_local
        updated[i] = rim_position(point, ankle, settings["ankle_rim_scale"])
        distance = (updated[i] - point).length
        if distance > 1e-8:
            rim_changes.append(distance)
    apply_positions(target.data, updated)
    # Remove the exact original shoe faces before any legacy fitting or patch
    # rebuilding. A later height-based selection can also catch the new socks.
    source_faces = set(faces)
    remainder, _ = copy_subset(source, [f.index for f in source.data.polygons if f.index not in source_faces], "SourceWithoutShoes")
    replace_mesh(source, remainder)
    report = {"method": "preserved_closed_shoe", "body_lift": settings["body_lift"],
              "vertex_morph_lock":morph_lock,
              "source_faces": len(faces), "source_vertices": len(original_ids),
              "original_source_vertex_ids": original_ids, "sides": reports,
              "max_relative_edge_error": error, "foot_shape_changed": bool(rim_changes),
              "ankle_rim": {"scale": settings["ankle_rim_scale"], "changed_vertices": len(rim_changes),
                            "max_displacement_m": max(rim_changes, default=0),
                            "scope": "smooth XY taper ending 45 mm above the ankle; original region backed up"},
              "backup_skin_faces": len(backup_faces),
              "masked_skin_faces": len(removed), "foot_backup_object": backup.name,
              "source_shoes_removed_before_legacy_fit": True,
              "binding": "one target 足首D deform bone per whole closed shoe",
              "scope": "closed shoes only; foot surface substituted, no barefoot toggle; motion and collar review required"}
    return {"shoes": shoes, "report": report}


def attach(state, clothes, armature, copy_subset, materials):
    if not state["report"].get("source_shoes_removed_before_legacy_fit"):
        raise ValueError("Original shoe faces must be removed before legacy fitting")
    start = len(clothes.data.vertices)
    shoes = state["shoes"]
    count = len(shoes.data.vertices)
    state['report']['reference_positions']=[list(v.co) for v in shoes.data.vertices]
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    shoes.select_set(True)
    clothes.select_set(True)
    bpy.context.view_layer.objects.active = clothes
    bpy.ops.object.join()
    state["report"]["attached_vertex_range"] = [start, start + count]
    return state["report"]
