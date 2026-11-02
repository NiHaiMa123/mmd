"""Freeze exact inputs and code for the MMD/Bullet plus display-guard pipeline."""
import argparse,json,shutil,hashlib,importlib.metadata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];P=ROOT.parent/'work/headswap_xl_codex/native_mmd_bridge_20261030/headless_bullet'
p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);a=p.parse_args();out=Path(a.delivery);dest=out/'reproduce';dest.mkdir(parents=True,exist_ok=True)
src=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030';native=P.parent
def copy(source,target):
 source=Path(source);target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
 if not target.exists():shutil.copy2(source,target)
def hashfile(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for b in iter(lambda:stream.read(16*1024*1024),b''):h.update(b)
 return h.hexdigest()
for file in (src/'input_body_aware').iterdir():
 if file.is_file():copy(file,dest/'input'/file.name)
copy(src/'dynamics_contact_islands/positions.npy',dest/'reference/positions.npy')
for name in ['hair_binding.npz','hair_binding.json']:copy(src/'review_11s_20261030'/name,dest/'binding'/name)
copy(native/'input/bone_name_map.json',dest/'binding/bone_name_map.json')
for name in ['character_calibrated.pmx','corrected_body_fk.vmd']:copy(P/'input'/name,dest/'native/input'/name)
for name in ['world_matrices.f32','initial_world.f32','bones.json','joint_pivot_calibration.json','status.json']:copy(P/'legal_start'/name,dest/'native/legal_start'/name)
pub=json.loads((out/'cache_publication.json').read_text('utf8'));guard_run=Path(pub['run'])
for name in ['component_fallback.json','component_labels.npy','guard_rows.json','status.json']:copy(guard_run/name,dest/'verification'/name)
if (guard_run/'temporal_filter.json').exists():
 copy(guard_run/'temporal_filter.json',dest/'verification/temporal_filter.json')
 temporal_metadata=json.loads((guard_run/'temporal_filter.json').read_text('utf8'));(dest/'verification/temporal_projection_episodes.json').write_text(json.dumps(temporal_metadata.get('avoid_projection_episodes',[]),indent=2),'utf8')
for name in ['rest_proxy_calibration.json','hair_proxy_shape_fit.json','proxy_initial_audit.json']:copy(native/'calibrated_proxy_chain'/name,dest/'calibration'/name)
for name in ['evaluate_headless_hair.py','guard_headless_hair.py','publish_headless_hair.py','export_full_hair_dynamics.py','prepare_native_mmd_bridge.py','mcp_calibrate_native_proxy_rest.py','mcp_fit_initial_hair_proxy_shapes.py','mcp_export_headless_input.py','assemble_full_hair_showcase.py','render_full_hair_showcase.py','audit_full_hair_showcase.py','audit_render_hair_raw_surfaces.py','verify_full_hair_source_preservation.py','encode_full_hair_showcase.py']:
 copy(ROOT/'scripts'/name,dest/'exact_15s_scripts'/name)
copy(ROOT/'scripts/smooth_headless_hair_temporal.py',dest/'exact_15s_scripts/smooth_headless_hair_temporal.py')
for name in ['package.json','package-lock.json','bake.mjs']:copy(ROOT/'tools/mmd_headless'/name,dest/'mmd_headless'/name)
copy(ROOT/'tools/mmd_headless/node_modules/babylon-mmd/LICENSE',dest/'mmd_headless/babylon-mmd_LICENSE')
copy(ROOT/'tools/mmd_headless/node_modules/babylon-mmd/esm/Runtime/Optimized/wasm/spr/index_bg.wasm',dest/'mmd_headless/frozen_bullet_spr.wasm')
for package in ['mmd_hair_dynamics']:
 for file in (ROOT/'tools/contact_stack'/package).glob('*.py'):copy(file,dest/'python'/package/file.name)
profile=Path(json.loads((src/'input_body_aware/export_complete.json').read_text('utf8'))['rig_profile']);copy(profile,dest/'input/rig_profile.json')
versions={name:importlib.metadata.version(name) for name in ['numpy','scipy','warp-lang']};(dest/'python_versions.json').write_text(json.dumps(versions,indent=2),'utf8')
replay=(ROOT/'scripts/evaluate_headless_hair.py').read_text('utf8')
replay=replay.replace("p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();run=Path(a.run)","p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--input',required=True);p.add_argument('--binding',required=True);p.add_argument('--name-map',required=True);p.add_argument('--preroll',type=int,default=30);a=p.parse_args();run=Path(a.run)")
replay=replay.replace("src=P/'fullhair_repro_20261030/input_body_aware'","src=Path(a.input);manifest=json.loads((src/'export_complete.json').read_text('utf8'));samples=manifest['samples'];assert manifest['sample_step']==.125")
replay=replay.replace("shape=(3833,n,4,4)","shape=((run/'world_matrices.f32').stat().st_size//(n*16*4),n,4,4)")
replay=replay.replace("P/'fullhair_repro_20261030/review_11s_20261030/hair_binding.npz'","Path(a.binding)").replace("P/'native_mmd_bridge_20261030/input/bone_name_map.json'","Path(a.name_map)")
replay=replay.replace('shape=(3593,len(x0),3)','shape=(samples,len(x0),3)').replace('range(3593)','range(samples)').replace('m[k+240]','m[k+a.preroll*8]').replace('samples=3593','samples=samples')
(dest/'replay_bones.py').write_text(replay,'utf8')
guard=(ROOT/'scripts/guard_headless_hair.py').read_text('utf8')
guard=guard.replace("ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))","ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'python'))")
guard=guard.replace("p=argparse.ArgumentParser();p.add_argument('--raw',required=True)","p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--raw',required=True)")
guard=guard.replace("src=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input_body_aware'","src=Path(a.input)")
guard=guard.replace('np.arange(1,450.01,.125)',"np.arange(json.loads((src/'export_complete.json').read_text('utf8'))['frames'][0],json.loads((src/'export_complete.json').read_text('utf8'))['frames'][1]+.0125,.125)")
(dest/'guard.py').write_text(guard,'utf8')
temporal=(ROOT/'scripts/smooth_headless_hair_temporal.py').read_text('utf8').replace("ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))","ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'python'))")
(dest/'temporal.py').write_text(temporal,'utf8')
for filename in ['replay_bones.py','guard.py','temporal.py']:compile((dest/filename).read_text('utf8'),filename,'exec')
readme='''# 复刻说明

本次头发运动来自 babylon-mmd 1.3.0 的单线程 Bullet WASM（240Hz，MMD 2.75 约束兼容），不是逐帧手调骨骼。一次性校准将发骨/代理绑定到合法发型，并重建导出后位置异常的关节枢轴。原质量、弹簧、限制轴和碰撞组保留。

当前宽发片仅用 PMX 代理仍会穿真实皮肤，因此复用已通过的避让参考，再以统一 25% 混合强度加入物理次级运动，最后做整头有限宽度几何约束。该后处理保留原8994真根、原边长±10%、实际身体表面；没有手填某秒的修正姿势。保留的参考也由算法生成。该流程不是“未经后处理的原生MMD物理”，也未证明发片自碰和连续CCD。

## 在新目录重算同一片段

1. 在 `mmd_headless` 运行 `npm ci --ignore-scripts`，然后 `node node_modules/esbuild/bin/esbuild bake.mjs --bundle --platform=node --format=esm --outfile=bake.bundle.mjs`。
2. 执行 `node mmd_headless/bake.bundle.mjs native 479 new_bake repair-pivots --legal-start`。保留输入/已有结果，使用新输出目录。
3. 使用配有 python_versions.json 所列版本的 Python，运行 `replay_bones.py --run native/new_bake --input input --binding binding/hair_binding.npz --name-map binding/bone_name_map.json --preroll 30`。
4. 运行 `guard.py --input input --raw native/new_bake --out new_guard --global-strain --safe-reference reference --physics-gain .25 --component-fallback`。输出3593个实际网格样本及每样本报告。少量不能收敛的自由连通发片自动对整段使用有效参考，避免按帧切换造成跳变；范围见 verification/component_fallback.json。所有子帧通过后再发布，失败不能补空尾帧。
5. 运行 `temporal.py --input input --run new_guard --out new_temporal --avoid-failures verification/temporal_projection_episodes.json`，按30fps超过3m/s自动定位旧接触参考的跳位发片，4Hz零相位滤波与12帧余弦包络后重新进行身体接触/边长约束；自动投影失败时刻附近平滑减弱过滤。具体作用范围和仍需原轨迹的发片见 verification/temporal_filter.json。换动作先不传 --avoid-failures，记录新投影结果后自动生成该动作自己的配置，勿直接套用15秒配置。
6. 通过本工程的头发缓存绑定层换入最后的 positions.npy/PC2；身体、腕部、保护段及原动作不改。exact_15s_scripts 保存本次工作区实际使用的导出、装配、渲染和验收源码；它们的默认路径属于本项目，搬目录须显式改命令路径。

## 三分钟迁移边界

核心后端和参数化回放/几何脚本按输入样本数运行，支持相同模型延长片长。先为完整时长重新计算身体避让及腕部蒙皮缓存，再导出整段准确身体轨迹、FK VMD和对应避让参考，传入新 input/reference，`bake.mjs` 的末帧改为 FK VMD 末帧（含30静态前缀）。不要延长、循环或冻结本次450帧的头发/腕部缓存来充当三分钟模拟。export_full_hair_dynamics.py 和 prepare_native_mmd_bridge.py 有 --last 参数；新动作的有意接触窗口及自动投影失败配置需重新生成，当前只验证15秒，并未验证整首。

新角色需重新映射骨骼、表面类别、发根和一次性代理/枢轴校准，不能照搬本角色的NPZ或代理尺寸。geometry guard 的 .95 暖启动衰减和自动丢弃无效暖启动是几何投影策略，未重置物理骨骼状态。WASM速度状态未导出，完整重算由固定步长和固定输入实现；有效的交付缓存是整头PC2和腕部缓存。
'''
(dest/'README_CN.md').write_text(readme,'utf8')
files={str(f.relative_to(dest)):dict(bytes=f.stat().st_size,sha256=hashfile(f)) for f in dest.rglob('*') if f.is_file() and f.name!='manifest.json'}
(dest/'manifest.json').write_text(json.dumps(dict(status='EXACT_INPUTS_AND_CODE_FROZEN',files=files,python=versions),ensure_ascii=False,indent=2),'utf8');print('REPRO_BUNDLE_FROZEN',len(files),sum(x['bytes'] for x in files.values()),flush=True)
