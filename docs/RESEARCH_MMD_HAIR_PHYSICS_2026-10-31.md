# MMD 头发物理来源核查：B站教程与夏安原工程

核查日期：2026-10-31。用户最新要求：先研究既有作者与插件的做法，不再沿用自行设计的混合物理、几何避让和时间滤波作为制作路线。旧工程和视频保留，本记录不是新视频验收。

## 夏安原工程：直接读到的证据

原始目录：`E:/data/模之屋/渲染/【夏安】BREAK ME DOWN!! - プレコ feat. 知声`。

检查其 ZIP 中对应的原始 `.blend`，而非本项目改造后的舞台：

- ZIP：`工程文件/「BREAK ME DOWN!!」プレコ feat. 知声【夏安】Blender 5.2.zip`。
- 已解包源文件：`E:/project/mmd/work/headswap_xl_codex/lookdev_reference_20261028/author_project/BREAK ME DOWN!! 20260902.blend`。
- `.blend` 大小 115018702 字节，CRC32 十进制 3264138709，与 ZIP 成员一致。
- 检查脚本只读打开，禁用文件内脚本，不执行模拟、不保存源文件。

### 头发实际播放链路

`Bake 动作中的骨骼旋转 → 夏安-Rig → 夏安-头发的 Armature 修改器 → UVTangent 着色辅助节点`

1. `夏安-头发` 没有 Cloth、Soft Body、Mesh Sequence Cache 修改器；其几何节点组是 `UVTangent`。
2. `夏安-Rig` 当前活动动作为 `Bake`，整份动作 332 条曲线、745385 个关键帧点，范围 0–5355。这个总数包括身体等，不能全部算成头发。
3. 20 根 `HairA1–A4 / HairB1–B2 / HairC1–C4 / HairD1–D4 / HairE1–E2 / HairF1–F2 / HairG1–G2` 均有四元数旋转曲线：每根 4 条，每条 5355 个点，帧 1–5355，合计 428400 个头发旋转关键帧点。数值有变化，并非四元数常量。
4. 这 20 根骨骼没有活动约束。当前文件没有刚体世界、刚体或刚体约束，没有 Cloth / Soft Body 修改器。因此当前渲染依靠骨骼动画重放，不是在每个渲染帧重新解头发物理。

### 新找到的插件线索：Jiggle Physics

`HairC1–HairC4` 还各有一条 `pose.bones["HairC…"].jiggle_blend` 参数曲线，每条 2 个点，位于 5034 和 5082 帧，值范围 0–0.3。

