"""Package completed diagnostic evidence and local normal image-sequence viewer."""
import json
import struct
from pathlib import Path

ROOT = Path(r'E:\project\mmd\work\headswap_xl_codex\jiggle_timing_trace_20261102')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


rows = []
for fps in [30, 120]:
    directory = ROOT / f'{fps}Hz'
    render = read(directory / 'continuous_review/render_report.json')
    assert len(render['frames']) == 36 and render['new_simulation'] is False
    sequence = []
    for item in render['frames']:
        image_path = directory / f"continuous_review/frames/f{item['output_frame']:04d}.png"
        with image_path.open('rb') as stream:
            header = stream.read(24)
        assert header[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', header[16:24]) == (1920, 1080), image_path
        sequence.append(image_path.relative_to(ROOT).as_posix())
    depth = read(directory / 'depth_keyframes/intrusion_measurement.json')
    values = [(max(r['maximum_vertex_inward_depth_cm'], r['maximum_face_centroid_inward_depth_cm']), r['frame']) for r in depth['frames']]
    caches = []
    for path in sorted((directory / 'cache').glob('*.pc2')):
        with path.open('rb') as stream:
            magic, version, points, start, step, samples = struct.unpack('<12siiffi', stream.read(32))
        assert magic == b'POINTCACHE2\x00' and version == 1
        assert path.stat().st_size == 32 + 12 * points * samples
        caches.append(dict(path=str(path), points=points, samples=samples))
    trace = read(directory / 'pipeline_analysis.json')
    mesh = read(directory / 'mesh_review.json')
    rows.append(dict(fps=fps, trace=trace, mesh=mesh,
                     maximum_sampled_depth_cm=max(values)[0], maximum_depth_frame=max(values)[1],
                     depth_frames=[r['frame'] for r in depth['frames']], frames_over_5cm=sum(v > 5 for v, _ in values),
                     caches=caches, sequence=sequence, render=render,
                     keyframes=[dict(frame=int(p.stem[1:]), url=p.relative_to(ROOT).as_posix()) for p in sorted((directory / 'keyframes').glob('f*.png'))]))
report = dict(status='MATCHED_DIAGNOSTIC_COMPLETE_SHARP_RAW_MOTION_REMAINS', cases=rows,
              conclusion='Sharp axis motion is already present in raw solver points; evaluated baked bones reproduce those points. Lower FPS changes motion but does not eliminate local sharp swings.',
              uncertain='Exact source within integration, collision projection and length/angular constraints has not yet been isolated. No claim of numerical explosion from axis angle alone.',
              current_scope='Full head source frames1..391; source30fps. Motion diagnostics10..13s. Depth only12 selected source frames. Continuous normal images11.25..12.75s,36 at24fps per case.',
              no_additional_dynamics_after_two_trials=True, no_shutdown=True)
(ROOT / 'review_result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
payload = json.dumps(rows, ensure_ascii=False).replace('</', '<\\/')
page = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>完整头发 · 时间流程核验</title><style>body{background:#16171c;color:#eee;margin:0;font:16px/1.5 system-ui,sans-serif}main{max-width:1440px;margin:auto;padding:18px}h1{font-size:24px;margin:0 0 8px}button,select{font:inherit;background:#30343f;color:white;border:1px solid #777;border-radius:5px;padding:6px 12px;margin:4px}input{width:min(650px,90%)}img{width:100%;height:auto;display:block;background:#222}.notice{border-left:4px solid #dcb27b;background:#3d3327;padding:10px 14px}.muted{color:#bbb}a{color:#acd2ff}#keys button{font-size:14px}</style>
<main><h1>完整头发 · 30Hz / 120Hz 时间流程核验</h1>
<p class="notice">仅改变解算步频，保留同一角色、14个椭球、发根与参数。两组仍有局部急摆，尚未验收为自然物理。原始求解点与烘焙发骨吻合，具体是哪项求解/碰撞约束触发急摆尚未定位。</p>
<select id="case"><option value="30">30Hz</option><option value="120">120Hz</option></select>
<button id="play">播放连续图片</button><select id="speed"><option value="1">原速</option><option value="0.25">四分之一速</option></select>
<input id="slider" type="range" min="0" max="35" value="0"><p id="caption"></p><img id="image" alt="完整角色正常材质连续图片">
<p id="metrics" class="muted"></p><p>另看整数关键帧：</p><div id="keys"></div>
<p class="muted">连续图片：11.25–12.75秒，24张/秒，1920×1080，24采样；没有重新模拟或另做平滑。静态帧或短片不能代表完整15秒验收。穿入深度仅核对12个关键源帧，按最深埋入5cm标准报告。</p>
<p><a href="review_result.json">完整证据记录</a> · <a id="blend">当前组工程</a></p></main>
<script>const data=PAYLOAD;const sel=document.querySelector('#case'),img=document.querySelector('#image'),slider=document.querySelector('#slider'),play=document.querySelector('#play');let playing=false,t0=0,startIndex=0;
function current(){return data.find(r=>String(r.fps)===sel.value)}function caption(i){document.querySelector('#caption').textContent=sel.value+'Hz · 原曲 '+(11.25+i/24).toFixed(3)+' 秒 · 连续图片 '+(i+1)+'/36'}
function draw(){const r=current(),i=Number(slider.value);img.src=r.sequence[i];caption(i);document.querySelector('#metrics').textContent='10–13秒最大显示发梢单帧位移 '+r.mesh.largest_tip_step_cm.toFixed(2)+'cm；后发活动量 '+r.mesh.rear_tip_rms_cm_median.toFixed(2)+'cm；12个关键帧最大埋入 '+r.maximum_sampled_depth_cm.toFixed(2)+'cm。';document.querySelector('#blend').href=r.fps+'Hz/完整角色_Jiggle时间核验_'+r.fps+'Hz_13秒.blend';}
function stop(){playing=false;play.textContent='播放连续图片'}function tick(t){if(!playing)return;const speed=Number(document.querySelector('#speed').value);const i=(startIndex+Math.floor((t-t0)*24*speed/1000))%36;slider.value=i;draw();requestAnimationFrame(tick)}
play.onclick=()=>{if(playing){stop();return}playing=true;startIndex=Number(slider.value);t0=performance.now();play.textContent='暂停';requestAnimationFrame(tick)};slider.oninput=()=>{stop();draw()};document.querySelector('#speed').onchange=()=>{startIndex=Number(slider.value);t0=performance.now()};
function change(){stop();const box=document.querySelector('#keys');box.replaceChildren();for(const k of current().keyframes){const b=document.createElement('button');b.textContent=((k.frame-1)/30).toFixed(3)+'秒 / 源帧'+k.frame;b.onclick=()=>{stop();img.src=k.url;document.querySelector('#caption').textContent=sel.value+'Hz · 整数源帧 '+k.frame+' · '+((k.frame-1)/30).toFixed(3)+' 秒'};box.append(b)}draw()}sel.onchange=change;change();for(const r of data)for(const url of r.sequence){const pre=new Image();pre.src=url}</script></html>""".replace('PAYLOAD', payload)
(ROOT / '完整头发_时间流程核验图集.html').write_text(page, encoding='utf-8')
print(json.dumps(dict(status=report['status'], images_verified=72, valid_caches=sum(len(r['caches']) for r in rows), gallery=str(ROOT / '完整头发_时间流程核验图集.html')), ensure_ascii=False))
