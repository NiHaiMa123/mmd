"""Package existing upstream-Jiggle trials; never simulate or alter the scenes."""
import hashlib
import html
import json
import struct
from pathlib import Path

ROOT = Path(r"E:\project\mmd\work\headswap_xl_codex\jiggle_naturalness_fix_20261102")
CASES = {
    "A_ellipsoids_only": "A：仅保留椭球碰撞",
    "B_smaller_radius": "B：椭球碰撞＋半径减半",
    "C_shorter_root": "C：再缩短非刘海固定区",
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def inspect_pc2(path):
    with path.open("rb") as stream:
        magic, version, count, start, rate, samples = struct.unpack("<12siiffi", stream.read(32))
    assert magic == b"POINTCACHE2\x00" and version == 1, path
    assert path.stat().st_size == 32 + count * samples * 12, path
    return dict(path=str(path), points=count, start_frame=start, sample_rate=rate, samples=samples)


motion = {row["name"]: row for row in read(ROOT / "motion_comparison.json")}
peak = {row["name"]: row for row in read(ROOT / "peak_orientation_review.json")}
snapshot = read(ROOT / "final_background_snapshot.json")
jobs = json.loads(snapshot["result"]["result"])
assert not jobs["active_jobs"], jobs
rows = []
for name, label in CASES.items():
    directory = ROOT / name
    config = read(directory / "configuration.json")
    receipt = read(directory / "bake_report.json")
    blend = Path(receipt["blend"])
    assert blend.is_file() and receipt["body_bone_max_error"] == 0
    plugin = Path(receipt["plugin"]["source_dir"]) / "__init__.py"
    assert hashlib.sha256(plugin.read_bytes()).hexdigest() == config["plugin_source_sha256"]
    depth = read(directory / "depth_target/intrusion_measurement.json")
    depths = [(max(row["maximum_vertex_inward_depth_cm"], row["maximum_face_centroid_inward_depth_cm"]), row["frame"]) for row in depth["frames"]]
    maximum, frame = max(depths)
    frame_paths = sorted((directory / "keyframes").glob("f*.png"))
    assert all((directory / f"keyframes/f{f:04d}.png").is_file() for f in (1, 331, 356, 376))
    rows.append(dict(
        case=name, label=label, blend=str(blend), status="UNRESOLVED_SHARP_BONE_SWING",
        frames=[1, 450], source_fps=30, chains=27, hair_bones=receipt["hair_bones"],
        active_bones=receipt["active_physics_bones"], body_error_m=motion[name]["body_error_m"],
        depth_sample_frames=[r["frame"] for r in depth["frames"]], depth_sample_count=len(depths),
        maximum_sampled_depth_cm=maximum, maximum_sampled_depth_frame=frame,
        sampled_frames_over_5cm=sum(d > 5 for d, _ in depths),
        peak_chain=peak[name]["chain"], peak_frame_pair=peak[name]["frames"],
        peak_bone_axis_swing_deg=max(b["y_axis_swing_deg"] for b in peak[name]["bones"]),
        largest_tip_step_cm=motion[name]["largest_tip_step_cm"],
        strain_flag_frames=motion[name]["strain_flag_frames"],
        pc2=[inspect_pc2(p) for p in sorted((directory / "cache").glob("*.pc2"))],
        stills=[dict(frame=int(p.stem[1:]), seconds=(int(p.stem[1:])-1)/30,
                     url=p.relative_to(ROOT).as_posix()) for p in frame_paths],
    ))

report = dict(
    status="ATTEMPT_COMPLETED_NATURALNESS_UNRESOLVED_STOPPED",
    cases=rows, all_registered_background_jobs_finished=True,
    scope="450 integer frames for body/motion; 101 integer frames for depth, including every frame 301..391; not all-time continuous contact acceptance",
    visuals="Normal full-character keyframe renders inspected. C strain flags do not establish conspicuous visible tearing at this full-body view.",
    interpretation="Sharp head-relative simulated bone-axis swings remain in every case; smaller radius and shorter fixed roots did not remove them. Bone-motion evidence rules out a purely display-roll explanation, but does not identify the underlying solver/contact/bake cause.",
    not_established=["natural reference quality", "all 450 frame contact acceptance", "subframe contact acceptance", "17.5 second dynamics", "specific solver root cause"],
    retained="Original files, body action including hug protection, hair weights, silver materials, full head and original upstream plugin solver preserved.",
    next_step="No fourth simulation launched. Diagnose reproducible sharp bone swings and establish a suitable maintained bone-physics workflow before rendering a final film.",
)
(ROOT / "attempt_result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

payload = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
page = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>完整头发 · 原版 Jiggle 三组尝试</title>
<style>body{margin:0;background:#15161a;color:#eee;font:16px/1.6 system-ui,sans-serif}main{max-width:1440px;margin:auto;padding:20px}h1{font-size:24px;margin:0 0 8px}.status{background:#463525;border-left:4px solid #e9b368;padding:12px 16px}button,select{font:inherit;padding:6px 12px;margin:4px;background:#2b2e36;color:#eee;border:1px solid #666;border-radius:5px}button[aria-current=true]{border-color:#e9b368;color:#ffd29a}img{display:block;width:100%;height:auto;background:#222;margin-top:12px}p{margin:8px 0}.muted{color:#bbb}a{color:#a8ceff}</style>
<main><h1>完整头发 · 原版 Jiggle 三组尝试</h1>
<p class="status">本轮未解决急甩，已停止继续试跑。三组均为完整角色、全部 27 束头发的正常材质画面。静态关键帧不用于证明运动自然。</p>
<label>工程 <select id="cases"></select></label><div id="frames"></div>
<p id="caption"></p><img id="picture" alt="完整角色正常材质关键帧">
<p id="metrics" class="muted"></p><p><a id="blend">对应 .blend 工程</a> · <a href="attempt_result.json">完整验证记录</a></p>
<p class="muted">已烘焙源帧 1–450（30fps）。穿入深度只检查 101 帧，其中 10–13 秒逐源帧检查；没有宣称整段接触通过。保留原动作和银白发色。</p></main>
<script>const data=PAYLOAD;const select=document.querySelector('#cases');let currentFrame=331;
for(const r of data){const o=document.createElement('option');o.textContent=r.label;o.value=r.case;select.append(o)}select.value='B_smaller_radius';
function show(){const r=data.find(x=>x.case===select.value);if(!r.stills.some(s=>s.frame===currentFrame))currentFrame=331;
const buttons=document.querySelector('#frames');buttons.replaceChildren();for(const s of r.stills){const b=document.createElement('button');b.textContent=s.seconds.toFixed(3)+' 秒';b.setAttribute('aria-current',String(s.frame===currentFrame));b.onclick=()=>{currentFrame=s.frame;show()};buttons.append(b)}
const s=r.stills.find(x=>x.frame===currentFrame);document.querySelector('#picture').src=s.url;document.querySelector('#caption').textContent=r.label+' · 源帧 '+s.frame+' · '+s.seconds.toFixed(3)+' 秒';
document.querySelector('#metrics').textContent='101 帧最大埋入 '+r.maximum_sampled_depth_cm.toFixed(2)+'cm；急甩时骨轴相邻帧摆动 '+r.peak_bone_axis_swing_deg.toFixed(1)+'°。身体动作误差 0。';
document.querySelector('#blend').href=r.case+'/完整角色_JigglePhysics原版_15秒.blend';}select.onchange=show;show();</script></html>""".replace("PAYLOAD", payload)
(ROOT / "完整头发_三组尝试_关键帧.html").write_text(page, encoding="utf-8")
print(json.dumps(dict(status=report["status"], gallery=str(ROOT / "完整头发_三组尝试_关键帧.html"), cases=len(rows), pc2_valid=sum(len(r["pc2"]) for r in rows), all_jobs_finished=True), ensure_ascii=False))
