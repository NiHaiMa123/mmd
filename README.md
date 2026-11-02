# MMD 成品模型拆衣与固定素体自动换装

> **当前交接（2026-11-02）：** 服装流程暂停，当前优先完整角色的头发惯性与防穿模。Astra新窗口先读[最新交接](docs/HANDOFF_ASTRA_HAIR_CONTACT_2026-11-02.md)。用户认可的无碰撞7.5–15秒视频已完成；防穿模候选尚未通过5cm深度门槛，PR47另复现浅穿越漏检。历史模块和试验保留，不代表当前任务已验收。大模型、工程、媒体、缓存、依赖和生成安装包保留本机，Git备份文档与轻量源码。

> **后续执行：** [头发接触深度调研与 Codex 修复计划](docs/HAIR_CONTACT_REPAIR_PLAN_2026-11-02.md)。先定位首次入体，再做有边界的接触补丁；保留认可惯性和 5cm 验收口径。文档包含 NovaBone 1.3.0 与 Blender 5.2 XPBD 的备选路线，尚无新增通过候选。

从来源角色的 PMX 里自动拆出衣服，适配到固定的素体骨架上，导出可以直接丢进 MMD 使用的 PMX。

进度与已知问题见 [`progress.md`](progress.md)，需求与实施顺序见 [`plan.md`](plan.md)。

## 动画接触工具（独立实验插件，2026-10-28）

最新插件 `dist/animation_contact_tools-0.1.5.zip`：[实际发片接触修正](docs/FINITE_WIDTH_HAIR_2026-10-29.md)把原生动力学与原皮肤代理、PBD 保形／接触／时间连续性约束接起来。这一束完整 15 秒的 3,593 个八分之一帧采样无交线和超限拉伸，本轮未新增改人物动作。仅该束对身体通过离散验收，其他头发、自碰、CCD 和完整身体仍未解决。前阶段[碰撞壳误焊修复](docs/HAIR_FULL_RUN_2026-10-29.md)及其失败候选保留作对照。

独立插件与 `skills/repair-animation-contact/` 支持显式骨架／表面映射、真实蒙皮检测、原 Action 保留的普通上肢修正层，以及子帧复查。独立英文骨架、厘米单位、技能打包后台运行已实测。当前真实 MMD 仍有进入抱手保护段的过渡残留、髋部穿插和头发问题，**不是完整无穿模系统**。[前阶段头发测试](docs/HAIR_CONTACT_TESTS_2026-10-28.md)修复了物理世界成员缺失与过滤错误；旧空世界物理对照作废。最新原生曲线与单束结果见上方记录。安装入口、算法、实测与限制见 [可迁移接触记录](docs/TRANSFERABLE_CONTACT_2026-10-28.md) 和 [技能](skills/repair-animation-contact/SKILL.md)。

## Blender 插件（0.9 实验版）

v0.2 的 `anatomical_foot_last` 明显破坏原鞋型，现已拒绝执行旧配置。0.3 改为原鞋等比变换、鞋口限定的脚面遮蔽及目标踝骨单骨绑定，Blend 保留脚部副本。这适用于本机刻晴的闭口硬底鞋，不支持凉鞋、脚趾弯折或自动裸足切换；[调查与实测](docs/SHOE_FITTING_RESEARCH_2026-10-23.md) 记录依据和限制。

**MMD Outfit Bridge**：Blender 侧栏、Python API 与 JSON/CLI 共用独立后台服务，支持绑定输入的可复用配置、目标旧衣物排除、胸衣连续变形、目标表面手套/袜层重建、闭口鞋保形适配、PMX 重导入检查与 VMD 检查。

0.9 增加默认关闭的试验袖口物理：识别两侧完整袖片，为原先只随手臂运动的袖口增加粒子骨、刚体、关节和权重过渡。继承 0.8 的袖片方向修正、闭口硬鞋形态键锁定、平地接地动作和手套覆盖。安装、使用与限制见 [`addon/README.md`](addon/README.md)。用 `python scripts/build_outfit_addon.py` 生成 `dist/mmd_outfit_bridge-0.9.0.zip`。需要已安装 MMD Tools；不包含第三方模型。

