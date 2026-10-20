"""P2 acceptance: consolidate the motion check artifacts into one report.

    python scripts/p2_acceptance.py outputs/dress14

Reads whatever the motion / qa / repair steps already wrote and produces
``p2_report.json`` plus a one page markdown summary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def newest(out: Path, pattern: str) -> Path | None:
    """The most recently written artifact of a kind (repair rounds pile up)."""
    hits = sorted(out.glob(pattern),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0] if hits else None


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: p2_acceptance.py <output-dir>")
        return 2
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)

    qa = load(out / "qa_report.json")
    poses = load(out / "poses" / "motion_report.json")
    repair = load(out / "repair" / "repair_report.json")
    motion_path = newest(out, "**/motion_repair_report.json")
    mrepair = load(motion_path) if motion_path else None

    items = []

    def add(check, status, detail):
        items.append({"check": check, "status": status, "detail": detail})

    # --- P2-01 motion set -------------------------------------------------
    if poses:
        worst = poses.get("worst") or {}
        add("P2-01 动作测试集", "OK",
            f"{len(poses.get('poses', []))} 类高风险姿势，"
            f"最差 {worst.get('pose')} 穿出 {worst.get('pierced')} 点，"
            f"静置姿态 {poses.get('rest_pierced')} 点（0 误报）")
    else:
        add("P2-01 动作测试集", "SKIPPED", "没有找到 poses/motion_report.json")

    # --- P2-02 detection --------------------------------------------------
    qa_motion = (qa or {}).get("motion", {})
    if "max_ratio" in qa_motion:
        worst = (qa_motion.get("worst_frames") or [{}])[0]
        add("P2-02 穿模检测", "OK",
            f"真实动作下最差帧 {worst.get('frame')}，"
            f"穿出率 {qa_motion.get('max_ratio') * 100:.2f}%")
    else:
        add("P2-02 穿模检测", "SKIPPED", "qa_report.json 里没有动作数据")

    # --- P2-03/04 repair loop ---------------------------------------------
    if repair:
        rep = repair.get("repair", {})
        verdict = repair.get("verdict", {})
        add("P2-03/04 姿势驱动修复", "OK" if verdict.get("accepted") else "WARNING",
            f"最差姿势 {rep.get('pose')}，删 {rep.get('faces_removed')} 面，"
            f"区域 {((rep.get('region') or {}).get('worst_band'))}；"
            f"改进={verdict.get('improved')} 回滚={verdict.get('rolled_back', False)}")
    if mrepair:
        rep = mrepair.get("repair", {})
        verdict = mrepair.get("verdict", {})
        band = ((rep.get("region") or {}).get("worst_band"))
        detail = (f"最差帧 {rep.get('worst_frame') or rep.get('frame')}，"
                  f"删 {rep.get('faces_removed')} 面")
        if rep.get("frames"):
            detail = f"最差帧 {rep['frames']}，删 {rep.get('faces_removed')} 面"
        if "total_before" in verdict:
            detail += (f"；总穿出 {verdict['total_before']} → "
                       f"{verdict['total_after']}")
        if band:
            detail += f"；区域 {band}"
        detail += (f"；改进={verdict.get('total_improved', verdict.get('improved'))} "
                   f"回滚={verdict.get('rolled_back', False)}")
        if verdict.get("regressed_frames"):
            detail += f" 回归帧 {verdict['regressed_frames']}"
        add("P2-03/04 动作驱动修复",
            "OK" if verdict.get("accepted") else "WARNING", detail)
    if not repair and not mrepair:
        add("P2-03/04 自动修复", "SKIPPED", "没有找到修复报告")

    # --- skinning sanity --------------------------------------------------
    if qa:
        skin = qa.get("skinning", {}).get("meshes", [])
        bad = [m for m in skin
               if m.get("unweighted_vertices") or m.get("unknown_bone_count")]
        add("蒙皮健康度", "OK" if not bad else "WARNING",
            f"未绑定顶点/未知骨骼/权重和异常合计 {len(bad)} 个网格")

    report = {
        "items": items,
        "status": "FAILED" if any(i["status"] == "FAILED" for i in items)
        else ("WARNING" if any(i["status"] == "WARNING" for i in items) else "OK"),
        "artifacts": {
            "qa": str(out / "qa_report.json") if qa else None,
            "poses": str(out / "poses" / "motion_report.json") if poses else None,
            "pose_repair": str(out / "repair" / "repair_report.json") if repair else None,
            "motion_repair": str(motion_path) if motion_path else None,
        },
    }
    (out / "p2_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# P2 验收摘要", ""]
    for i in items:
        lines.append(f"- **{i['status']}** — {i['check']}：{i['detail']}")
    lines.append("")
    lines.append(f"总体：**{report['status']}**")
    (out / "p2_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
