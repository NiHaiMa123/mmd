"""The distributed package must reject a known exploding-motion model."""
import argparse
import json
from pathlib import Path
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
for name in ("blender", "model", "profile", "motion", "output"):
    parser.add_argument("--" + name, required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
out = Path(args.output)
package = out / ("guard_package_" + uuid.uuid4().hex[:8])
package.mkdir(parents=True)
with zipfile.ZipFile(ROOT / "dist/mmd_outfit_bridge-0.9.0.zip") as archive:
    archive.extractall(package)
sys.path.insert(0, str(package))
from mmd_outfit.jobs import run, read_json, write_json
result = run({"action": "validate", "model": args.model, "profile": args.profile,
              "motion": args.motion, "render": False, "output_root": str(out), "timeout": 300}, args.blender)
report = read_json(Path(result["job_dir"]) / "motion/qa_report.json")
check = next(item for item in report["items"] if item["check"] == "motion_deformation")
assert not result["ok"] and result["state"] == "FAILED", result
assert check["status"] == "FAILED", check
write_json(out / "guard_regression.json", {"state": result["state"], "check": check,
    "deformation": report["motion"]["deformation"], "job_dir": result["job_dir"]})
print(json.dumps({"regression": "PASSED", "rejected_by": check}, ensure_ascii=True), flush=True)
