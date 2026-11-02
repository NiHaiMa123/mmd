"""Anatomical shoe sizing with a raised toe cavity and retained shoe panels."""
from mathutils import Vector


def fit(garment, body, armature, apply_positions, limb_regions, margin=0.004, max_scale=2.5,
        materials=("服", "服+jinshu"), toe_extra_length=0.020, toe_width_scale=1.15,
        toe_height_boost=1.2):
    source_regions, target_regions = limb_regions(garment), limb_regions(body)
    positions = [v.co.copy() for v in garment.data.vertices]
    report = []
    for side in ("L", "R"):
        key = "foot_" + side
        bone = armature.data.bones.get("足首." + side) or armature.data.bones.get("足首D." + side)
        if bone is None:
            raise ValueError(f"Missing ankle landmark for {side}")
        allowed = {i for face in garment.data.polygons
                   if garment.data.materials[face.material_index].name in materials for i in face.vertices}
        ids = [i for i, region in enumerate(source_regions) if region == key
               and i in allowed and positions[i].z <= bone.head_local.z + .04]
        target = [v.co for v, region in zip(body.data.vertices, target_regions)
                  if region == key and v.co.z <= bone.head_local.z + .02]
        if not ids or not target or bone is None:
            raise ValueError(f"No anatomical shoe/foot reference for {side}")
        anchor = bone.head_local
        factors = []
        capped = []
        source_center, target_center = [], []
        for axis in range(3):
            low, high = min(positions[i][axis] for i in ids), max(positions[i][axis] for i in ids)
            target_low, target_high = min(p[axis] for p in target) - margin, max(p[axis] for p in target) + margin
            source_center.append((low + high) / 2)
            target_center.append((target_low + target_high) / 2)
            factor = max(.5, (target_high - target_low) / max(.002, high - low)) if axis < 2 else 1.
            capped.append(factor > max_scale)
            factors.append(min(factor, max_scale))
        for index in ids:
            point = positions[index]
            positions[index] = Vector(tuple(target_center[i] + (point[i] - source_center[i]) * factors[i]
                                             if i < 2 else point[i] for i in range(3)))
        # Some targets have individual toe bones. A foot-only bounding box
        # misses those vertices, and a high-heel cap can sit above bare toes
        # even when the overall shoe bbox encloses the foot.
        source_names = {g.index: g.name for g in garment.vertex_groups}
        target_names = {g.index: g.name for g in body.vertex_groups}
        def toe_weight(vertex, names):
            return sum(e.weight for e in vertex.groups if names[e.group].endswith("." + side)
                       and names[e.group].startswith(("足先EX", "足親指", "足人指", "足中指", "足薬指", "足小指", "つま先")))
        weights = {i: min(1., toe_weight(garment.data.vertices[i], source_names)) for i in ids}
        toe_ids = [i for i in ids if weights[i] >= .5]
        toes = [v.co for v in body.data.vertices if toe_weight(v, target_names) >= .5]
        toe_fit = None
        if toe_ids and toes:
            lo = Vector(tuple(min(positions[i][a] for i in toe_ids) for a in range(3)))
            hi = Vector(tuple(max(positions[i][a] for i in toe_ids) for a in range(3)))
            target_lo = Vector(tuple(min(p[a] for p in toes) - margin for a in range(3)))
            target_hi = Vector(tuple(max(p[a] for p in toes) + margin for a in range(3)))
            # A pointed shoe needs space ahead of the toe tips; matching
            # their bbox would put the toes in the narrowing tip itself.
            target_lo.y -= toe_extra_length
            # Width/length follow toe extents; retain the raised instep and
            # heel silhouette while lowering the toe sole below the toes.
            scales = [(target_hi[a] - target_lo[a]) / max(.002, hi[a] - lo[a]) for a in (0, 1)]
            scales = [max(.5, min(max_scale, value)) for value in scales]
            zscale = max(1., min(max_scale, (hi.z - target_lo.z) / max(.002, hi.z - lo.z)))
            for index in ids:
                point = positions[index]
                desired = Vector((target_lo.x + (point.x - lo.x) * scales[0],
                                  target_lo.y + (point.y - lo.y) * scales[1],
                                  hi.z + (point.z - hi.z) * zscale))
                center_x = (target_lo.x + target_hi.x) / 2
                desired.x = center_x + (desired.x - center_x) * toe_width_scale
                front = max(0., min(1., (target_hi.y - desired.y) / max(.002, target_hi.y - target_lo.y)))
                front = front * front * (3 - 2 * front)
                desired.z = target_lo.z + (desired.z - target_lo.z) * (1 + toe_height_boost * front)
                positions[index] = point.lerp(desired, weights[index])
            toe_fit = {"vertices": len(toe_ids), "scale": [*scales, zscale]}
        report.append({"side": side, "selected_vertices": len(ids), "scale": factors,
                       "capped_axes": capped, "toe_fit": toe_fit})
    apply_positions(garment.data, positions)
    return {"method": "anatomical_foot_last", "sides": report,
            "scope": "bounding extents are sizing guides; toe enclosure needs visual review"}
