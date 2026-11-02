"""Run the actual distributed ZIP against local assets, without source imports.

All input paths are arguments; no private assets are included in the release.
"""
import argparse
import json
from pathlib import Path
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_outfit_addon import build


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    for name in ("blender", "source", "target", "motion", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument('--ground-motion',action='store_true')
    parser.add_argument('--cuff-physics',action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    package_dir = output / ("release_env_" + uuid.uuid4().hex[:8])
    with zipfile.ZipFile(build()) as archive:
        archive.extractall(package_dir)
    sys.path.insert(0, str(package_dir))
    from mmd_outfit.jobs import run, write_json
    import mmd_outfit
    assert package_dir in Path(mmd_outfit.__file__).parents
    assert "src.dressing" not in sys.modules
    prepared = run({"action": "inspect", "source": args.source, "target": args.target,
                    "output_root": str(output), "preset": "keqing_daniya",
                    "render": False, "timeout": 300}, args.blender)
    print(json.dumps({"inspect": prepared}, ensure_ascii=False), flush=True)
    if not prepared.get("ok"):
        raise RuntimeError("Packaged preflight failed")
    result = run({"action": "fit", "profile": prepared["profile"],
                  "motion": args.motion, "output_root": str(output),
                  'ground_motion':args.ground_motion,
                  'cuff_physics':args.cuff_physics,
                  "render": True, "timeout": 1800}, args.blender)
    report = {"packaged_module": str(mmd_outfit.__file__), "inspect": prepared, "fit": result,
              "visual_acceptance": "NOT_AUTOMATICALLY_APPROVED"}
    write_json(output / "release_e2e.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if not result.get("ok"):
        raise RuntimeError("Packaged transfer failed structural or requested validation")
    if args.cuff_physics:
        cuff=result['adaptations']['cuff_physics']
        assert len(cuff['created_bones'])==16 and cuff['added_rigids']==16 and cuff['added_joints']==32
        validation=json.loads(Path(result['validation']).read_text(encoding='utf-8'))
        assert not validation['cuff_physics']['failures']
        assert validation['cuff_physics']['weighted_vertices']>0
    arm_rest=result['adaptations'].get('arm_rest',{})
    if arm_rest.get('method')!='anatomical_upper_arm' or not arm_rest.get('overridden_bones'):
        raise RuntimeError('Keqing/Daniya release must exercise anatomical sleeve rest mapping')
    hand = next(p for p in result['adaptations']['patches'] if p['region']=='hands')
    if not hand.get('skin_coverage',{}).get('masked_skin_faces'):
        raise RuntimeError('Keqing/Daniya release must exercise opaque glove coverage, not silently retain every skin face')
    qa=json.loads((Path(result['job_dir'])/'motion/qa_report.json').read_text(encoding='utf-8'))
    if not qa.get('skin_coverage'):
        raise RuntimeError('Covered-skin sampling limits must be annotated in motion QA')
    if args.ground_motion:
        grounding=json.loads(Path(result['grounding_report']).read_text(encoding='utf-8'))
        assert grounding['verified_frames']==grounding['frames']
        assert grounding['min_height_verified_m']>=grounding['clearance_m']-1e-5
        assert result['effective_motion']!=args.motion


if __name__ == "__main__":
    main()
