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

# 正式换装：拆衣 → 骨架映射 → 体型适配 → 重新绑权 → 隐藏身体 → 导出
python -m src.cli dress --source assets/source.pmx --target assets/base.pmx --out outputs/dress01

# 静态 / 动作检查
python -m src.cli qa --model outputs/dress01/model.pmx --motions assets/motions/
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
| `model.pmx` + `textures/` | 最终产物，可直接用 MMD 打开 |
| `work.blend` | 可人工继续修的中间工程 |
| `preview/` | 关键视角预览与错误标记图 |

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
