"""Command line interface (runs OUTSIDE Blender).

    python -m src.cli inspect   --source assets/source.pmx --target assets/base.pmx
    python -m src.cli roundtrip  --source assets/source.pmx --out outputs/roundtrip
    python -m src.cli extract-preview --source assets/source.pmx --out outputs/preview
    python -m src.cli dress      --source assets/source.pmx --target assets/base.pmx --out outputs/dress01
    python -m src.cli qa         --model outputs/dress01/model.pmx --motions assets/motions/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import blender_env

REPO_ROOT = Path(__file__).resolve().parent.parent


def _cmd_inspect(args) -> int:
    argv = ["--mode", "inspect", "--source", args.source]
    if args.target:
        argv += ["--target", args.target]
    res = blender_env.run_in_blender(
        "scripts/blender_runner.py", argv, blender=args.blender)
    blender_env.print_json(res)
    return 0 if res.get("ok") else 1


def _cmd_roundtrip(args) -> int:
    res = blender_env.run_in_blender(
        "scripts/blender_runner.py",
        ["--mode", "roundtrip", "--source", args.source, "--out", args.out],
        blender=args.blender)
    blender_env.print_json(res)
    return 0 if res.get("ok") else 1


def _cmd_extract_preview(args) -> int:
    res = blender_env.run_in_blender(
        "scripts/blender_runner.py",
        ["--mode", "extract-preview", "--source", args.source, "--out", args.out],
        blender=args.blender)
    blender_env.print_json(res)
    return 0 if res.get("ok") else 1


def _cmd_extract(args) -> int:
    argv = ["--mode", "extract", "--source", args.source, "--out", args.out]
    if args.selection:
        argv += ["--selection", args.selection]
    res = blender_env.run_in_blender(
        "scripts/blender_runner.py", argv, blender=args.blender)
    blender_env.print_json(res)
    return 0 if res.get("ok") else 1


def _cmd_motion_check(args) -> int:
    argv = ["--mode", "motion-check", "--source", args.model]
    if args.out:
        argv += ["--out", args.out]
    if args.motions:
        argv += ["--motions", args.motions]
    if args.repair:
        argv += ["--repair"]
    res = blender_env.run_in_blender(
        "scripts/blender_runner.py", argv, blender=args.blender)
    blender_env.print_json(res)
    return 0 if res.get("ok") else 1


def _cmd_closeup(args) -> int:
    argv = ["--mode", "closeup", "--source", args.model, "--out", args.out]
    if args.regions:
        argv += ["--regions", args.regions]
    if args.views:
        argv += ["--views", args.views]
    res = blender_env.run_in_blender(
        "scripts/blender_runner.py", argv, blender=args.blender)
    blender_env.print_json(res)
    return 0 if res.get("ok") else 1


def _cmd_dress(args) -> int:
    argv = ["--mode", "dress", "--source", args.source, "--target", args.target,
            "--out", args.out]
    if args.config:
        argv += ["--config", args.config]
    if args.selection:
        argv += ["--selection", args.selection]
    if args.stages:
        argv += ["--stages"]
    res = blender_env.run_in_blender(
        "scripts/blender_runner.py", argv, blender=args.blender)
    blender_env.print_json(res)
    return 0 if res.get("ok") else 1


def _cmd_qa(args) -> int:
    argv = ["--mode", "qa", "--source", args.model]
    if args.motions:
        argv += ["--motions", args.motions]
    if args.out:
        argv += ["--out", args.out]
    res = blender_env.run_in_blender(
        "scripts/blender_runner.py", argv, blender=args.blender)
    blender_env.print_json(res)
    return 0 if res.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="src.cli",
                                 description="MMD clothing transfer toolkit")
    ap.add_argument("--blender", default=None,
                    help="path to blender.exe (default: auto-detect)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("inspect", help="import and report model inventory")
    p.add_argument("--source", required=True)
    p.add_argument("--target", default=None)
    p.set_defaults(func=_cmd_inspect)

    p = sub.add_parser("roundtrip", help="import -> export -> re-import check")
    p.add_argument("--source", required=True)
    p.add_argument("--out", default=str(REPO_ROOT / "outputs" / "roundtrip"))
    p.set_defaults(func=_cmd_roundtrip)

    p = sub.add_parser("extract-preview",
                       help="list clothing candidates + render a preview")
    p.add_argument("--source", required=True)
    p.add_argument("--out", default=str(REPO_ROOT / "outputs" / "preview"))
    p.set_defaults(func=_cmd_extract_preview)

    p = sub.add_parser("extract", help="copy the selected parts into a garment mesh")
    p.add_argument("--source", required=True)
    p.add_argument("--out", default=str(REPO_ROOT / "outputs" / "extract01"))
    p.add_argument("--selection", default=None,
                   help="selection.json from extract-preview")
    p.set_defaults(func=_cmd_extract)

    p = sub.add_parser("closeup",
                       help="render every outfit part close up, from many angles")
    p.add_argument("--model", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--regions", default=None,
                   help="hands,feet,head,shoulders,sleeves,bodice,skirt")
    p.add_argument("--views", default=None,
                   help="front,back,left,right,top,bottom,q_left,q_right")
    p.set_defaults(func=_cmd_closeup)

    p = sub.add_parser("dress", help="transfer clothing onto the fixed base body")
    p.add_argument("--source", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--out", default=str(REPO_ROOT / "outputs" / "dress01"))
    p.add_argument("--config", default=None)
    p.add_argument("--selection", default=None,
                   help="selection.json from extract-preview")
    p.add_argument("--stages", action="store_true",
                   help="render a preview after every pipeline step")
    p.set_defaults(func=_cmd_dress)

    p = sub.add_parser("motion-check",
                       help="run the high risk pose suite and measure clipping")
    p.add_argument("--model", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--motions", default=None,
                   help="VMD to drive the check with a real motion")
    p.add_argument("--repair", action="store_true",
                   help="widen the body mask where the clothes get pierced "
                        "and write model_repaired.pmx")
    p.set_defaults(func=_cmd_motion_check)

    p = sub.add_parser("qa", help="static / motion checks on a produced model")
    p.add_argument("--model", required=True)
    p.add_argument("--motions", default=None)
    p.add_argument("--out", default=None,
                   help="output dir; manifest.json here tells QA which "
                        "materials belong to the garment")
    p.set_defaults(func=_cmd_qa)
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
