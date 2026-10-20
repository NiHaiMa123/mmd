"""Entry point that runs INSIDE Blender.

    blender -b --python scripts/blender_runner.py -- --mode inspect --result out.json

Every mode writes a JSON result file so the outer CLI can consume it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _garment_materials(out_dir: str | None) -> list[str] | None:
    """Read the selected outfit materials from a dress manifest.

    The manifest lives in the dress output directory, but the motion check
    usually writes into a sub directory of it, so look a few levels up.
    """
    if not out_dir:
        return None
    base = Path(out_dir).resolve()
    for _ in range(4):
        manifest = base / "manifest.json"
        if manifest.exists():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            return data.get("selection", {}).get("selected_materials", [])
        if base.parent == base:
            break
        base = base.parent
    return None


def _parse() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    ap = argparse.ArgumentParser(prog="blender_runner")
    ap.add_argument("--mode", required=True)
    ap.add_argument("--result", required=True)
    ap.add_argument("--source", default=None)
    ap.add_argument("--target", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--selection", default=None)
    ap.add_argument("--motions", default=None)
    ap.add_argument("--scale", type=float, default=None)
    ap.add_argument("--keep-scene", action="store_true")
    ap.add_argument("--stages", action="store_true",
                    help="render a preview after every pipeline step")
    ap.add_argument("--repair", action="store_true",
                    help="widen the body mask where the clothes get pierced")
    return ap.parse_args(args=argv)


def main() -> int:
    args = _parse()
    result: dict = {"ok": False, "mode": args.mode}
    try:
        from src import import_export as ie

        if args.mode == "inspect":
            ie.clear_scene()
            src_objs = []
            if args.source:
                src_objs += ie.import_pmx(args.source)
            tgt_objs = []
            if args.target:
                tgt_objs += ie.import_pmx(args.target)
            result["source"] = ie.model_info(src_objs)
            result["target"] = ie.model_info(tgt_objs)
            result["ok"] = True

        elif args.mode == "roundtrip":
            # P1-00 step 4: import -> export -> re-import -> compare
            ie.clear_scene()
            objs = ie.import_pmx(args.source)
            info = ie.model_info(objs)
            out_dir = Path(args.out or (REPO_ROOT / "outputs" / "roundtrip"))
            out_dir.mkdir(parents=True, exist_ok=True)
            pmx_path = str(out_dir / "roundtrip.pmx")
            ie.export_pmx(pmx_path, objs)
            ie.clear_scene()
            again = ie.import_pmx(pmx_path)
            info2 = ie.model_info(again)
            result["first"] = info
            result["second"] = info2
            result["pmx"] = pmx_path
            result["counts_match"] = (info["counts"]["vertices"]
                                     == info2["counts"]["vertices"]
                                     and info["counts"]["bones"]
                                     == info2["counts"]["bones"])
            result["ok"] = True

        elif args.mode == "extract-preview":
            from src import extraction
            ie.clear_scene()
            objs = ie.import_pmx(args.source)
            result.update(extraction.extract_preview(objs, args.out))
            result["ok"] = True

        elif args.mode == "extract":
            from src import extraction, garment
            ie.clear_scene()
            objs = ie.import_pmx(args.source)
            body = ie.model_meshes(objs)
            parts = extraction.enumerate_parts(body)
            bbox = extraction._scene_bbox(body)
            height = bbox[1][2] - bbox[0][2]
            classified = extraction.classify_parts(parts, height, bbox)
            if args.selection and Path(args.selection).exists():
                selection = json.loads(Path(args.selection).read_text(
                    encoding="utf-8"))
            else:
                selection = extraction.suggest_selection(
                    classified, extraction.material_table(classified))
            res = garment.extract_clothing(objs, classified,
                                           selection.get("selected_parts", []),
                                           args.out)
            result.update(res["summary"])
            for o in body:
                o.hide_render = True
            imgs = extraction.render_objects(res["cloth"],
                                             Path(args.out) / "preview",
                                             prefix="cloth")
            for o in body:
                o.hide_render = False
            result["images"] = imgs
            blend = Path(args.out) / "cloth.blend"
            bpy.ops.wm.save_as_mainfile(filepath=str(blend))
            result["blend"] = str(blend)
            result["ok"] = True

        elif args.mode == "motion-check":
            from src import motion
            ie.clear_scene()
            objs = ie.import_pmx(args.source)
            materials = _garment_materials(args.out)
            if args.motions:
                if args.repair:
                    export = (str(Path(args.out) / "model_repaired.pmx")
                              if args.out else None)
                    result.update(motion.repair_motion(
                        objs, args.motions, materials, args.out,
                        export_path=export))
                else:
                    result.update(motion.sample_motion(objs, args.motions,
                                                      materials))
            elif args.repair:
                export = (str(Path(args.out) / "model_repaired.pmx")
                          if args.out else None)
                result.update(motion.repair_and_verify(
                    objs, materials, args.out, export_path=export))
            else:
                result.update(motion.run_pose_suite(objs, materials, args.out))
            result["ok"] = True

        elif args.mode == "dress":
            from src import dressing, extraction
            ie.clear_scene()
            src_objs = ie.import_pmx(args.source)
            tgt_objs = ie.import_pmx(args.target)
            selection = None
            if args.selection and Path(args.selection).exists():
                selection = json.loads(Path(args.selection).read_text(
                    encoding="utf-8"))
            result.update(dressing.run(src_objs, tgt_objs, args.out,
                                       config_path=args.config,
                                       selection=selection,
                                       stages=args.stages))
            # preview of the dressed result
            body = ie.model_meshes(tgt_objs)
            if body:
                imgs = extraction.render_objects(body, Path(args.out) / "preview",
                                                 prefix="dressed")
                result["images"] = imgs

            # P1-07: the exported PMX has to load again on its own
            if result.get("pmx"):
                try:
                    ie.clear_scene()
                    again = ie.import_pmx(result["pmx"])
                    info = ie.model_info(again)
                    result["reimport"] = {
                        "counts": info["counts"],
                        "materials": info["materials"],
                        "textures": len(info["textures"]),
                        "missing_textures": [t for t in info["textures"]
                                             if not Path(t).exists()],
                    }
                except Exception as exc:            # noqa: BLE001
                    result["reimport"] = {"error": f"{type(exc).__name__}: {exc}"}
            result["ok"] = True

        elif args.mode == "qa":
            from src import qa
            ie.clear_scene()
            objs = ie.import_pmx(args.source)
            result.update(qa.run_qa(objs, motions=args.motions,
                                    out_dir=args.out,
                                    garment_materials=_garment_materials(args.out)))
            result["ok"] = True

        else:
            result["error"] = f"unknown mode {args.mode}"

    except Exception as exc:                       # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
    finally:
        out = Path(args.result)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print("[blender_runner] wrote", out)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
