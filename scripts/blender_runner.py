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

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


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
    ap.add_argument("--motions", default=None)
    ap.add_argument("--scale", type=float, default=None)
    ap.add_argument("--keep-scene", action="store_true")
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

        elif args.mode == "dress":
            from src import dressing
            ie.clear_scene()
            src_objs = ie.import_pmx(args.source)
            tgt_objs = ie.import_pmx(args.target)
            result.update(dressing.run(src_objs, tgt_objs, args.out,
                                       config_path=args.config))
            result["ok"] = True

        elif args.mode == "qa":
            from src import qa
            ie.clear_scene()
            objs = ie.import_pmx(args.source)
            result.update(qa.run_qa(objs, motions=args.motions))
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
