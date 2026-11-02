"""Rebuild explicit skin-tight regions on the target's skin topology.

Loose cuffs stay on their original mesh. Texture coordinates are sampled from
the coarse retargeted garment within anatomical domains, while vertex weights
and shape keys come from the target skin.
"""
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
from collections import Counter,defaultdict


def face_domain(face, values):
    """Use a unique plurality; ambiguous digit junctions keep the hand fallback."""
    found=[values[i] for i in face.vertices if values[i]]
    if len(found)<len(face.vertices)/2:return None
    counts=Counter(found)
    leaders=[name for name,count in counts.items() if count==max(counts.values())]
    return leaders[0] if len(leaders)==1 else None


def seam_safe_offsets(body, face_ids, margin):
    """Offset spatially shared vertices together, including split UV seams.

    Keep topology, UVs, weights and morphs; only share the displacement. A
    bounded miter keeps clearance at normal splits without opening a crack.
    """
    groups = defaultdict(list)
    used = sorted({i for fi in face_ids for i in body.data.polygons[fi].vertices})
    for i in used:
        groups[tuple(round(float(c), 6) for c in body.data.vertices[i].co)].append(i)
    offsets = {}
    split_groups, max_gap, capped = 0, 0., 0
    for indices in groups.values():
        normals = [body.data.vertices[i].normal for i in indices]
        direction = sum(normals, Vector())
        if direction.length < 1e-6:
            direction = normals[0].copy()
        direction.normalize()
        projection = min(direction.dot(n) for n in normals)
        factor = 1 / max(.5, projection)
        capped += projection < .5
        delta = direction * (margin * factor)
        if len(indices) > 1:
            split_groups += 1
            max_gap = max(max_gap, max((a-b).length for a in normals for b in normals)*margin)
        for i in indices:
            offsets[i] = delta.copy()
    return [offsets[i] for i in used], {'shared_position_groups': split_groups,
        'max_previous_offset_gap_m': max_gap, 'miter_capped_groups': capped,
        'max_offset_m': max((d.length for d in offsets.values()), default=0)}


