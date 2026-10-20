# MMD 成品模型拆衣与固定素体自动换装

从来源角色的 PMX 里自动拆出衣服，适配到固定的素体骨架上，导出可以直接丢进 MMD 使用的 PMX。

进度与已知问题见 [`progress.md`](progress.md)，需求与实施顺序见 [`plan.md`](plan.md)。

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

# 高风险姿势测试集（8 类），输出每个姿势的穿模数与截图
python -m src.cli motion-check --model outputs/dress01/model.pmx --out outputs/dress01/poses
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
再用 KD 树把这份覆盖率映射到目标身体并删面；腐蚀一圈，领口/袖口/下沿保留皮肤。
长发落在衣服里的部分单独检测后删除。

**穿模检测**。身体被遮蔽挖了洞之后，「点在身体内」这种奇偶判定就不成立了；
而且衣服是单面壳，也没有内外之分。实际用的是：静置姿态下衣服永远在身体外侧，
记下这个方向；动作里如果身体顶点相对衣服法线的方向翻转了、而且衣服就在 6 mm 以内，
才算真的穿出。静置姿态下这个判据 0 误报。

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
