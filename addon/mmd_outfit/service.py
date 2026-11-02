"""Blender-side service. Profiles bind settings and selections to exact inputs."""
from __future__ import annotations

import hashlib
import importlib
import json
import math
from pathlib import Path
import sys

import bpy

from .jobs import read_json, write_json


class OutfitError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def engine(name):
    # ZIP builds contain their own engine. A source checkout uses ../src.
    if Path(__file__).with_name("engine").is_dir():
        return importlib.import_module(f"{__package__}.engine.{name}")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    return importlib.import_module(f"src.{name}")


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def load_profile(path):
    profile = read_json(path)
    if profile.get("schema_version") != 1 or profile.get("kind") != "mmd_outfit_pair":
        raise OutfitError("PROFILE_SCHEMA", "Expected a version 1 mmd_outfit_pair profile")
    for side in ("source", "target"):
        record = profile.get(side, {})
        source = Path(record.get("path", ""))
        if not source.is_file() or digest(source) != record.get("sha256"):
            raise OutfitError("PROFILE_INPUT_CHANGED", f"{side} PMX is missing or changed; inspect again")
    selected = profile.get("selected_materials")
    if not isinstance(selected, list) or not selected or not all(isinstance(n, str) for n in selected) or len(selected) != len(set(selected)):
        raise OutfitError("EMPTY_SELECTION", "selected_materials must contain unique, exact material names")
    allowed = {m["material"] for m in profile["materials"]}
    missing = set(selected) - allowed
    if missing:
        raise OutfitError("UNKNOWN_MATERIAL", f"Materials absent from source: {sorted(missing)}")
    excluded = profile.get("target_exclude_materials", [])
    if not isinstance(excluded, list) or not all(isinstance(n, str) for n in excluded):
        raise OutfitError("CONFIG_SCHEMA", "target_exclude_materials must be a list of exact names")
    target_materials = set(profile.get("target_materials", []))
    if set(excluded) - target_materials:
        raise OutfitError("UNKNOWN_MATERIAL", "Excluded materials are absent from target inventory")
    if "Body" in excluded and profile.get("preset") == "keqing_daniya":
        raise OutfitError("SKIN_PROTECTED", "The Keqing/Daniya preset protects target skin material Body")
    rules = profile.get("clearance_rules", [])
    if 'cuff_physics' in profile and not isinstance(profile['cuff_physics'],bool):
        raise OutfitError('CONFIG_SCHEMA','cuff_physics must be boolean')
    if 'arm_rest' in profile and profile['arm_rest']!={'method':'anatomical_upper_arm'}:
        raise OutfitError('CONFIG_SCHEMA','arm_rest must specify only method=anatomical_upper_arm')
    if not isinstance(rules, list):
        raise OutfitError("CONFIG_SCHEMA", "clearance_rules must be a list")
    for rule in rules:
        required = {"name", "materials", "target_skin_materials", "lower_bone", "upper_bone"}
        optional = {"lower_offset", "upper_offset", "clearance", "max_distance", "max_displacement",
                    "iterations", "subdivide", "subdivide_materials", "max_edge", "include_bone_prefixes", "method", "target_bone_prefixes"}
        if not isinstance(rule, dict) or not required.issubset(rule) or set(rule) - required - optional:
            raise OutfitError("CONFIG_SCHEMA", "Invalid clearance rule fields")
        if rule.get("method", "nearest_signed_surface") not in {"nearest_signed_surface", "radial_envelope", "radial_order"}:
            raise OutfitError("CONFIG_SCHEMA", "Unknown clearance method")
        for key in ("materials", "target_skin_materials", "subdivide_materials", "include_bone_prefixes", "target_bone_prefixes"):
            value = rule.get(key, [])
            if not isinstance(value, list) or not all(isinstance(n, str) and n for n in value):
                raise OutfitError("CONFIG_SCHEMA", f"{key} must be a list of nonempty names")
        if not set(rule["materials"]).issubset(selected) or not rule["materials"]:
            raise OutfitError("CONFIG_SCHEMA", "Clearance materials must be selected outfit materials")
        if not rule["target_skin_materials"] or not set(rule["target_skin_materials"]).issubset(target_materials - set(excluded)):
            raise OutfitError("CONFIG_SCHEMA", "Clearance skin materials must exist and remain in the target")
        for key in ("lower_bone", "upper_bone"):
            if rule[key] not in profile.get("common_bones", []):
                raise OutfitError("CONFIG_SCHEMA", f"Unknown anatomical landmark: {rule[key]}")
        for key, maximum in (("iterations", 20), ("subdivide", 3)):
            value = rule.get(key, 4 if key == "iterations" else 0)
            if type(value) is not int or not (1 if key == "iterations" else 0) <= value <= maximum:
                raise OutfitError("CONFIG_SCHEMA", f"Invalid {key}")
        for key in ("lower_offset", "upper_offset", "clearance", "max_distance", "max_displacement", "max_edge"):
            if key in rule:
                value = rule[key]
                if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                    raise OutfitError("CONFIG_SCHEMA", f"Invalid {key}")
                if "offset" not in key and not 0 < value <= 1:
                    raise OutfitError("CONFIG_SCHEMA", f"{key} must be in (0, 1] meters")
    patches = profile.get("surface_patches", [])
    if not isinstance(patches, list):
        raise OutfitError("CONFIG_SCHEMA", "surface_patches must be a list")
    for patch in patches:
        required = {"region", "material", "skin_material"}
        if not isinstance(patch, dict) or not required.issubset(patch) or set(patch) - required - {"margin", "lower_offset", "wrist_overlap", "include_skin_materials", "covered_skin"}:
            raise OutfitError("CONFIG_SCHEMA", "Invalid surface patch fields")
        if patch.get('covered_skin','retain') not in {'retain','opaque_backup'} or (patch.get('covered_skin')=='opaque_backup' and patch.get('region')!='hands'):
            raise OutfitError('CONFIG_SCHEMA','Opaque skin coverage is supported only for hand patches')
        if patch["region"] not in {"hands", "legs"} or patch["material"] not in selected or patch["skin_material"] not in target_materials - set(excluded):
            raise OutfitError("CONFIG_SCHEMA", "Invalid surface patch region/material")
        extra_skin = patch.get("include_skin_materials", [])
        if not isinstance(extra_skin, list) or not all(isinstance(n, str) and n in target_materials - set(excluded) for n in extra_skin):
            raise OutfitError("CONFIG_SCHEMA", "Included skin materials must remain in target")
        for key, lower, upper in (("margin", 0.0001, 0.02), ("lower_offset", -0.1, 0.1), ("wrist_overlap", -0.05, 0)):
            if key in patch:
                value = patch[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
                    raise OutfitError("CONFIG_SCHEMA", f"Invalid patch {key}")
    shoes = profile.get("shoe_fit")
    if shoes is not None:
        allowed = {"method", "materials", "collar_material", "skin_materials", "scale", "body_lift", "mask_depth", "ankle_rim_scale"}
        if isinstance(shoes, dict) and shoes.get("method") == "anatomical_foot_last":
            raise OutfitError("SHOE_METHOD_WITHDRAWN", "The old foot_last deforms shoes; inspect again for the closed-shoe profile")
        if not isinstance(shoes, dict) or set(shoes) != allowed or shoes.get("method") != "preserved_closed_shoe":
            raise OutfitError("CONFIG_SCHEMA", "Invalid shoe fitting method")
        materials = shoes.get("materials")
        if not isinstance(materials, list) or not materials or not all(isinstance(n, str) and n in selected for n in materials):
            raise OutfitError("CONFIG_SCHEMA", "Shoe materials must be selected")
        if shoes["collar_material"] not in selected or not isinstance(shoes["skin_materials"], list) or not shoes["skin_materials"] or not set(shoes["skin_materials"]).issubset(target_materials - set(excluded)):
            raise OutfitError("CONFIG_SCHEMA", "Closed shoes require source collar and retained target skin materials")
        for key, lower, upper in (("scale", .5, 1.5), ("body_lift", 0, .15), ("mask_depth", .001, .02), ("ankle_rim_scale", .6, 1)):
            if key in shoes:
                value = shoes[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
                    raise OutfitError("CONFIG_SCHEMA", f"Invalid shoe {key}")
    native_fit = profile.get("native_config", {}).get("fit", {})
    if (shoes or any(p["region"] == "hands" for p in patches)) and native_fit.get("fit_limbs", True):
        raise OutfitError("CONFIG_SCHEMA", "New hand/shoe methods require native_config.fit.fit_limbs=false")
    if shoes and (native_fit.get("fit_limb_ends", True) or native_fit.get("subdivide_shoe", 2) != 0
                  or native_fit.get("lay_shoe_on_foot", True) or native_fit.get("fit_shoe_radius", True)):
        raise OutfitError("CONFIG_SCHEMA", "Preserved shoes require all legacy shoe deformation and subdivision disabled")
    if any(p["region"] == "legs" for p in patches) and native_fit.get("project_layers"):
        raise OutfitError("CONFIG_SCHEMA", "Target leg patches require empty legacy project_layers")
    return profile


def _inventory(objects):
    ie = engine("import_export")
    meshes = ie.model_meshes(objects)
    arms = [o for o in objects if o.type == "ARMATURE"]
    # The existing backend uses cloth[0] and single body BVHs. Reject other
    # layouts until those paths have real multi-mesh support.
    if len(meshes) != 1 or len(arms) != 1:
        raise OutfitError("UNSUPPORTED_LAYOUT", "This version requires one skinned body mesh and one armature per PMX")
    for obj in [*meshes, *arms]:
        if any(abs(obj.matrix_world[r][c] - (1 if r == c else 0)) > 1e-5
               for r in range(4) for c in range(4)):
            raise OutfitError("UNSUPPORTED_TRANSFORM", f"Non-identity object transform: {obj.name}")
    if not meshes[0].data.polygons:
        raise OutfitError("EMPTY_MESH", "The body mesh has no faces")
    info = ie.model_info(objects)
    return info, meshes[0], arms[0]


def _parts(mesh):
    extraction = engine("extraction")
    bounds = extraction._scene_bbox([mesh])
    parts = extraction.classify_parts(extraction.enumerate_parts([mesh]),
                                     bounds[1][2] - bounds[0][2], bounds)
    return parts, extraction.material_table(parts)


def _settings(preset, material_names):
    # Do not let the legacy engine's character-specific defaults leak into
    # another character. The old preset is opt-in and recorded in the profile.
    config = {"fit": {"project_layers": [], "fit_paint_layers": []},
              "motion": {"enabled": False}, "physics": {"enabled": True},
              "body_mask": {"enabled": False, "hair": False}}
    if preset == "keqing_daniya":
        if not {"腿", "服", "服+jinshu"}.issubset(material_names):
            raise OutfitError("PRESET_MISMATCH", "Keqing preset requires 腿 / 服 / 服+jinshu materials")
        config["fit"]["fit_limbs"] = False
    return config


def inspect(request, progress):
    ie = engine("import_export")
    progress("dependency_check")
    module = ie.ensure_mmd_tools()
    ie.clear_scene()
    progress("import_source")
    src = ie.import_pmx(request["source"])
    src_info, src_mesh, src_arm = _inventory(src)
    progress("import_target")
    tgt = ie.import_pmx(request["target"])
    tgt_info, tgt_mesh, tgt_arm = _inventory(tgt)
    parts, materials = _parts(src_mesh)
    common = sorted(set(src_arm.data.bones.keys()) & set(tgt_arm.data.bones.keys()))
    required = {"上半身", "下半身", "腕.L", "腕.R", "足.L", "足.R"}
    if not required.issubset(common):
        raise OutfitError("RIG_MAP_REQUIRED", f"Missing common anatomical bones: {sorted(required - set(common))}")
    suggested = engine("extraction").suggest_selection(parts, materials)["selected_materials"]
    # Accessories attached to the head are not clothes by default.
    suggested = [name for name in suggested if not any(
        word in name.lower() for word in ("发", "髪", "hair"))]
    if not suggested:
        raise OutfitError("SELECTION_REQUIRED", "No high-confidence clothing candidates; inspect the inventory manually")
    preset = request.get("preset", "conservative")
    profile = {"schema_version": 1, "kind": "mmd_outfit_pair", "preset": preset,
               "backend": "legacy_mmd", "common_bones": common,
               "selected_materials": suggested, "materials": materials,
               "native_config": _settings(preset, {m["material"] for m in materials}),
               "notes": ["Material selection is a suggestion; review before production use.",
                         "Body masking defaults to off so geometry problems remain visible.",
                         "legacy_mmd reuses the existing fitting algorithm; it is not a new universal solver."]}
    profile["target_materials"] = tgt_info["materials"]
    profile["target_exclude_materials"] = []
    profile["clearance_rules"] = []
    profile["surface_patches"] = []
    if preset == "keqing_daniya":
        if not {"Body", "材质", "丝袜"}.issubset(tgt_info["materials"]):
            raise OutfitError("PRESET_MISMATCH", "Daniya preset requires Body / 材质 / 丝袜 target materials")
        # This pair's 材质 is the white torso garment; 连衣裙通用 is a head
        # accessory despite its name. Never apply this rule to other presets.
        profile["target_exclude_materials"] = ["材质", "丝袜"]
        profile['arm_rest']={'method':'anatomical_upper_arm'}
        profile["clearance_rules"] = [{"name": "torso", "materials": ["服", "服+jinshu"],
            "target_skin_materials": ["Body"], "lower_bone": "下半身", "upper_bone": "首",
            "upper_offset": -0.012, "clearance": 0.006,
            "max_distance": 0.10, "max_displacement": 0.10, "iterations": 8,
            "method": "radial_order",
            "include_bone_prefixes": ["胸", "おっぱい"],
            "target_bone_prefixes": ["上半身", "下半身", "胸", "乳", "おっぱい"],
            "subdivide": 2, "subdivide_materials": ["服"], "max_edge": 0.012}]
        profile["surface_patches"] = [
            {"region": "hands", "material": "服", "skin_material": "Body", "margin": .0015, "wrist_overlap": -.018,
             "covered_skin": "opaque_backup",
             "include_skin_materials": ["Nails"] if "Nails" in tgt_info["materials"] else []},
            {"region": "legs", "material": "腿", "skin_material": "Body", "margin": .0015, "lower_offset": -.035}]
        profile["shoe_fit"] = {"method": "preserved_closed_shoe", "materials": ["服", "服+jinshu"],
                              "collar_material": "腿", "skin_materials": ["Body", "Nails"],
                              "scale": 1.2, "body_lift": .012, "mask_depth": .006, "ankle_rim_scale": .75}
        profile["native_config"]["fit"].update({"fit_limb_ends": False, "subdivide_shoe": 0,
            "lay_shoe_on_foot": False, "fit_shoe_radius": False})
        profile["notes"].append("Closed-shoe mode masks only shoe-covered foot surfaces; a hidden recoverable foot mesh is retained in the Blend.")
    for side, info in (("source", src_info), ("target", tgt_info)):
        profile[side] = {"path": request[side], "sha256": digest(request[side]),
                         "counts": info["counts"]}
    directory = Path(request["job_dir"])
    write_json(directory / "profile.json", profile)
    write_json(directory / "inventory.json", {"source": src_info, "target": tgt_info})
    return {"state": "COMPLETED", "ok": True, "accepted": False,
            "profile": str(directory / "profile.json"), "mmd_tools": module,
            "blender": bpy.app.version_string, "selected_materials": suggested,
            "warnings": ["Profile prepared. Fitting and visual/motion acceptance have not run."]}


def prepare_target(mesh, excluded):
    """Remove only explicit old outfit materials and compact their unused verts.

    Keep the original object, parent, modifiers and MMD morph references.
    """
    if not excluded:
        return {"excluded_materials": [], "faces_removed": 0}
    names = {slot.name for slot in mesh.data.materials if slot}
    if set(excluded) - names:
        raise OutfitError("UNKNOWN_MATERIAL", "Target material selection changed during import")
    faces = [face.index for face in mesh.data.polygons
             if mesh.data.materials[face.material_index].name not in excluded]
    if not faces:
        raise OutfitError("EMPTY_TARGET", "Target exclusion would remove every face")
    before = len(mesh.data.polygons)
    copy, _ = engine("garment")._copy_mesh_subset(mesh, faces, "PreparedTarget")
    group_names = [group.name for group in copy.vertex_groups]
    # clear() edits deform data, so do it before attaching the shared new mesh.
    mesh.vertex_groups.clear()
    mesh.data = copy.data
    # Group membership lives in the new Mesh; rebuilding identical index/name
    # entries attaches it to the retained object without touching the weights.
    for name in group_names:
        if name not in mesh.vertex_groups:
            mesh.vertex_groups.new(name=name)
    bpy.data.objects.remove(copy, do_unlink=True)
    return {"excluded_materials": excluded, "faces_removed": before - len(faces),
            "vertices_after": len(mesh.data.vertices)}


def _static_validation(objects, expected=None):
    ie = engine("import_export")
    info = ie.model_info(objects)
    skin = engine("qa").skinning_report(objects)
    failures = []
    bone_names = {bone.name for obj in objects if obj.type == "ARMATURE"
                  for bone in obj.data.bones}
    rigids = {obj for obj in objects if getattr(obj, "mmd_type", "NONE") == "RIGID_BODY"}
    joints = [obj for obj in objects if getattr(obj, "mmd_type", "NONE") == "JOINT"]
    for rigid in rigids:
        bone = rigid.mmd_rigid.bone
        if bone and bone not in bone_names:
            failures.append({"code": "RIGID_BONE_MISSING", "object": rigid.name, "bone": bone})
    for joint in joints:
        constraint = joint.rigid_body_constraint
        if constraint is None or constraint.object1 not in rigids or constraint.object2 not in rigids:
            failures.append({"code": "JOINT_ENDPOINT_MISSING", "object": joint.name})
    for mesh in skin["meshes"]:
        if mesh["unweighted_vertices"] or mesh["unknown_bone_count"] or mesh["bad_weight_sum_vertices"]:
            failures.append({"code": "SKINNING", "detail": mesh})
    if expected:
        for key in ("vertices", "faces", "bones"):
            if expected["counts"][key] != info["counts"][key]:
                failures.append({"code": "ROUNDTRIP_COUNTS", "field": key,
                                 "before": expected["counts"][key], "after": info["counts"][key]})
    missing = [p for p in info["textures"] if not Path(p).is_file()]
    return {"counts": info["counts"], "physics_references": {"rigid_bodies": len(rigids), "joints": len(joints)},
            "skinning": skin, "failures": failures,
            "missing_textures": missing}


def _validate_config(config):
    defaults = engine("dressing").DEFAULT_CONFIG
    if not isinstance(config, dict) or set(config) - set(defaults):
        raise OutfitError("CONFIG_SCHEMA", "Unknown native_config section")
    for section, settings in config.items():
        if not isinstance(settings, dict) or set(settings) - set(defaults[section]):
            raise OutfitError("CONFIG_SCHEMA", f"Unknown settings in {section}")
        for key, value in settings.items():
            default = defaults[section][key]
            if isinstance(default, bool) and not isinstance(value, bool):
                raise OutfitError("CONFIG_SCHEMA", f"{section}.{key} must be boolean")
            if isinstance(default, (float, int)) and not isinstance(default, bool):
                if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
                    raise OutfitError("CONFIG_SCHEMA", f"{section}.{key} must be a finite nonnegative number")
            if isinstance(default, str) and not isinstance(value, str):
                raise OutfitError("CONFIG_SCHEMA", f"{section}.{key} must be text")
            if isinstance(default, (list, tuple)) and not isinstance(value, list):
                raise OutfitError("CONFIG_SCHEMA", f"{section}.{key} must be a list")
    if config.get("motion", {}).get("enabled"):
        raise OutfitError("CONFIG_SCHEMA", "Run motion validation after export, not inside the export pipeline")


def fit(request, progress):
    ie, dressing = engine("import_export"), engine("dressing")
    directory = Path(request["job_dir"])
    progress("profile_check")
    profile = load_profile(request["profile"])
    if profile.get("backend") != "legacy_mmd":
        raise OutfitError("BACKEND_UNAVAILABLE", "Version 0.4 supports the recorded legacy_mmd backend only")
    if request.get('ground_motion') and profile.get('shoe_fit',{}).get('method')!='preserved_closed_shoe':
        raise OutfitError('GROUNDING_REQUIRES_SHOES','Motion grounding requires the preserved closed-shoe mode')
    config = profile.get("native_config", {})
    _validate_config(config)
    # Every effective parameter, including defaults, is recorded with the job.
    effective = json.loads(json.dumps(dressing.DEFAULT_CONFIG))
    for section, values in config.items():
        effective[section].update(values)
    if 'cuff_physics' in request:profile['cuff_physics']=request['cuff_physics']
    if profile.get('cuff_physics'):
        if profile.get('preset')!='keqing_daniya' or profile.get('arm_rest')!={'method':'anatomical_upper_arm'}:
            raise OutfitError('CUFF_PRESET_REQUIRED','Cuff physics requires the Keqing/Daniya anatomical arm profile')
        if not effective['physics']['enabled']:
            raise OutfitError('CUFF_PHYSICS_DISABLED','Cuff physics requires physics migration')
    write_json(directory / "effective_config.json", effective)
    write_json(directory / "profile_snapshot.json", profile)
    ie.clear_scene()
    progress("import_source")
    src = ie.import_pmx(profile["source"]["path"])
    _inventory(src)
    progress("import_target")
    tgt = ie.import_pmx(profile["target"]["path"])
    _, target_mesh, _ = _inventory(tgt)
    progress("prepare_target")
    preparation = prepare_target(target_mesh, profile.get("target_exclude_materials", []))
    shoe_state = None
    if profile.get("shoe_fit"):
        from .preserved_shoe import prepare
        source_mesh = ie.model_meshes(src)[0]
        source_arm = next(obj for obj in src if obj.type == "ARMATURE")
        target_arm = next(obj for obj in tgt if obj.type == "ARMATURE")
        progress("prepare_closed_shoes")
        shoe_state = prepare(source_mesh, source_arm, target_mesh, target_arm, tgt,
                             profile["shoe_fit"], ie.model_meshes, engine("garment")._copy_mesh_subset,
                             dressing.apply_positions)
        preparation["closed_shoes"] = shoe_state["report"]
    write_json(directory / "target_preparation.json", preparation)
    parts, _ = _parts(ie.model_meshes(src)[0])
    selection = {"selected_materials": profile["selected_materials"],
                 "selected_parts": [p["id"] for p in parts if p["material"] in profile["selected_materials"]]}
    actual = {p["material"] for p in parts if p["id"] in selection["selected_parts"]}
    if actual != set(profile["selected_materials"]):
        raise OutfitError("SELECTION_CHANGED", "Imported material names no longer match the profile")
    write_json(directory / "selection.json", selection)
    output = directory / "model"
    rules = profile.get("clearance_rules", [])
    adaptations = {}
    def refine_rest(source_arm,target_arm,deltas):
        from .arm_rest import apply
        adaptations['arm_rest']=apply(source_arm,target_arm,deltas)
    def refine_physics(clothes,armature):
        from .cuff_physics import build
        progress('generate_cuff_physics')
        try:report=build(clothes[0],armature,engine('physics'))
        except ValueError as exc:raise OutfitError('CUFF_PHYSICS_FAILED',str(exc)) from exc
        adaptations['cuff_physics']=report
        write_json(directory/'adaptation_report.json',adaptations)
        return report
    def refine(clothes, bodies):
        from .surface_fit import apply_rules
        armature = next(obj for obj in tgt if obj.type == "ARMATURE")
        if profile.get("surface_patches"):
            from .skin_patch import rebuild
            adaptations["patches"] = [rebuild(clothes[0], bodies[0], armature, rule, engine("garment")._copy_mesh_subset,
                                              engine('garment').split_uv_vertices)
                                       for rule in profile["surface_patches"]]
        refinement = apply_rules(clothes[0], bodies[0], armature, set(profile["common_bones"]),
                                 rules, dressing.apply_positions, dressing.subdivide_triangles)
        if shoe_state:
            from .preserved_shoe import attach
            adaptations["shoes"] = attach(shoe_state, clothes[0], armature,
                engine("garment")._copy_mesh_subset, profile["shoe_fit"]["materials"])
        write_json(directory / "adaptation_report.json", adaptations)
        return refinement
    result = dressing.run(src, tgt, str(output),
                          config_path=str(directory / "effective_config.json"),
                          selection=selection, progress=progress,
                          fit_backend=refine if rules or profile.get("surface_patches") or profile.get("shoe_fit") else None,
                          rest_backend=refine_rest if profile.get('arm_rest') else None,
                          physics_backend=refine_physics if profile.get('cuff_physics') else None)
    if not result.get("pmx") or not Path(result["pmx"]).is_file():
        raise OutfitError("EXPORT_FAILED", "PMX export failed; see model/manifest.json")
    progress("roundtrip_check")
    # These are all remaining model objects: the source was removed by run().
    expected = ie.model_info(list(bpy.data.objects))
    ie.clear_scene()
    again = ie.import_pmx(result["pmx"])
    validation = _static_validation(again, expected)
    if profile.get('cuff_physics'):
        from .cuff_physics import validate as validate_cuff
        validation['cuff_physics']=validate_cuff(ie.model_meshes(again)[0],next(o for o in again if o.type=='ARMATURE'),again,adaptations['cuff_physics'])
        validation['failures'].extend(validation['cuff_physics']['failures'])
    if shoe_state:
        from .preserved_shoe import exported_vertices,vertex_morph_report
        try:
            shoe_mesh=ie.model_meshes(again)[0]
            shoe_ids=exported_vertices(shoe_mesh,adaptations['shoes']['reference_positions'],profile['shoe_fit']['materials'])
            morph_check=vertex_morph_report(shoe_mesh,shoe_ids)
            validation['preserved_shoes']={'vertices':len(shoe_ids),'vertex_morphs':morph_check}
            if morph_check['changed_keys']:
                validation['failures'].append('Rigid shoes change shape under vertex morphs')
        except ValueError as exc:
            validation['failures'].append(str(exc))
    write_json(directory / "validation.json", validation)
    warnings = []
    if profile.get('cuff_physics'):
        warnings.append('Experimental cuff particles require physical simulation. Static Blend/VMD previews do not show the collision response; residual sleeve and ribbon intersections remain possible.')
    if shoe_state:
        warnings.append("Closed shoes replace hidden foot surfaces; the Blend retains a foot backup. Rigid ankle binding does not support toe bending or open shoes.")
    for patch in adaptations.get('patches',[]):
        coverage=patch.get('skin_coverage',{})
        if coverage.get('masked_skin_faces'):
            warnings.append(f"Opaque glove coverage backs up {coverage['masked_skin_faces']} corresponding skin faces in the Blend. This dressed export has no automatic glove removal/alpha fade.")
    if result["physics"].get("joints_skipped", 0):
        warnings.append(f"Physics migration skipped {result['physics']['joints_skipped']} source joints; see manifest")
    refinements = result["fit"].get("external_backend", [])
    for refinement in refinements:
        remaining = refinement["after"]["violating_vertices"]
        if remaining or refinement["after"]["unavailable_vertices"]:
            warnings.append(f"Clearance rule {refinement['rule']}: {remaining} violating vertices, "
                            f"{refinement['after']['unavailable_vertices']} outside reference coverage; see manifest")
    if validation["missing_textures"]:
        warnings.append("Missing textures; see validation.json")
    if request.get("render", True):
        progress("preview")
        result["images"] = engine("extraction").render_objects(
            ie.model_meshes(again), directory / "preview", width=600, height=800,
            prefix="dressed")
        from .preview import details
        result["images"] += details(again, directory / "preview", engine("extraction"))
    motion_valid = True
    effective_motion=request.get('motion')
    grounding=None
    if request.get('ground_motion'):
        from .motion_grounding import ground
        progress('ground_motion')
        ie.clear_scene(); bpy.context.scene.frame_set(1)
        again=ie.import_pmx(result['pmx'])
        try:
            grounding=ground(ie.model_meshes(again)[0],next(o for o in again if o.type=='ARMATURE'),
                request['motion'],directory/'motion/grounded.vmd',profile['shoe_fit']['materials'],engine,
                reference_points=adaptations['shoes']['reference_positions'],notify=progress)
        except ValueError as exc:
            raise OutfitError('MOTION_GROUNDING_FAILED',str(exc)) from exc
        write_json(directory/'motion/grounding_report.json',grounding)
        effective_motion=grounding['motion']
        warnings.append('Grounded VMD moves the whole character vertically; use effective_motion with this PMX. Original VMD is unchanged.')
    if request.get("motion"):
        progress("motion_check")
        # A new import gives QA a clean model after preview setup.
        ie.clear_scene()
        bpy.context.scene.frame_set(1)
        again = ie.import_pmx(result["pmx"])
        qa = engine("qa").run_qa(again, motions=effective_motion,
                                out_dir=str(directory / "motion"),
                                garment_materials=profile["selected_materials"])
        coverage=[p['skin_coverage'] for p in adaptations.get('patches',[]) if p.get('skin_coverage',{}).get('masked_skin_faces')]
        if coverage:
            qa['skin_coverage']={'regions':coverage,
                'comparison_note':'Covered skin is absent from candidates. Do not compare penetration ratios with an unmasked body as equivalent coverage.'}
            write_json(directory/'motion/qa_report.json',qa)
        result["motion_status"] = qa["status"]
        motion_valid = qa["status"] not in {"FAILED", "UNKNOWN"}
        if qa["status"] != "OK":
            warnings.append(f"Motion QA: {qa['status']}")
    else:
        warnings.append("Motion not checked: no VMD supplied")
    # A completed geometry job is never silently promoted to visual approval.
    warnings.append("Visual review required, especially hands, shoes, sleeve openings and skirt")
    success = not validation["failures"] and motion_valid
    return {"pmx": result["pmx"], "blend": result["blend"],
            'effective_motion':effective_motion,'grounding_report':str(directory/'motion/grounding_report.json') if grounding else None,
            "images": result.get("images", []), "motion_status": result.get("motion_status", "NOT_RUN"),
            "summary": {"counts": validation["counts"],
                        "mapped_body_bones": len(result["rig_map"]["mapped_body_bones"]),
                        "created_garment_bones": len(result["rig_map"]["created_bones"]),
                        "rigid_bodies_migrated": result["physics"].get("rigid_bodies", 0),
                        "joints_migrated": result["physics"].get("joints", 0)},
            "manifest": str(output / "manifest.json"),
            "clearance": refinements,
            "adaptations": adaptations,
            "state": "REVIEW_REQUIRED" if success else "FAILED",
            "ok": success, "accepted": False, "validation": str(directory / "validation.json"),
            "warnings": warnings, "backend": "legacy_mmd",
            "error": None if success else {"code": "VALIDATION_FAILED", "message": "Roundtrip, skinning or requested motion validation failed"}}


def validate(request, progress):
    ie = engine("import_export")
    progress("import_model")
    ie.clear_scene()
    objects = ie.import_pmx(request["model"])
    progress("static_check")
    validation = _static_validation(objects)
    directory = Path(request["job_dir"])
    write_json(directory / "validation.json", validation)
    materials = None
    if request.get("profile"):
        materials = load_profile(request["profile"])["selected_materials"]
    if request.get("motion") and not materials:
        # A joined PMX cannot distinguish clothes from skin without its profile.
        raise OutfitError("PROFILE_REQUIRED", "Motion validation requires the outfit profile")
    motion = None
    if request.get("motion"):
        progress("motion_check")
        motion = engine("qa").run_qa(objects, request["motion"], str(directory / "motion"), materials)
    success = not validation["failures"] and (motion is None or motion["status"] not in {"FAILED", "UNKNOWN"})
    return {"state": "REVIEW_REQUIRED" if success else "FAILED", "ok": success,
            "accepted": False, "validation": validation,
            "motion_status": motion["status"] if motion else "NOT_RUN"}


def execute(request, progress):
    if not bpy.app.background:
        raise OutfitError("ISOLATION_REQUIRED", "Run this service through jobs.submit() in a background process")
    return {"inspect": inspect, "fit": fit, "validate": validate}[request["action"]](request, progress)
