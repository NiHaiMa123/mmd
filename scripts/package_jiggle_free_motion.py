"""Summarize collision-free inertia/gravity evidence and make a normal-frame viewer."""
import json
import struct
from pathlib import Path
import numpy as np

ROOT = Path(r'E:\project\mmd\work\headswap_xl_codex\jiggle_free_motion_20261102')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


on, off = np.load(ROOT / 'motion.npz'), np.load(ROOT / 'gravity_off/motion.npz')
assert np.array_equal(on['head_world'], off['head_world'])
assert np.array_equal(on['rigid_tip_world'], off['rigid_tip_world'])
configs = [read(ROOT / 'configuration.json'), read(ROOT / 'gravity_off/configuration.json')]
for a, b in zip(configs[0]['settings'], configs[1]['settings']):
    assert {k:v for k,v in a.items() if k != 'gravity'} == {k:v for k,v in b.items() if k != 'gravity'}
    assert a['gravity'] == .25 and b['gravity'] == 0
for folder in [ROOT, ROOT / 'gravity_off']:
    report = read(folder / 'bake_report.json')
    assert report['no_collision_confirmed_in_every_observed_step'] and not report['strain_flags']
    assert report['body_control_error'] == 0 and report['head_control_error'] == 0
    for path in (folder / 'cache').glob('*.pc2'):
        with path.open('rb') as stream:
            magic, version, count, first, step, samples = struct.unpack('<12siiffi',stream.read(32))
        assert magic == b'POINTCACHE2\x00' and version == 1
        assert path.stat().st_size == 32+12*count*samples
actual = on['physical_tip_world']
rear = list(range(7,23))+[25,26]
hold_curve = np.median(np.linalg.norm(actual[15:31,rear]-actual[15:16,rear],axis=2),axis=1)*100
peak = int(np.argmax(hold_curve))
gravity = actual-off['physical_tip_world']
analysis = dict(status='NO_COLLISION_INERTIA_GRAVITY_BASELINE_REVIEW_READY',
    whole_head_chains=27, dynamic_bones=90, source_frames=[1,91], source_fps=30,
    unchanged_production_files=True, collision_acceptance_not_evaluated=True,
    first_stop_time_s=.5, after_first_stop_peak_motion_cm=float(hold_curve[peak]),
    first_stop_to_peak_s=peak/30,
    after_return_difference_from_late_equilibrium_cm={str((f-1)/30):float(np.median(np.linalg.norm(actual[f-1,rear]-actual[90,rear],axis=1))*100) for f in [46,49,52,61,76,91]},
    gravity_on_minus_off_at_tilted_hold=dict(time_s=1, rear_median_3d_offset_cm=float(np.median(np.linalg.norm(gravity[30,rear],axis=1))*100),rear_median_vertical_offset_cm=float(np.median(gravity[30,rear,2])*100)),
    gravity_on_minus_off_at_rest=dict(time_s=3,rear_median_3d_offset_cm=float(np.median(np.linalg.norm(gravity[90,rear],axis=1))*100),rear_median_vertical_offset_cm=float(np.median(gravity[90,rear,2])*100)),
    statistics_scope='18 rear/long-side chains; all27 chains remain present and visible. Displacement statistics do not constitute naturalness acceptance.',
    interpretation='Motion persists after the controlled head stops, and gravity-on minus gravity-off deforms tips downward. Return motion damps quickly. No judgement based on penetration; this is not the original dance or a collision-enabled production pass.')