def rebuild(garment, body, armature, rule, copy_subset, split_uv=None):
    kind, material = rule["region"], rule["material"]
    skin_materials = {rule["skin_material"], *rule.get("include_skin_materials", [])}
    def domain(name):
        if not name.endswith((".L", ".R")):
            return None
        base, side = name[:-2], name[-1]
        if kind == "hands":
            if base.startswith(("手首", "親指", "人指", "中指", "薬指", "小指", "ひじ", "腕", "手捩")):
                return "hand_" + side
        elif kind == "legs":
            if base.startswith(("足", "ひざ")) and not base.startswith(("足IK", "足ＩＫ")):
                return "leg_" + side
        return None

    def domains(obj):
        names = {group.index: group.name for group in obj.vertex_groups}
        return [domain(max(((e.weight, names[e.group]) for e in v.groups
                            if not names[e.group].startswith("mmd_")), default=(0, ""))[1])
                for v in obj.data.vertices]

    source_domains, target_domains = domains(garment), domains(body)
    def digit_domains(obj):
        names = {group.index: group.name for group in obj.vertex_groups}
        def label(vertex):
            name = max(((e.weight, names[e.group]) for e in vertex.groups
                        if not names[e.group].startswith('mmd_')), default=(0, ''))[1]
            return next((p for p in ('親指','人指','中指','薬指','小指') if name.startswith(p)), 'palm')
        return [label(v) for v in obj.data.vertices]
    source_digits = digit_domains(garment) if kind == 'hands' else None
    target_digits = digit_domains(body) if kind == 'hands' else None
    def distal(point, side):
        if kind != "hands":
            return True
        wrist = armature.data.bones["手首." + side].head_local
        knuckle = armature.data.bones["中指１." + side].head_local
        return (point - wrist).dot((knuckle - wrist).normalized()) >= rule.get("wrist_overlap", -0.018)

    source_faces = {}
    remove = set()
    for face in garment.data.polygons:
        if garment.data.materials[face.material_index].name != material:
            continue
        key = face_domain(face, source_domains)
        if key and distal(face.center, key[-1]):
            source_faces.setdefault(key, []).append(face.index)
            remove.add(face.index)
    if not source_faces:
        raise ValueError(f"No source faces for skin patch {kind}/{material}")
    source_positions = [v.co.copy() for v in garment.data.vertices]
    source_uv = garment.data.uv_layers.active
    if source_uv is None:
        raise ValueError("Skin patch requires source UV coordinates")
    garment.data.calc_loop_triangles()
    trees = {}
    sampling_faces = dict(source_faces)
    if kind == 'hands':
        for key, face_ids in source_faces.items():
            for fi in face_ids:
                digit = face_domain(garment.data.polygons[fi], source_digits)
                sampling_faces.setdefault((key, digit), []).append(fi)
    for key, face_ids in sampling_faces.items():
        allowed = set(face_ids)
        triangles = [t for t in garment.data.loop_triangles if t.polygon_index in allowed]
        trees[key] = (BVHTree.FromPolygons(source_positions, [tuple(t.vertices) for t in triangles], all_triangles=True),
                      [(tuple(t.vertices), [Vector((*source_uv.data[i].uv, 0)) for i in t.loops]) for t in triangles])
    heights = {key: (min(garment.data.vertices[i].co.z for fi in ids for i in garment.data.polygons[fi].vertices),
                     max(garment.data.vertices[i].co.z for fi in ids for i in garment.data.polygons[fi].vertices))
               for key, ids in source_faces.items()}
    target_faces, target_keys = [], {}
    uv_domain_fallbacks = set()
    for face in body.data.polygons:
        if body.data.materials[face.material_index].name not in skin_materials:
            continue
        key = face_domain(face, target_domains)
        if key not in trees or not distal(face.center, key[-1]):
            continue
        if kind == "legs" and not heights[key][0] + rule.get("lower_offset", 0) <= face.center.z <= heights[key][1]:
            continue
        target_faces.append(face.index)
        target_keys[face.index] = key
    if not target_faces:
        raise ValueError(f"No target skin for patch {kind}")
    patch, patch_original_ids = copy_subset(body, target_faces, "TargetSkinPatch")
    # copy_subset preserves polygon order and all target morphs and groups.
    slots = list(garment.data.materials)
    material_index = next(i for i, m in enumerate(slots) if m.name == material)
    patch.data.materials.clear()
    for slot in slots:
        patch.data.materials.append(slot)
    uv = patch.data.uv_layers.active or patch.data.uv_layers.new(name="UVMap")
    sampled_distances = []
    for patch_face, original_index in zip(patch.data.polygons, target_faces):
        patch_face.material_index = material_index
        for loop_index in patch_face.loop_indices:
            vertex_index = patch.data.loops[loop_index].vertex_index
            point = patch.data.vertices[vertex_index].co
            key = target_keys[original_index]
            if kind == 'hands':
                refined = (key, target_digits[patch_original_ids[vertex_index]])
                if refined in trees:
                    key = refined
                else:
                    uv_domain_fallbacks.add(original_index)
            tree, triangles = trees[key]
            hit, _, triangle_index, distance = tree.find_nearest(point)
            if hit is None:
                raise ValueError("No garment UV reference for target patch")
            indices, coords = triangles[triangle_index]
            mapped = barycentric_transform(hit, *(source_positions[i] for i in indices), *coords)
            uv.data[loop_index].uv = mapped.xy
            sampled_distances.append(distance)
    # Use target smooth normals; carry the same offset to every target morph.
    margin = rule.get("margin", 0.0015)
    deltas, seam_report = seam_safe_offsets(body, target_faces, margin)
    # copy_subset's vertex order is sorted original vertex index.
    for vertex, delta in zip(patch.data.vertices, deltas):
        vertex.co += delta
    if patch.data.shape_keys:
        for key in patch.data.shape_keys.key_blocks:
            for point, delta in zip(key.data, deltas):
                point.co += delta
    uv_split = split_uv(patch) if split_uv else {'added_vertices': 0, 'checked': False}
    coverage={'mode':'retain_skin','masked_skin_faces':0}
    if rule.get('covered_skin','retain')=='opaque_backup':
        from .opaque_cover import back_up_covered_skin
        from .service import engine
        coverage=back_up_covered_skin(body,patch,target_faces,copy_subset,kind,engine)
    retained, _ = copy_subset(garment, [f.index for f in garment.data.polygons if f.index not in remove], "RetainedOutfit")
    group_names = [g.name for g in retained.vertex_groups]
    garment.vertex_groups.clear()
    garment.data = retained.data
    for name in group_names:
        if name not in garment.vertex_groups:
            garment.vertex_groups.new(name=name)
    import bpy
    bpy.data.objects.remove(retained, do_unlink=True)
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    garment.select_set(True)
    patch.select_set(True)
    bpy.context.view_layer.objects.active = garment
    bpy.ops.object.join()
    return {"region": kind, "method": "target_skin_patch", "removed_faces": len(remove),
            "patch_faces": len(target_faces), "material": material,
            "skin_materials": sorted(skin_materials),
            "max_uv_reference_distance": max(sampled_distances),
            "uv_domains": 'per finger and palm' if kind == 'hands' else 'per leg',
            "uv_domain_fallback_faces": len(uv_domain_fallbacks),
            "uv_seam_split": uv_split,
            "skin_coverage": coverage,
            "seams": seam_report,
            "scope": "target geometry/weights; UV seams, cuffs and animation need visual review"}
