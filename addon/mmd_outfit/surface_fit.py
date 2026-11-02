"""Bounded, region-selected clearance correction after coarse rig adaptation.

Only selected garment vertices can move; the body is never edited here.
Signed nearest-surface clearance is a local diagnostic, not a
watertight collision proof, and is reported as such.
"""
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


def correct(garment, body, vertex_ids, body_materials, *, clearance=0.003,
            max_distance=0.1, max_displacement=0.1, iterations=4, radial_axis=None,
            target_bone_prefixes=None, radial_order=False):
    faces = [face for face in body.data.polygons
             if body.data.materials[face.material_index].name in body_materials]
    if target_bone_prefixes:
        groups = {group.index for group in body.vertex_groups if any(
            group.name.startswith(prefix) for prefix in target_bone_prefixes)}
        allowed = {vertex.index for vertex in body.data.vertices
                   if sum(entry.weight for entry in vertex.groups if entry.group in groups) >= 0.4}
        faces = [face for face in faces if sum(index in allowed for index in face.vertices) >= len(face.vertices) * 0.5]
    if not faces:
        raise ValueError("No faces in the requested target skin materials")
    vertices = [body.matrix_world @ vertex.co for vertex in body.data.vertices]
    bvh = BVHTree.FromPolygons(vertices, [tuple(face.vertices) for face in faces])
    ids = set(vertex_ids)
    positions = [garment.matrix_world @ vertex.co for vertex in garment.data.vertices]
    originals = [point.copy() for point in positions]
    inverse = garment.matrix_world.inverted()
    neighbors = {index: [] for index in ids}
    for edge in garment.data.edges:
        a, b = edge.vertices
        if a in ids and b in ids:
            neighbors[a].append(b)
            neighbors[b].append(a)

    def contact(point):
        if radial_axis is None:
            hit, normal, _, distance = bvh.find_nearest(point)
            return hit, normal, distance, (point - hit).dot(normal) if hit is not None else None
        lower, upper = radial_axis
        t = min(1.0, max(0.0, (point.z - lower.z) / (upper.z - lower.z)))
        anchor = lower.lerp(upper, t)
        anchor.z = point.z
        direction = point - anchor
        direction.z = 0
        if direction.length < 1e-6:
            return None, None, None, None
        direction.normalize()
        # Cast from outside to find the outer envelope. This avoids picking
        # an inner skin layer or relying on inward/inconsistent nipple normals.
        hit, _, _, _ = bvh.ray_cast(anchor + direction, -direction, 2.0)
        if hit is None:
            return None, None, None, None
        signed = (point - hit).dot(direction)
        return hit, direction, abs(signed), signed

    def measure():
        violated, unavailable = 0, 0
        minimum = None
        for index in ids:
            hit, normal, distance, signed = contact(positions[index])
            if hit is None or distance > max_distance:
                unavailable += 1
                continue
            minimum = signed if minimum is None else min(minimum, signed)
            violated += signed < clearance - 1e-5
        return {"violating_vertices": violated, "unavailable_vertices": unavailable,
                "min_signed_clearance": minimum}

    before = measure()
    capped = set()
    if radial_order:
        import math
        from .deformation import RadialEnvelopeField
        ordered = sorted(ids)
        lower, upper = radial_axis
        def polar(point):
            t = min(1., max(0., (point.z - lower.z) / (upper.z - lower.z)))
            anchor = lower.lerp(upper, t)
            anchor.z = point.z
            direction = point - anchor
            angle = math.atan2(direction.y, direction.x)
            return angle, direction.normalized()
        angles, heights, amounts = [], [], []
        directions = []
        supported = []
        for index in ordered:
            point = originals[index]
            angle, direction = polar(point)
            hit, _, distance, signed = contact(point)
            angles.append(angle)
            heights.append(point.z)
            directions.append(direction)
            supported.append(hit is not None and distance <= max_distance)
            amounts.append(max(0., clearance - signed) if supported[-1] else 0.)
        field = RadialEnvelopeField(angles, heights, amounts)
        values = field.evaluate(angles, heights)
        for index, direction, amount, valid in zip(ordered, directions, values, supported):
            if not valid:
                continue
            if amount > max_displacement:
                capped.add(index)
            positions[index] += direction * min(amount, max_displacement)
        return ([inverse @ point for point in positions],
                {"selected_vertices": len(ids), "before": before, "after": measure(),
                 "capped_vertices": len(capped), "target_faces": len(faces),
                 "max_displacement": max(((positions[i] - originals[i]).length for i in ids), default=0),
                 "method": "radial_order", "control_centers": len(field.centers),
                 "scope": "radius-independent field preserves radial layer order; animation needs separate review"})
    if radial_axis is not None:
        # Neighboring layers share a coarse displacement instead of all being
        # collapsed onto the same skin offset (which causes garment z-fighting).
        tree = KDTree(len(ids))
        required = {}
        normals = {}
        for index in ids:
            tree.insert(originals[index], index)
            hit, normal, distance, signed = contact(originals[index])
            required[index] = max(0.0, clearance - signed) if hit is not None and distance <= max_distance else 0.0
            normals[index] = normal
        tree.balance()
        for index in ids:
            if normals[index] is None or required[index] <= 0:
                continue
            amount = max((required[other] for _, other, _ in tree.find_range(originals[index], 0.006)),
                         default=required[index])
            if amount > max_displacement:
                amount = max_displacement
                capped.add(index)
            positions[index] = originals[index] + normals[index] * amount
    for _ in range(iterations):
        field = {}
        for index in ids:
            hit, normal, distance, signed = contact(positions[index])
            delta = Vector((0, 0, 0))
            if hit is not None and distance <= max_distance:
                if signed < clearance:
                    delta = normal * (clearance - signed)
            field[index] = delta
        # Mild regularization retains most of a required outward correction.
        for index in ids:
            delta = field[index]
            if neighbors[index]:
                delta = delta * 0.85 + sum((field[j] for j in neighbors[index]),
                                          Vector()) * (0.15 / len(neighbors[index]))
            desired = positions[index] + delta
            total = desired - originals[index]
            if total.length > max_displacement:
                desired = originals[index] + total.normalized() * max_displacement
                capped.add(index)
            positions[index] = desired
    # Regularization must not halve the required clearance on the last pass.
    for index in ids:
        hit, normal, distance, signed = contact(positions[index])
        if hit is not None and distance <= max_distance and signed < clearance:
            desired = positions[index] + normal * (clearance - signed)
            total = desired - originals[index]
            if total.length <= max_displacement:
                positions[index] = desired
            else:
                capped.add(index)
    after = measure()
    return ([inverse @ point for point in positions],
            {"selected_vertices": len(ids), "before": before, "after": after,
             "capped_vertices": len(capped),
             "max_displacement": max(((positions[i] - originals[i]).length for i in ids), default=0),
             "method": "radial_envelope" if radial_axis else "nearest_signed_surface",
             "target_faces": len(faces),
             "scope": "local signed vertex clearance; face intersections and animation require separate checks"})


