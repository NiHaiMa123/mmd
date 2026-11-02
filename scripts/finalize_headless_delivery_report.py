"""Write a delivery summary only after the actual finished artifacts pass."""
import argparse,json,struct,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);a=p.parse_args();out=Path(a.delivery)
def read(name):return json.loads((out/name).read_text('utf8'))
pub=read('cache_publication.json');video=read('video_report.json');native=read('native_geometry_audit.json');preserve=read('source_preservation.json');motion=read('motion_report.json');blend=read('blend_delivery_report.json');fallback=json.loads((Path(pub['run'])/'component_fallback.json').read_text('utf8'));repro=read('reproduce/manifest.json')
assert pub['status']=='COMPLETE_PHYSICAL_TRAJECTORY' and video['decoded_video_frames']==450 and video['width']==1920 and video['height']==1080 and video['fps']==30 and video['video_seconds']==15
assert native['samples']==3593 and all(r['crossings']==r['inside_samples']==0 for r in native['rows']);assert all(preserve['unchanged'].values()) and all(preserve['source_actions_unchanged'].values());assert not (out/'full_decode.log').read_text('utf8').strip();assert Path(video['video']).is_file()
with (out/'cache/full_head.pc2').open('rb') as stream:header=struct.unpack('<12siiffi',stream.read(32))
assert header[2:]==(24207,0.,.125,3593)
report=dict(status='COMPLETE_NEW_NORMAL_MMD15_VIDEO_BLEND_CACHES_AND_REPRO_VERIFIED',video=video['video'],blend=blend['blend'],head_cache=str(out/'cache/full_head.pc2'),fingerprint=pub['fingerprint'],frames=450,seconds=15,resolution=[1920,1080],fps=30,head_vertices=24207,hair_triangles=40181,real_skin_triangles=50428,native_geometry_samples=3593,geometry_sample_step=.125,physical_backend='babylon-mmd 1.3.0 Bullet WASM SPR',physical_step_hz=240,physical_blend_gain=.25,reference_fallback=fallback,motion_summary={k:v for k,v in motion.items() if k not in ['frame_rows','worst_speed_samples']},protected_body_frames=[256,321],protected_body_unchanged=True,original_data_preserved=True,clothing_workflow_resumed=False,shutdown_configured=False,render_card_self_collision_proven=False,continuous_ccd_proven=False,repro_files=len(repro['files']))
(out/'delivery_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
text=f'''# 完整角色 15 秒交付

视频：{Path(video['video']).name}。1920×1080、30fps、450帧、15秒，指定Shikako音乐，H.264/AAC，完整音视频解码通过。

工程：完整角色_整头连续物理_15秒.blend。完整脸、眼睛、头饰、全部头发、现有素体、原地库、固定全身镜头及柔光材质。cache/ 中为有效整头与腕部缓存，保留相对路径，搬动时复制整个交付文件夹。

## 头发方法及验收范围

采用 babylon-mmd 1.3.0 的成熟 MMD 兼容 Bullet WASM，240Hz；一次性发骨/代理和枢轴校准，不手调某秒的骨骼。先合法初态，再加入统一25%强度的物理次级运动，与已有有效避让参考结合，最后做有限宽度发片几何约束。自动定位参考中跳位的发片，按4Hz时间滤波及平滑包络处理后，重新做接触约束；范围和保留情况见 reproduce/verification/temporal_filter.json。

{fallback['disabled_free_vertices']} / {fallback['all_free_vertices']} 个自由顶点所属的少量连通发片，在整段一致使用参考轨迹；其余 {fallback['retained_physical_free_vertices']} 个自由顶点保留物理次级运动。该自动选择对整段统一生效，避免按帧开关。原8994真发根、原权重和身体动作不改。具体范围和原因见 reproduce/verification/component_fallback.json。

最终Blender实际网格逐1/8帧复查3593样本：40181头发三角面与50428真实皮肤面无交线，包含点与边长/发根/缓存重放检查通过。另有关键时刻全部顶点、边中点和面心的包含检查以及不经碰撞体简化的原SurfaceClass交线复查。这是采样验收，不是连续CCD或全头发片自碰的证明。

身体原Action、231形态键、网格、权重及保护抱手段256–321保持；原身体髋部/腕部和有意接触残余仍保留，不计为本次已修复。服装流程暂停，旧工程和原始数据保留，没有设置关机。

## 复刻

reproduce/README_CN.md 提供固定依赖、WASM校验、PMX/FK输入、完整身体轨迹、有效参考、参数、校准日志、实际源码和参数化运行步骤。后端与回放/几何脚本可按输入长度运行；三分钟须重新导出对应完整输入并全段验收，目前只验证这15秒，不能循环或延长15秒缓存充当长片。

本次指纹：{pub['fingerprint']}。
'''
(out/'README_CN.md').write_text(text,'utf8');print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