现成插件 [Jiggle Physics 作者仓库](https://github.com/naelstrof/blender-jiggle-physics) 的[源码](https://github.com/naelstrof/blender-jiggle-physics/blob/main/__init__.py)注册了同名 `PoseBone.jiggle_blend`，用于控制物理混合。参数名称与数据路径直接吻合，属于该插件的明确使用痕迹。

必须保留证据边界：这能支持工程曾使用 Jiggle Physics 参数，尤其是 HairC 链；不能仅凭四条残留参数曲线证明全部 20 根头发的旋转均由它生成。原文件未保留可读取的这组骨骼插件设置，准确版本、碰撞半径、碰撞目标和完整烘焙前状态尚不能还原。不能声称已经完整复刻作者物理，也不能反推为原生 MMD 或 XPBD。

该插件作者说明：它是 Wiggle 2 的分支，使用 Verlet 求解；支持缩放 Empty 碰撞体，网格碰撞支持有限；渲染前必须烘焙。作者也提示复杂约束骨架可能不匹配，建议作用于变形骨骼。上述是插件能力说明，不是本角色已通过测试的承诺。[作者文档](https://github.com/naelstrof/blender-jiggle-physics#readme)

### ABC 属于衣服

| 文件 | 源 ZIP 中大小 | 播放对象与传递方式 |
| --- | ---: | --- |
| `proxy/代理-外套烘焙.abc` | 194305232 字节 | 2970 顶点外套代理 → `夏安-外套` 的 Surface Deform |
| `proxy/代理-裙子烘焙.abc` | 61141784 字节 | 930 顶点裙子代理 → `夏安-裙子` 的 Surface Deform |

两个 CacheFile 的 frame_offset 都为 -120。外套另有局部 Shrinkwrap 指向身体，裙子另有局部 Shrinkwrap 指向 `夏安-碰撞体`。这些是衣服缓存的重放/贴合链路，不是头发缓存；仅凭 ABC 无法判定上游是 Blender Cloth 还是 MD。

已解包 author_project 缺少这两个代理文件，检查日志中的 ABC 缺失警告因此出现。源 ZIP 中两份缓存存在；本次未修改原始路径或重存工程。

### XPBD 与片尾

文件保存了 `Cloth Dynamics (Experimental)`、`XPBD Simulation`、`XPBD Solver` 节点组，但从所有对象的几何节点修改器递归遍历，未发现通向 XPBD 的实际对象链路。不能按数据块名称判断作者正在用 XPBD 解头发。

实际抽看原视频最后 12 秒及 171.2 秒借物表：片尾列出模型、音乐、动作和镜头，没有列物理插件。工程两个 Font 对象也没有提供物理工作流。未找到作者制作过程教程。

## B站：已读内容与候选分开

本次使用 `E:/project/bilibili` 的 Bilibili 技能和现有本地缓存。搜索 CLI 返回 -352，直接视频页返回 412 后停止 API 请求，没有换代理或重复请求。以下只有第一项实际读了全片字幕；第二项实际读了作者专栏。其余视频不能称为已经观看。

### Paper朱：阻尼追踪教程

[BV16rzpBcEFT《无需插件的MMD头发和服装物理如何制作？》](https://www.bilibili.com/video/BV16rzpBcEFT)，7:30。实际读取本地全片 `platform_subtitle`，轨道为 `ai-zh`，属于平台 AI 字幕；未观看关键帧画面，识别术语可能有错。

| 时间 | 字幕中的做法 | 对当前目标的意义 |
| --- | --- | --- |
| 00:21–00:30 | 需要已有骨骼权重 | 不是无需绑定的自动发丝模拟 |
| 00:53–01:27 | 添加阻尼追踪，调 Influence；过低会像粘住 | 能解释僵硬与摆幅调节 |
| 02:36–03:17 | 根部低、末端高，按区域设置 | 调整分布，不逐帧摆头发 |
| 03:21–03:57 | 靠近身体/手臂降低摆幅，留空大的地方增加 | 通过限制运动减轻穿模 |
| 04:31–05:13 | 刘海小幅摆动，贴皮肤的根部谨慎处理 | 需要为贴脸部分另设范围 |
| 05:55–06:15 | 删除不合适的追踪、修权重 | 作者也依赖绑定检查和局部修改 |

技术核对：[Blender 官方 Damped Track 文档](https://docs.blender.org/manual/en/latest/animation/constraints/tracking/damped_track.html)说明它是使骨骼朝向目标的追踪约束，“damped”指 swing 旋转方式。它本身不提供惯性、碰撞检测与碰撞响应。不能把字幕 06:17–06:31 关于“模型有刚体但未开物理”的说法当成防穿模保证。

视频简介另建议骨骼多而密的头发先在 MMD 本体烘焙再进入 Blender。简介与操作内容分别记录，不混称为画面证明。

本地字幕：`E:/project/bilibili/output/BV16rzpBcEFT/P01_35535782015/transcript.md`；manifest 保存字幕来源。

### Konak 流程的中文作者实现：布料代理驱动骨骼

[嘘嘘的小行星《blender快速物理骨骼生成-可用于代替MMD物理模拟》](https://www.bilibili.com/opus/1102988837620023384)，2025-08-20。实际读取专栏，作者注明来自粉くん / Konak 的思路。

做法是 Cloth 代理网格 → 骨骼追踪网格 → 原头发骨骼复制旋转；复制并精简身体、保留 Armature，再加 Collision。可保留 FK 修补。作者提供自动生成脚本，每次处理一条连续无分叉骨骼链，承认仍可能有轻微穿模。此为已有作者流程，尚未在本角色上复现验收。

### 仅查到简介的线索

[BV1vw411t7bY《MMD Blender用物理骨骼取代刚体物理 布料解算 头发解算》](https://www.bilibili.com/video/BV1vw411t7bY)，rint-，2023-12-13：简介列 BoneDynamicsPro 等工具。视频页风控，未取得正文/画面，因此不引用操作步骤。

## 其他现成路线与官方交叉核对

| 路线 | 已核实依据 | 限制/适用性 |
| --- | --- | --- |
| 原生 MMD + MMDBridge 烘焙 VMD | [MMD Tools 官方说明](https://github.com/MMD-Blender/blender_mmd_tools#rigid-body-physics-limitations)明确推荐 | Blender 与 MMD 的 Bullet 约束实现不同，导入 PMX 刚体并不保证同样效果。应校验 PMX 和身体/头发刚体适配，再由原生求解器烘焙 |
| MMD Tools Append：Rigid Body to Cloth | [官方 Wiki](https://github.com/MMD-Blender/blender_mmd_tools_append/wiki#physics-converter)有转换步骤；[Ulyssa 的 MMD 教程](https://ulyssas.github.io/my_tutorials/tutorial-blender/065-physics-sim/)明确用于衣服和头发 | 现成转换器，不必自己编写求解器；转换后仍要检查碰撞和显示网格 |
| BoneDynamics Pro | [开发者页面](https://superhivemarket.com/products/bonedynamics)说明骨骼链、整根骨骼碰撞和烘焙；2.0 使用 Cloth | 已存在的插件路线；未购买、未安装，不能据旧教程假定当前版本已经兼容本机所有设置 |
| Jiggle Physics | [作者仓库](https://github.com/naelstrof/blender-jiggle-physics)，与夏安残留参数直接吻合 | 现阶段最值得优先复现的夏安相关线索。需按作者文档建立碰撞并烘焙，不能把骨骼碰撞当作全部发片零穿模的证明 |

MMDBridge 作者要求先用 PMXEditor 和 MMD Tools 分别校验模型；支持 VMD/ABC 导出。[使用文档](https://github.com/rintrint/mmdbridge/blob/master/docs/how_to_use.md)

## 制作方向的修正

1. 停止继续生产旧的“25%物理位移混合 + 几何回退 + 自定义时间处理”候选。旧交付仅归档，用户没有接受这种制作方法。
2. 后续优先验证夏安有实际痕迹的 Jiggle Physics 原版工作流；若采用其他路线，使用上述有明确作者/文档的插件流程，记录来源和版本。自动化只负责插件配置、烘焙、渲染与检查，不再替代物理求解器或混入旧避让轨迹。
3. “先修初始穿模”仍必要，但不是后续不穿模的充分条件。后续还取决于碰撞体覆盖、骨骼/发片宽度、碰撞半径及运动；不能承诺开启物理就自动保证完整显示网格无穿模。
4. 保持完整角色展示与 11 秒重点复查，先做正常画面关键帧和连续动作验证，再全 450 帧。不要退回只有单束诊断的交付。
5. 服装流程暂停，保护抱手 256–321 不拆开，原文件保留，不恢复自动关机。原生 MMD 曾因电脑控制工具的应用访问限制而未能操作，不能绕过该拒绝改用其他通道启动；研究推荐与实际已完成的操作须分开。

## 证据文件

目录：`E:/project/mmd/work/headswap_xl_codex/mmd_physics_sources_20261031/`。

- `archive_inventory.json`：源 ZIP 成员与原始 blend 校验。
- `author_physics_inventory.json`：对象、修改器、骨骼、动作、缓存、文本。
- `author_physics_links.json`：实际修改器/几何节点依赖与骨骼约束。
- `author_hair_bake_details.json`：20 根头发曲线、四条 jiggle_blend 参数曲线及片内文字。
- `author_video_last12s.jpg`、`author_video_171_2.jpg`：本次实际查看的原视频抽帧。

2026-10-31 宿主进程核对：Blender GUI PID 60164 存在，未发现本项目后台渲染/解算任务；只读检查任务均已退出，未重复启动旧流水线。