本版仍需视觉验收，`REVIEW_REQUIRED` 不等于无穿模。它复用已有适配流程，并开始将对模型的现场操作要求转成可复用配置。

供其他 AI 模型执行的固定流程见 [`docs/OUTFIT_AGENT_WORKFLOW.md`](docs/OUTFIT_AGENT_WORKFLOW.md)。袖口物理见 [`docs/OUTFIT_V09_2026-10-24.md`](docs/OUTFIT_V09_2026-10-24.md)，[B 站研究记录](docs/SLEEVE_RIBBON_BILIBILI_2026-10-24.md) 说明依据。袖片静止适配见 0.8、鞋型与接地见 0.7、手套覆盖及备份见 0.6。历史记录保留作对照。

## 环境要求

| 组件 | 要求 | 本机实测 |
|---|---|---|
| Blender | 4.2+ （含 MMD Tools 扩展接口） | 5.2.1 LTS，`D:\software\blender\5.2.1\blender.exe` |
| MMD Tools | 扩展形式 `bl_ext.blender_org.mmd_tools`（或旧版 addon `mmd_tools`） | 已装 |
| 外层 Python | 3.10+ | 3.14（系统自带即可，**不需要 pip 装任何东西**） |

程序会在 Blender 里用 `--factory-startup` 起后台进程，并在运行时自行 `addon_enable` MMD Tools，
所以不需要改 Blender 首选项，也不需要开 GUI。

## 安装

```powershell
# 1) 确认 Blender 与扩展
& 'D:\software\blender\5.2.1\blender.exe' -b --factory-startup --python-expr "import bpy; bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.mmd_tools'); print('mmd_tools ok')"

# 2) 放素材（见 assets/README.md）
#    assets/source.pmx  + 同目录贴图
#    assets/base.pmx    + 同目录贴图
```

## 运行

所有命令都在仓库根目录执行。Blender 路径按 `--blender` → 环境变量 `BLENDER_EXE` → PATH → 内置候选顺序自动查找。

```powershell
# 看清楚来源模型和素体各是什么（对象 / 材质 / 面数 / 骨骼 / 贴图）
python -m src.cli inspect --source assets/source.pmx --target assets/base.pmx

# 拆衣预览：列出候选服装部件，生成 4 视角预览图
python -m src.cli extract-preview --source assets/source.pmx --out outputs/preview

# 只把选中的部件抽成独立服装网格（可单独检查 UV / 权重 / Morph）
python -m src.cli extract --source assets/source.pmx --out outputs/extract01 `
    --selection outputs/preview/selection.json

# 正式换装：拆衣 → 骨架映射 → 体型适配 → 重新绑权 → 隐藏身体 → 导出
python -m src.cli dress --source assets/source.pmx --target assets/base.pmx --out outputs/dress01

# 静态 / 动作检查
python -m src.cli qa --model outputs/dress01/model.pmx --motions assets/motions/ --out outputs/dress01

# 带 MMD 物理的穿模检测：在 Blender 里跑 Bullet，把仿真结果写回骨骼后再测
python -m src.cli qa --model outputs/dress01/model.pmx --motions assets/motions/x.vmd --physics --out outputs/dress01/qa_phys

# 同一模型的「碰撞组翻译前」对照：只拆掉服装↔身体这一层碰撞关系，其余不变
python -m src.cli qa --model outputs/dress01/model.pmx --motions assets/motions/x.vmd --physics --break-collision --out outputs/dress01/qa_phys_broken

# 各部位的特写（手/脚/头/腰/裙…），用来核对"装上去之后长什么样"
python -m src.cli closeup --model outputs/dress01/model.pmx --out outputs/closeup --regions foot_l,hand_l,waist --views front,left,q_left,top

