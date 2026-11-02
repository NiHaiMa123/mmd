# 配置与运行

安装包是独立 legacy Blender add-on，测试版本 Blender 5.2.1。核心只依赖 Blender 自带 NumPy；MMD 元数据／约束需要原工程使用的 MMD Tools，通用英文骨架不需要。

```powershell
python scripts/run_contact.py --blender "D:\software\blender\5.2.1\blender.exe" --source "D:\models\dance.blend" --profile "D:\models\rig_profile.json" --out "D:\results\contact-001" --mode audit --first 1 --last 450 --step 5
```

改为 `--mode solve`，另选输出目录，生成独立候选工程。脚本拒绝复用已有回执的目录。后台日志 `worker.log`，回执 `job_status.json`。成功运行不等于修复通过；检查 acceptance 和报告，脚本以退出码 2 标记未通过候选。

界面：网格编辑模式选择面并标记 SurfaceClass；身体 1、头皮肤 2、真实头发 3、眼睛口内等不参与表面 0。材质名和几何高度不能可靠区分长发、皮肤和假阴影。MMD 按钮只生成初始映射，需检查辅助骨、控制骨和保护窗口。

JSON schema 1 的通用例见 [generic-profile.json](generic-profile.json)。

| 字段 | 含义 |
|---|---|
| mesh / armature | 实际对象名，允许任意语言 |
| units_to_m | 最终世界坐标一单位对应多少米；厘米坐标为 0.01 |
| surface_attribute | FACE / INT 属性，默认 SurfaceClass |
| bone_roles | 语义区域到实际变形骨：torso、head、arm.L/R、hand.L/R、leg.L/R |
| body_classes / head_classes / hair_classes / exclude_classes | 属性整数分类，未识别面不要自动忽略 |
| pairs | 有向检测对；普通手臂求解以 arm/hand 在前、head/torso 在后 |
| self_collision_regions | 可选，同一区域内部的三角自交；未配置时，28 对区域检测不包含同手手指、同腿内部自交 |
| protected_pairs | 有意双侧接触，延后并单列报告，不计作已解决 |
| protected_windows | start、end、intent；单位 Blender 帧，支持小数 |
| control_chains | 每条为上臂、肘、腕控制骨，当前要求四元数旋转 |
| preserve_wrist_orientation | 默认 true 补偿腕朝向；false 让腕部受限调整以处理关节折叠，保护窗口仍保留原动作 |
| protected_bones | 保留原动画的主骨，按实际骨架设置 |
| clearance_m | 间隙，米，常用 0.003 |
| rotation_limit_degrees | 每骨偏移上限，增大时同时复查动作 |
| verification_step | 子帧复查步长，默认 0.25；仍非 CCD |
| root_hair_anchor_bones | 真正头／颈附着骨，不是所有继承 head 角色的发骨 |

本版单网格接口要求最终求值顶点对应原顶点，不支持改变拓扑的修改器。普通身体 solve 要求一个活动 Action、无已有 NLA 栈；实验头发入口可接续已有修正栈。复杂 NLA／Rigify 控制器仍需适配，不能删掉原动画硬跑。

头发用 `--mode hair-experiment`，先读 [头发后端](hair-backends.md)，显式声明求解目标、主骨与是否允许手臂反馈；先跑 1–2 帧。输出固定为未验收实验，退出码 2 表示未满足完整头发验收，并非进程崩溃。

辅助骨继承最近已映射祖先；未映射身体三角形须补全；混合区域面保留，不能只取三个顶点都属于同一区域的面。

有意接触通常用时间窗口表达，不能因为一个抱手段而全程忽略左右手臂。protected_pairs 会全程延后该配对，只在动作全程确有此意图时设置。
