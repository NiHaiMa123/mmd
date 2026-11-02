"""Stable CLI shared with the Blender panel. JSON requests are also supported."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))
from mmd_outfit.jobs import read_json, run, VERSION


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=f"MMD Outfit Bridge {VERSION}")
    parser.add_argument("--blender", required=True)
    parser.add_argument("--request", help="JSON request file; mutually exclusive with command flags")
    parser.add_argument("--action", choices=["inspect", "fit", "validate"])
    for name in ("source", "target", "profile", "model", "motion", "output-root"):
        parser.add_argument("--" + name)
    parser.add_argument("--preset", choices=["conservative", "keqing_daniya"])
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument('--ground-motion',action='store_true',default=None)
    parser.add_argument('--cuff-physics',action='store_true',default=None)
    args = vars(parser.parse_args())
    blender, request_file = args.pop("blender"), args.pop("request")
    no_render = args.pop("no_render")
    flags = {k: v for k, v in args.items() if v is not None}
    if request_file and (flags or no_render):
        parser.error("--request cannot be combined with command flags")
    request = read_json(request_file) if request_file else {**flags, "render": not no_render}
    try:
        result = run(request, blender)
    except Exception as exc:
        print(json.dumps({"ok": False, "state": "FAILED", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