def apply_rules(garment, body, armature, common_bones, rules, apply_positions, subdivide=None):
    result = []
    for rule in rules:
        low = (armature.matrix_world @ armature.data.bones[rule["lower_bone"]].head_local).z
        high = (armature.matrix_world @ armature.data.bones[rule["upper_bone"]].head_local).z
        low += rule.get("lower_offset", 0)
        high += rule.get("upper_offset", 0)
        if low >= high:
            raise ValueError(f"Reversed landmark interval: {rule['name']}")
        subdivision = None
        if rule.get("subdivide", 0) and subdivide:
            subdivision = []
            for _ in range(rule["subdivide"]):
                face_ids = []
                for face in garment.data.polygons:
                    if garment.data.materials[face.material_index].name not in rule.get("subdivide_materials", []):
                        continue
                    points = [garment.matrix_world @ garment.data.vertices[index].co for index in face.vertices]
                    if all(low <= point.z <= high for point in points) and any(
                        (points[i] - points[(i + 1) % len(points)]).length > rule.get("max_edge", 0.012)
                        for i in range(len(points))):
                        face_ids.append(face.index)
                subdivision.append(subdivide(garment.data, face_ids))
        names = {group.index: group.name for group in garment.vertex_groups}
        candidates = {index for face in garment.data.polygons
                      if garment.data.materials[face.material_index].name in rule["materials"]
                      for index in face.vertices}
        selected = []
        for index in candidates:
            vertex = garment.data.vertices[index]
            point = garment.matrix_world @ vertex.co
            weights = [(entry.weight, names[entry.group]) for entry in vertex.groups
                       if not names[entry.group].startswith("mmd_")]
            dominant = max(weights, default=(0, ""))[1]
            body_driven = dominant in common_bones or any(
                dominant.startswith(prefix) for prefix in rule.get("include_bone_prefixes", []))
            if low <= point.z <= high and (body_driven or rule.get("method") == "radial_order"):
                selected.append(index)
        if not selected:
            raise ValueError(f"Clearance rule selected no vertices: {rule['name']}")
        positions, report = correct(garment, body, selected, rule["target_skin_materials"],
                                    clearance=rule.get("clearance", 0.003),
                                    max_distance=rule.get("max_distance", 0.1),
                                    max_displacement=rule.get("max_displacement", 0.1),
                                    iterations=rule.get("iterations", 4),
                                    radial_axis=(armature.matrix_world @ armature.data.bones[rule["lower_bone"]].head_local,
                                                 armature.matrix_world @ armature.data.bones[rule["upper_bone"]].head_local)
                                    if rule.get("method") in {"radial_envelope", "radial_order"} else None,
                                    target_bone_prefixes=rule.get("target_bone_prefixes"),
                                    radial_order=rule.get("method") == "radial_order")
        apply_positions(garment.data, positions)
        result.append({"rule": rule["name"], "subdivision": subdivision, **report})
    return result