render = read(ROOT / 'continuous_review/render_report.json')
assert len(render['frames']) == 72 and render['new_simulation'] is False
images = []
for i in range(1,73):
    path = ROOT / f'continuous_review/frames/f{i:04d}.png'
    with path.open('rb') as stream:
        header = stream.read(24)
    assert header[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',header[16:24]) == (1920,1080)
    images.append(path.relative_to(ROOT).as_posix())
(ROOT / 'free_motion_analysis.json').write_text(json.dumps(analysis,ensure_ascii=False,indent=2),encoding='utf-8')
payload = json.dumps(images,ensure_ascii=False)
page = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>完整头发 · 无碰撞惯性与重力</title><style>body{margin:0;background:#17191e;color:#eee;font:16px/1.6 system-ui,sans-serif}main{max-width:1440px;margin:auto;padding:20px}h1{font-size:24px;margin:0}p{margin:8px 0}.notice{padding:10px 14px;background:#293746;border-left:4px solid #9dc7e5}button,select{font:inherit;color:white;background:#30343c;border:1px solid #777;border-radius:5px;padding:6px 12px;margin:4px}img{width:100%;height:auto;display:block;background:#222}#viewport{overflow:hidden}#viewport.zoom{max-width:900px;aspect-ratio:1/1;margin:auto}#viewport.zoom img{width:300%;max-width:none;transform:translate(-33.333%,-7%)}input{width:min(700px,95%)}a{color:#add5ff}.muted{color:#bbb}</style>
<main><h1>完整头发 · 只看惯性与重力</h1><p class="notice">身体静止，头转过去→停住→回正→停住。全部27束头发，原版Jiggle、30Hz；本测试禁用所有头发碰撞，仅观察运动，不作穿模验收。原舞蹈文件保留。</p>
<button id="play">播放</button><select id="speed"><option value="1">原速</option><option value="0.25">四分之一速</option></select><button id="zoom">放大完整头发</button><input id="slider" type="range" min="0" max="71" value="0"><p id="caption"></p><div id="viewport"><img id="picture" alt="完整角色无碰撞头发惯性短测"></div>
<p><button data-time="0">开始</button><button data-time="0.5">转头后停住</button><button data-time="1">开始回正</button><button data-time="1.5">回正后停住</button><button data-time="2">回正后半秒</button><button data-time="2.9583333">接近结束</button></p>
<p>头停止后，后发继续变化，约0.13秒后变化达到约2cm；回正后约半秒已接近静止。相同动作的零重力对照确认：当前重力会让发梢向下偏移。先看这种滞后、回摆和收敛节奏是否自然。</p>
<p class="muted">25°转头＋15°侧倾，0–0.5秒；0.5–1秒停住；1–1.5秒回正；1.5–3秒停住。原始物理30fps，图集24张/秒，1920×1080、24采样。画面是完整角色正常材质，无左右诊断分屏。不是原舞蹈15秒验收。</p>
<p><a href="free_motion_analysis.json">惯性和重力对照数据</a> · <a href="完整角色_无碰撞惯性重力_3秒.blend">完整工程</a></p></main>
<script>const frames=PAYLOAD;const picture=document.querySelector('#picture'),slider=document.querySelector('#slider'),button=document.querySelector('#play');let playing=false,t0=0,start=0;
function draw(){const i=Number(slider.value),t=i/24;picture.src=frames[i];const phase=t<.5?'转头与侧倾':t<1?'头保持不动':t<1.5?'头回正':'头保持不动，观察余动';document.querySelector('#caption').textContent=t.toFixed(3)+'秒 · '+phase+' · '+(i+1)+'/72'}
function stop(){playing=false;button.textContent='播放'}function tick(t){if(!playing)return;slider.value=(start+Math.floor((t-t0)*24*Number(document.querySelector('#speed').value)/1000))%72;draw();requestAnimationFrame(tick)}
button.onclick=()=>{if(playing){stop();return}playing=true;start=Number(slider.value);t0=performance.now();button.textContent='暂停';requestAnimationFrame(tick)};slider.oninput=()=>{stop();draw()};document.querySelector('#speed').onchange=()=>{start=Number(slider.value);t0=performance.now()};document.querySelector('#zoom').onclick=()=>{const zoom=document.querySelector('#viewport').classList.toggle('zoom');document.querySelector('#zoom').textContent=zoom?'全身画面':'放大完整头发'};for(const b of document.querySelectorAll('[data-time]'))b.onclick=()=>{stop();slider.value=Math.min(71,Math.round(Number(b.dataset.time)*24));draw()};for(const url of frames){const pre=new Image();pre.src=url}draw();</script></html>""".replace('PAYLOAD',payload)
(ROOT / '完整头发_只看惯性与重力.html').write_text(page,encoding='utf-8')
print(json.dumps(analysis,ensure_ascii=False))
