"""Only entry point for Blender subprocesses; never run in the user's scene."""
import argparse
import sys
from pathlib import Path
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mmd_outfit.jobs import read_json, write_json, VERSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    request = read_json(args.request)
    directory = Path(request["job_dir"])
    result = {"schema_version": 1, "version": VERSION, "action": request["action"],
              "job_dir": str(directory), "ok": False, "accepted": False}

    def progress(stage):
        write_json(directory / "status.json", {"state": "RUNNING", "stage": stage})
        print(f"[MMD Outfit] {stage}", flush=True)

    try:
        from mmd_outfit.service import execute
        result.update(execute(request, progress))
    except Exception as exc:
        result.update(state="FAILED", error={"code": getattr(exc, "code", type(exc).__name__),
                      "message": str(exc), "stage": read_json(directory / "status.json").get("stage")})
        (directory / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        traceback.print_exc()
    write_json(directory / "result.json", result)
    write_json(directory / "status.json", {"state": result["state"], "stage": "finished"})
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
