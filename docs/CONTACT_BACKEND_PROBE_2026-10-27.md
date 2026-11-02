# 统一接触底座的本机实测

## 状态与产物

状态：`LIMITED_BACKEND_OUTPUT_PROBE_PASS_FULL_MMD_SYSTEM_INCOMPLETE`。
后续更新：原始实时姿态错位、随动衣料附着已在限定拓扑修复，并新增两关节头部避让和六关节双手接触对照。当前记录见 [实时与双手接触](CONTACT_LIVE_AND_BIMANUAL_2026-10-27.md)；本文件保留旧输出桥小样的真实历史，旧目录不覆盖，完整 MMD 仍未完成。

已实际运行 Genesis＋libuipc，不再只停留于论文／功能介绍。
通过的是单关节、双层衣料的数值输出小样，完整 MMD 系统尚未完成。

目录：`outputs/contact_stack/joint_axis_sync_v1/`。

- `Backend_JointCloth_Probe.blend`：真正由骨骼驱动的关节，以及两层实际解算衣料缓存。
- `Backend_JointCloth_1080p.mp4`：1920×1080，91 帧，30 fps；0.9 秒仿真放慢播放，无音轨，不是角色试片。
- `comparison_physics_output.json`：同一物理时刻的骨骼输出与衣料的独立表面检查。
- `comparison.json`：原始实时 Genesis 姿态仍失败的对照，不覆盖或藏掉这个结果。
- `blender_playback_qa.json`、`joint_output_bridge.json`、`acceptance.json`：回写、重载和范围记录。

## 环境

独立环境在 `tools/contact_stack/venv/`，不修改 Blender 的 Python 或用户模型。
Genesis World 1.4.5、pyuipc 0.0.29、Quadrants 1.3.3、PyTorch 2.14.1+cpu、NumPy 2.5.4。
采用 CPU 关节求解与 CUDA IPC；RTX 5080／驱动 610.88 的实际 CUDA doctor 检查通过。
完整依赖锁定在 `config/contact_stack.windows.lock.txt`，`pip check` 通过。

[Genesis 官方 IPC 资料](https://genesis-world.readthedocs.io/en/v1.3.0/user_guide/theory/couplers/ipc_coupler.html)
用于定位接口，实际调用以已安装 1.4.5 源码为准。
[libuipc 官方代码及示例](https://github.com/spiriMirror/libuipc)
提供底层关节、衣料、固定点与原生状态访问机制。

## 对照结果

首先运行同一控制目标的无衣料、单向、双向软耦合三组。
双向反馈力矩最大约 1.87 N·m，最大关节差约 0.04524 rad（2.59°）；
但实际 Genesis 关节表面在 91 个采样中有 38 个与衣料交叉，该候选拒绝。

随后切换直接关节耦合，加入两层各 169 点的衣料及顶部共 26 个固定点。
当前版本组合的原生转轴与 Genesis 目标方向相反，已用只作用于本次建场景的
版本限定适配器修正；第三方安装文件未修改。该适配仅支持此处验证过的固定基座、
转动关节，不能直接扩展成任意关节转换。

修正轴向及启用参考同步后，原始实时骨架仍有状态时刻偏差：
最大表面偏离约 13.5 mm，20 个采样存在身体／衣料交叉，衣料顶点深入约 0.085 mm。
该实时结果仍不通过。场景实例的 `transform` 属性也不能直接当实时 ABD 状态；
本次最终导出使用耦合器的 `AffineBodyStateAccessorFeature`。

独立输出桥接从与衣料同一时刻的原生状态重建单关节旋转：

- 原始 Genesis 姿态与数据保留；新输出不是直接挪皮肤顶点，也没有删除身体。
- 固定枢轴和骨长不变，仅改变骨骼旋转。重建骨骼角点与原生物理体的最大误差约 4.10 微米。
- 相同目标下，有衣料与无衣料的输出关节最大差约 0.07295 rad（4.18°）。
- 91 个采样的重建骨骼表面／衣料、衣料自碰、两层互碰交线均为 0；26 个固定点误差为 0。
- 两层衣片边长比分别为 0.9888–1.0143、0.9944–1.0058，没有以拉成长薄片来避让。
- 回写成 Blender 的实际骨骼＋PC2，保存重开并随机读取 1、45、91 帧，最大坐标差约 9.67e-8 m。

这证明该小样可以输出一致的骨骼运动与衣料，并产生真实衣料反馈。
它没有修复 Genesis 内部实时状态顺序；也不是完整骨架重定向或任意蒙皮表面防穿保证。

## 具体接口缺口

1. Genesis 的 `FEMEntity.set_vertex_constraints` 明确拒绝 IPC。新增
   `scripts/genesis_ipc_constraints.py`，在原生初始化前设置当前／静止几何的固定点属性。
   已测世界固定边；跟随骨骼的动态附着尚未实现。
2. `two_way_coupling=False` 仅能作为软耦合力反馈的关闭对照，不能据此认定
   `external_articulation` 的关节状态反馈也关闭；直接关节模式采用有／无衣料对照。
3. 不能用代理无交线替代实际骨骼表面检查。当前始终同时保留原实时骨架、原生物理体、
   重建骨骼输出三组数据，单独验收。
4. 单关节输出桥不能直接用于 MMD 的球关节、扭转辅助骨或闭环双手接触。
   接触语义和整体动作约束仍须在此底座之上实现。

## 复现入口

在项目根目录使用独立环境，先按官方 CPU 索引安装 `torch==2.14.1+cpu`，
再安装 `config/contact_stack.windows.lock.txt`。不向 Blender 自带 Python 装这些依赖。

```powershell
& tools/contact_stack/venv/Scripts/python.exe -m uipc doctor --probe-cuda
& tools/contact_stack/venv/Scripts/python.exe scripts/run_genesis_contact_matrix.py --steps 90 --layers 2 --pin-top --coupling external_articulation --axis-fix --sync-reference --modes free two_way --margin .002 --output outputs/contact_stack/new_probe
& tools/contact_stack/venv/Scripts/python.exe scripts/export_genesis_joint_pose.py --input outputs/contact_stack/new_probe
```

然后用 Blender 后台执行 `audit_genesis_ipc.py -- --input <目录>` 保留原姿态检查，
再加 `--physics-joint-output` 检查输出姿态。`preview_contact_backend.py` 只接受输出表面
已通过的目录，创建真实骨骼并验证重载；`--render-all` 渲染全部帧，
`encode_contact_backend.py` 编码并完整解码复查。
后台 Blender 必须使用 `--python-exit-code 1`，外层不得用随后成功的日志读取覆盖失败退出码。

## 完整系统仍需完成

完整角色的全身关节／蒙皮对应、主体与肢体优先级、双肢及有意接触约束、
跟随身体的衣料附着、初始穿插整理、整段动作优化、高精衣服传递和多角度验收。
旧抱拳候选仍被否决；本轮没有生成新的合格抱拳或角色 15 秒成片。