# 高风险姿势测试集（8 类），输出每个姿势的穿模数与截图
python -m src.cli motion-check --model outputs/dress01/model.pmx --out outputs/dress01/poses

# 自动修复：找出最差姿势 → 扩大身体 Mask → 重测对比 → 输出 model_repaired.pmx
python -m src.cli motion-check --model outputs/dress01/model.pmx --out outputs/dress01/repair --repair

# 同上，但用真实 VMD 的最差帧来定位问题（裙子甩动这类只有真实动作才暴露）
python -m src.cli motion-check --model outputs/dress01/model.pmx --motions assets/motions/x.vmd --out outputs/dress01/repair_motion --repair
```

跑完可以把检测和修复的产物汇总成一份验收报告：

```powershell
python scripts/p2_acceptance.py outputs/dress01
```

`dress` 加 `--stages` 会在每个阶段（抽出 / 重蒙皮 / 贴合 / 遮蔽）各渲染一组 4 视角图，
用来定位是哪一步把衣服弄坏了：

```powershell
python -m src.cli dress --source ... --target ... --out outputs/dress01 --stages
```

用系统的 `python` 即可；如果不想切目录，可以：

```powershell
$env:PYTHONPATH = 'E:\project\mmd\mmd_repo'
python -m src.cli inspect --source ...
```

### 指定 Blender

```powershell
python -m src.cli inspect --blender "D:\software\blender\5.2.1\blender.exe" --source ...
# 或
$env:BLENDER_EXE = 'D:\software\blender\5.2.1\blender.exe'
```

## 输入素材约定

```
assets/
  source.pmx      来源角色（要拆走的衣服在这里）
  base.pmx        固定素体（最终穿着衣服的身体）
  motions/*.vmd   动作测试集
```

PMX 里的贴图引用是相对 PMX 所在目录的，**贴图必须和 PMX 放在一起并保持原来的相对结构**，
否则导入后贴图会丢。详见 [`assets/README.md`](assets/README.md)。

## 输出

`dress` 一次运行会在输出目录里留下：

| 文件 | 内容 |
|---|---|
| `manifest.json` | 输入模型路径与哈希、解析信息、服装部件选择、材质/纹理、状态 |
| `rig_map.json` | 来源骨骼 → 目标骨骼映射、未匹配的服装辅助骨 |
| `fit_params.json` | 比例、骨架位姿差异、分区变形参数 |
| `report.json` | 每项 OK / WARNING / FAILED / SKIPPED |
| `model.pmx` + `tex/ sph/ toon/` | 最终产物，可直接用 MMD 打开 |
| `work.blend` | 可人工继续修的中间工程 |
| `preview/` | 关键视角预览与错误标记图 |
| `extracted/` | 独立服装网格 + 依赖清单（骨骼/刚体/Joint/Morph） |

`qa` 会在同一目录写 `qa_report.json`（静态权重检查 + 动作穿模帧号），
`motion-check` 会在 `poses/` 下写 8 个高风险姿势的截图和 `motion_report.json`。

## 算法要点

**骨骼重定向**。两套 MMD 骨架的通用骨骼同名，但腰高、颈部 Y 向、肩宽、臂角都不一样
（实测刻晴 vs 达妮娅：腰高差 6.8 cm、颈部 Y 差 4.3 cm、臂角差 4.7°）。
所以不做全局缩放，而是给每根匹配上的骨算一个静置矩阵差

```
D(bone) = M_target(bone) · M_source(bone)⁻¹
```

再用权重做线性混合蒙皮把衣服搬过去：

```
p' = Σ w_i · D(bone_i) · p
```

逐骨的差异因此被自动吸收，接缝处因为是加权混合所以不会裂开。
衣服专用的骨链（スカート/袖/带/流苏/配饰，刻晴身上 113 根）按父骨的 D 变换
重建进目标骨架，衣服不会因为没有裙子骨而散架。

**分区适配**。用「主导骨骼」把顶点分成贴身区（身体骨主导）和宽松区（服装骨主导）：
贴身区拉到目标身体表面 + 5 mm，宽松区保持来源轮廓（裙摆、喇叭袖不会被压到腿上）。

**身体遮蔽**。先在来源模型上按顶点测「是否被衣服盖住」（衣服近且在身体外侧），
再用 KD 树把这份覆盖率映射到目标身体；**同时**在目标上直接再测一次。
两次都要：刻晴的手套、鞋、过膝袜是「漆皮层」——她身体表面本身刷了服装材质，
来源模型在这些部位**没有独立的皮肤面**，只靠来源覆盖率会算成 0，目标裸脚就一直露在靴子里。
直接法补上这一块（`cover_dist` 12 mm + 领口/袖口 3 cm 的开口余量）。

**穿模检测**。身体被遮蔽挖了洞之后，「点在身体内」这种奇偶判定就不成立了；
而且衣服是单面壳，也没有内外之分。实际用的是：静置姿态下衣服永远在身体外侧，
记下这个方向；动作里如果身体顶点相对衣服法线的方向翻转了、而且衣服就在 6 mm 以内，
才算真的穿出。静置姿态下这个判据 0 误报。

**带物理的检测**。MMD 的碰撞组和遮罩在 Blender 里没有对应物，所以 `src/physics_sim.py`
把 MMD 的 group/mask 翻译成 Blender 的碰撞集合，让 Bullet 跑起来，再把仿真结果写回骨骼。
两个坑必须记住：MMD 要求**双方都允许**才算相撞，Blender 只要一方允许就撞（实测），
所以集合要按刚体收窄；`new_from_object` 读原始对象得到的是**未变形**的网格，
物理路径必须用 `evaluated.to_mesh()`。

**自动修复**。穿模的修法就是「把露出来的身体再遮掉」：取最差的那几个姿势（或真实动作的
最差几帧），把该状态下穿出的身体面删掉（扩大 Mask），再跑一遍全部姿势/帧对比。
判定看的是**总穿出量**而不是单帧 —— 修一帧常常会把问题推到下一帧，按单帧判会一直震荡；
没变好或者别的帧明显变差就整体回滚。报告会写清问题出在哪个身体区域（按高度分带统计穿出点数量）
和对应帧号，并给出修复前后的对比图。

## 目录结构

```
mmd/
  plan.md                      需求 / 顺序 / 验收标准
  progress.md                  进度与踩坑记录
  config/project.example.json  输入素体、来源、服装选择、输出目录、参数
  src/
    cli.py                     命令行入口（跑在 Blender 之外）
    blender_env.py             找 Blender、起后台进程
    import_export.py           PMX 导入 / 导出 / 清单（需要 bpy）
    extraction.py              服装材质与网格提取、预览
    dressing.py                骨架映射、体型适配、重新绑权、隐藏身体
    qa.py                      静态与动作 QA
  scripts/blender_runner.py    Blender 内运行的入口
  assets/                      本地输入（默认不提交）
  outputs/                     产物、预览、报告
```

## 注意事项

- 源文件永远不会被修改：程序一律「导入 → 另存」。
- 第三方模型只在本机使用，`.gitignore` 已经排除 `assets/*` 和 `outputs/`。
- Blender 5.x 的两个坑（后台模式 `object.select_all` 报错、`export_pmx` 的 poll 要求活动对象是 MMD 根物体）已在代码里处理，改动相关代码时请留意。
- 碰撞/物理相关的数字都要看 `progress.md` 里的说明：Blender 的刚体过滤是**单向**的，
  MMD 是**双向**的，所以带物理的 QA 是「代理仿真」，不能当成 MMD 本体的验收。
- 外部代码审查见 [`docs/REVIEW.md`](docs/REVIEW.md)，里面列了还没做完的部分
  （漆皮类服装的 body-derived shell、鞋楦变形、带物理的 A/B 方法论）。

